import secrets
import logging
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse

from accounts.models import OTPVerification, UserLockout
from accounts.forms import SignUpForm
from accounts.recaptcha import verify_recaptcha
from accounts.audit_logger import log_event

logger = logging.getLogger(__name__)


def generate_secure_otp():
    """Generates a secure 6-digit numeric OTP using secrets."""
    return "".join(secrets.choice("0123456789") for _ in range(6))


def save_otp_to_file(user_email, otp_code):
    """Saves the OTP code to a flat text file in the workspace root for developer reference."""
    try:
        otp_file_path = os.path.join(settings.BASE_DIR.parent, 'otp.txt')
        with open(otp_file_path, 'w') as f:
            f.write(f"To: {user_email}\nOTP Code: {otp_code}\nGenerated At: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        logger.error(f"Failed to write OTP to file: {e}")



def login_view(request):
    """
    Renders login form and processes authentication with:
    - IP-based rate limiting (HTTP 429)
    - Username-based account lockout (15 minutes lockout)
    - Google reCAPTCHA v3 server-side validation
    - Two-Factor Authentication (2FA) redirection
    - CSRF protection & audit logging
    """
    if request.user.is_authenticated:
        return redirect('home')

    # Get client IP for rate limiting
    from accounts.audit_logger import get_client_ip
    ip = get_client_ip(request)

    # 1. Rate Limiting Check (Limit failed logins by IP using Django Cache)
    from django.core.cache import cache
    ip_fail_key = f"ip_login_failures:{ip}"
    ip_lock_key = f"ip_login_lock:{ip}"

    if cache.get(ip_lock_key):
        log_event(request, 'blocked', details=f"IP {ip} blocked due to rate limit exhaustion.")
        return HttpResponse("Too Many Requests. Login limit exceeded for this IP. Please try again later.", status=429)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        
        # Resolve email to username to support logging in via email
        if '@' in username:
            try:
                user_obj = User.objects.get(email__iexact=username)
                username = user_obj.username
            except User.DoesNotExist:
                pass

        post_data = request.POST.copy()
        post_data['username'] = username
        form = AuthenticationForm(request, data=post_data)


        # 2. Google reCAPTCHA verification
        recaptcha_token = request.POST.get('g-recaptcha-response') or request.POST.get('recaptcha_token') or ''
        # We perform server verification
        recaptcha_passed, score = verify_recaptcha(recaptcha_token, ip)
        
        # In a real environment, we'd check if recaptcha_passed and score >= 0.5.
        # But we verify token and score threshold gracefully
        if not recaptcha_passed or score < 0.5:
            log_event(request, 'failed_login', details=f"reCAPTCHA validation failed. Score: {score}")
            recaptcha_site_key = getattr(settings, 'RECAPTCHA_SITE_KEY', '')
            return render(request, 'accounts/login.html', {
                'form': form,
                'recaptcha_error': "Google reCAPTCHA validation failed. Please try again.",
                'recaptcha_site_key': recaptcha_site_key
            })

        # 3. Account Lockout Check (Check lockout model status)
        lockout_record, _ = UserLockout.objects.get_or_create(username=username)
        if lockout_record.is_locked():
            # Auto unlock logic check: if duration expired
            if timezone.now() > lockout_record.lockout_until:
                lockout_record.failed_attempts = 0
                lockout_record.lockout_until = None
                lockout_record.save()
            else:
                remaining_time = int((lockout_record.lockout_until - timezone.now()).total_seconds() / 60)
                form.add_error('username', f"Account locked due to too many failed attempts. Try again in {remaining_time} minute(s).")
                log_event(request, 'lockout', username=username, details="Attempted login on locked account.")

        if not form.errors and form.is_valid():
            # Credentials are valid
            user = form.get_user()
            
            # Reset failure tracking
            lockout_record.failed_attempts = 0
            lockout_record.lockout_until = None
            lockout_record.save()
            cache.delete(ip_fail_key)

            # Do NOT call login(request, user) yet — redirect to 2FA view!
            # Store pre-authenticated user in session
            request.session['pre_2fa_user_id'] = user.id
            request.session.set_expiry(300) # 5 minutes expiry for 2FA screen
            
            # Generate & Save OTP
            otp_code = generate_secure_otp()
            expires_at = timezone.now() + timedelta(minutes=5)
            OTPVerification.objects.create(
                user=user,
                otp_code=otp_code,
                expires_at=expires_at
            )

            # Save OTP to file in workspace root
            save_otp_to_file(user.email or 'user@shopsafe.local', otp_code)

            # Send OTP via console (or configured mail backend)
            from django.core.mail import send_mail
            subject = "ShopSafe Two-Factor Authentication OTP"
            message = f"Your ShopSafe Two-Factor Authentication code is: {otp_code}. Valid for 5 minutes."
            try:
                send_mail(
                    subject,
                    message,
                    'noreply@shopsafe.local',
                    [user.email or 'user@shopsafe.local'],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send 2FA email to {user.email}: {e}")

            # Print to stdout in dev console so analyst can easily find it without SMTP
            print(f"\n[2FA EMAIL SIMULATOR] To: {user.email} | OTP Code: {otp_code}\n")

            log_event(request, 'otp_verification', username=username, details="OTP generated and sent to email.")
            messages.info(request, "A Two-Factor Authentication code has been sent to your registered email.")
            return redirect('verify_2fa')
        else:
            # Failed credentials (only check if form wasn't locked out)
            if not lockout_record.is_locked() or (timezone.now() > lockout_record.lockout_until if lockout_record.lockout_until else True):
                # Increment failed attempts
                lockout_record.failed_attempts += 1
                if lockout_record.failed_attempts >= 5:
                    lockout_record.lockout_until = timezone.now() + timedelta(minutes=15)
                    form.add_error('username', "⚠ Account locked out due to 5 failed attempts. Please try again in 15 minutes.")
                    log_event(request, 'lockout', username=username, details="Account locked out for 15 minutes.")
                else:
                    form.add_error('username', "⚠ Invalid username or password. Please try again.")
                    form.add_error('password', "⚠ Invalid username or password. Please try again.")
                    log_event(request, 'failed_login', username=username, details=f"Failed attempt {lockout_record.failed_attempts} of 5.")
                lockout_record.save()

            # Increment IP failures
            failures = cache.get(ip_fail_key, 0) + 1
            cache.set(ip_fail_key, failures, timeout=300) # 5 minutes tracking
            if failures >= 10:
                # Lockout IP for 10 minutes
                cache.set(ip_lock_key, True, timeout=600)
                log_event(request, 'blocked', details=f"IP {ip} locked out for 10 minutes due to 10 failed login attempts.")
    else:
        form = AuthenticationForm()

    recaptcha_site_key = getattr(settings, 'RECAPTCHA_SITE_KEY', '')
    return render(request, 'accounts/login.html', {'form': form, 'recaptcha_site_key': recaptcha_site_key})



def verify_2fa_view(request):
    """
    Two-Factor Authentication OTP input verification view.
    Executes session key regeneration upon successful validation.
    """
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        otp_entered = request.POST.get('otp_code', '').strip()
        
        # Get active OTP records for the user
        otp_record = OTPVerification.objects.filter(
            user=user,
            verified=False
        ).order_by('-created_at').first()

        if not otp_record:
            messages.error(request, "No active verification code found. Please request a new code.")
            return render(request, 'accounts/verify_2fa.html')

        # Check OTP expiration
        if otp_record.is_expired():
            messages.error(request, "Verification code has expired. Please request a new code.")
            log_event(request, 'otp_verification', username=user.username, details="Expired OTP attempt.")
            return render(request, 'accounts/verify_2fa.html')

        # Check attempts limit
        otp_record.attempts += 1
        if otp_record.attempts > 3:
            otp_record.expires_at = timezone.now() # Expire it immediately
            otp_record.save()
            messages.error(request, "Too many failed verification attempts. Please request a new code.")
            log_event(request, 'otp_verification', username=user.username, details="OTP attempts limit exceeded.")
            return render(request, 'accounts/verify_2fa.html')

        otp_record.save()

        # Check code correctness
        if otp_entered == otp_record.otp_code:
            # Success! Mark OTP verified
            otp_record.verified = True
            otp_record.save()

            # Secure Session Regeneration (Prevents Session Fixation)
            request.session.cycle_key()

            # Perform actual Django Login
            login(request, user)
            
            # Clean session variables
            del request.session['pre_2fa_user_id']

            log_event(request, 'otp_verification', username=user.username, details="OTP verification success.")
            messages.success(request, f"Welcome back, {user.username}! Two-factor authentication verified.")
            return redirect('home')
        else:
            messages.error(request, f"⚠ Invalid code. You have {3 - otp_record.attempts} attempts remaining.")
            log_event(request, 'otp_verification', username=user.username, details=f"Invalid OTP entered: {otp_entered}")

    return render(request, 'accounts/verify_2fa.html')


def resend_otp_view(request):
    """
    Handles request to regenerate and resend a 2FA OTP code.
    Is rate-limited to prevent email spamming.
    """
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, pk=user_id)

    # Prevent spamming: check if last OTP was sent less than 30 seconds ago
    last_otp = OTPVerification.objects.filter(user=user).order_by('-created_at').first()
    if last_otp and (timezone.now() - last_otp.created_at).total_seconds() < 30:
        messages.error(request, "Please wait 30 seconds before requesting another code.")
        return redirect('verify_2fa')

    # Generate & Save new OTP
    otp_code = generate_secure_otp()
    expires_at = timezone.now() + timedelta(minutes=5)
    OTPVerification.objects.create(
        user=user,
        otp_code=otp_code,
        expires_at=expires_at
    )

    # Save OTP to file in workspace root
    save_otp_to_file(user.email or 'user@shopsafe.local', otp_code)

    # Send OTP
    from django.core.mail import send_mail
    try:
        send_mail(
            "ShopSafe Two-Factor Authentication OTP (Resent)",
            f"Your ShopSafe Two-Factor Authentication code is: {otp_code}. Valid for 5 minutes.",
            'noreply@shopsafe.local',
            [user.email or 'user@shopsafe.local'],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Failed to resend 2FA email: {e}")

    # Dev console output
    print(f"\n[2FA EMAIL SIMULATOR - RESEND] To: {user.email} | OTP Code: {otp_code}\n")

    log_event(request, 'otp_verification', username=user.username, details="OTP resent to email.")
    messages.success(request, "A new verification code has been sent to your email.")
    return redirect('verify_2fa')


def register_view(request):
    """
    Renders and processes user registration with:
    - Google reCAPTCHA v3 verification
    - Strong password policy complexity validation
    - Security audit logging
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        # Google reCAPTCHA check
        from accounts.audit_logger import get_client_ip
        ip = get_client_ip(request)
        recaptcha_token = request.POST.get('g-recaptcha-response') or request.POST.get('recaptcha_token') or ''
        recaptcha_passed, score = verify_recaptcha(recaptcha_token, ip)
        
        if not recaptcha_passed or score < 0.5:
            recaptcha_site_key = getattr(settings, 'RECAPTCHA_SITE_KEY', '')
            return render(request, 'accounts/register.html', {
                'form': SignUpForm(request.POST),
                'recaptcha_error': "Google reCAPTCHA validation failed. Please try again.",
                'recaptcha_site_key': recaptcha_site_key
            })

        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_event(request, 'successful_login', username=user.username, details="New account created successfully.")
            
            # Immediately trigger 2FA view on registration
            request.session['pre_2fa_user_id'] = user.id
            
            otp_code = generate_secure_otp()
            expires_at = timezone.now() + timedelta(minutes=5)
            OTPVerification.objects.create(
                user=user,
                otp_code=otp_code,
                expires_at=expires_at
            )

            # Save OTP to file in workspace root
            save_otp_to_file(user.email or 'user@shopsafe.local', otp_code)

            # Send OTP
            from django.core.mail import send_mail
            try:
                send_mail(
                    "ShopSafe Two-Factor Authentication OTP",
                    f"Your ShopSafe Two-Factor Authentication code is: {otp_code}. Valid for 5 minutes.",
                    'noreply@shopsafe.local',
                    [user.email or 'user@shopsafe.local'],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send 2FA email: {e}")

            print(f"\n[2FA EMAIL SIMULATOR - REGISTER] To: {user.email} | OTP Code: {otp_code}\n")
            messages.success(request, "✓ Registration successful! Please verify your email OTP to complete login.")
            return redirect('verify_2fa')
        else:
            # Form errors are rendered inline in the template
            pass
    else:
        form = SignUpForm()
        
    recaptcha_site_key = getattr(settings, 'RECAPTCHA_SITE_KEY', '')
    return render(request, 'accounts/register.html', {'form': form, 'recaptcha_site_key': recaptcha_site_key})



def logout_view(request):
    """
    Logs the user out of the session and generates an audit log.
    """
    username = request.user.username if request.user.is_authenticated else 'anonymous'
    log_event(request, 'logout', username=username, details="User initiated sign out.")
    logout(request)
    messages.info(request, "You have been logged out of your session.")
    return redirect('home')


@login_required
def profile_view(request):
    """
    Renders user profile information.
    """
    return render(request, 'accounts/profile.html')


def forgot_password_view(request):
    """
    Renders forgot password stub page with reCAPTCHA v3 checks.
    """
    recaptcha_site_key = getattr(settings, 'RECAPTCHA_SITE_KEY', '')
    if request.method == 'POST':
        from accounts.audit_logger import get_client_ip
        ip = get_client_ip(request)
        recaptcha_token = request.POST.get('g-recaptcha-response') or request.POST.get('recaptcha_token') or ''
        recaptcha_passed, score = verify_recaptcha(recaptcha_token, ip)

        if not recaptcha_passed or score < 0.5:
            return render(request, 'accounts/forgot_password.html', {
                'recaptcha_error': "Google reCAPTCHA validation failed. Please try again.",
                'recaptcha_site_key': recaptcha_site_key
            })

        email = request.POST.get('email', '').strip()
        messages.success(request, f"A reset link has been dispatched to {email} if the account exists.")
        log_event(request, 'otp_verification', details=f"Password reset requested for {email}")
        return redirect('login')

    return render(request, 'accounts/forgot_password.html', {'recaptcha_site_key': recaptcha_site_key})

