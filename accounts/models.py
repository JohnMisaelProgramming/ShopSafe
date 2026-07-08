from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class OTPVerification(models.Model):
    """
    Stores temporary Two-Factor Authentication OTPs.
    Codes are valid for 5 minutes and can only be verified 3 times max.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.user.username} — {'Verified' if self.verified else 'Active'}"


class UserLockout(models.Model):
    """
    Tracks failed login attempts and lockouts per username.
    This tracks both valid users and non-existent accounts for brute force protection.
    """
    username = models.CharField(max_length=150, unique=True)
    failed_attempts = models.IntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)
    last_attempt = models.DateTimeField(auto_now=True)

    def is_locked(self):
        if self.lockout_until and timezone.now() < self.lockout_until:
            return True
        return False

    def __str__(self):
        status = "Locked" if self.is_locked() else "Active"
        return f"{self.username} — Failures: {self.failed_attempts} ({status})"
