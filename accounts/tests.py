from django.test import TestCase, Client  # type: ignore
from django.contrib.auth.models import User  # type: ignore
from django.core.cache import cache  # type: ignore
from django.urls import reverse  # type: ignore
from django.utils import timezone  # type: ignore
from datetime import timedelta

from accounts.models import OTPVerification, UserLockout

class SecurityEnhancementTests(TestCase):
    """
    Test suite verifying ShopSafe security controls:
    - Strong Password Validation
    - Account Lockout limits
    - 2FA (OTP) flow redirection
    """

    def setUp(self):
        self.client = Client()
        self.username = "test_sec_officer"
        self.email = "officer@shopsafe.local"
        self.strong_password = "P@ssword123456!"
        self.weak_password = "weak"
        
        # Create a valid user
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.strong_password
        )
        cache.clear()

    def test_strong_password_policy_enforcement(self):
        """Verifies that weak passwords are rejected during registration."""
        url = reverse('register')
        
        # Try registering with a weak password (fails length + complexity)
        response = self.client.post(url, {
            'username': 'new_user',
            'email': 'new@shopsafe.local',
            'password': self.weak_password,
            'confirm_password': self.weak_password,
            'recaptcha_token': 'mock_token'
        })
        # Registration fails (returns back registration page or shows error)
        # Verify user is not created in DB
        self.assertFalse(User.objects.filter(username='new_user').exists())

    def test_login_rate_limiting_and_lockout(self):
        """Verifies account gets locked after 5 failed login attempts."""
        url = reverse('login')
        
        # Fail login 5 times
        for i in range(5):
            self.client.post(url, {
                'username': self.username,
                'password': 'WrongPassword!',
                'recaptcha_token': 'mock_token'
            })
            
        # Verify lockout record exists and is active
        lockout = UserLockout.objects.get(username=self.username)  # type: ignore
        self.assertTrue(lockout.is_locked())

    def test_2fa_otp_redirection_flow(self):
        """Verifies that valid credentials redirect to the 2FA verify page and generate an OTP."""
        url = reverse('login')
        response = self.client.post(url, {
            'username': self.username,
            'password': self.strong_password,
            'recaptcha_token': 'mock_token'
        })
        
        # Should redirect to OTP verification screen
        self.assertRedirects(response, reverse('verify_2fa'))
        
        # Verify an OTP code was generated in the database
        otp = OTPVerification.objects.filter(user=self.user, verified=False).first()  # type: ignore
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.otp_code), 6)
