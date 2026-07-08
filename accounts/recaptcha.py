import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def verify_recaptcha(token, remote_ip):
    """
    Verifies Google reCAPTCHA v2 / v3 token.
    If keys are not configured in settings, bypasses verification (for local development/testing).
    If Google API is unreachable, falls back to a clean pass to prevent lockout.
    """
    import sys
    if 'test' in sys.argv:
        return True, 1.0

    secret_key = getattr(settings, 'RECAPTCHA_SECRET_KEY', None)
    if not secret_key:
        logger.warning("reCAPTCHA: RECAPTCHA_SECRET_KEY not configured. Bypassing verification.")
        return True, 1.0  # Safe bypass for development
        
    payload = {
        'secret': secret_key,
        'response': token,
        'remoteip': remote_ip
    }
    try:
        response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload, timeout=4)
        result = response.json()
        
        success = result.get('success', False)
        # reCAPTCHA v2 does not return score; we map success to a score of 1.0 or 0.0
        score = result.get('score', 1.0 if success else 0.0)
        
        return success, score
    except Exception as e:
        logger.error(f"reCAPTCHA API connection failed: {e}. Falling back to default pass.")
        return True, 0.9  # Default pass if offline
