import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class ComplexityValidator:
    """
    Django-compliant password validator that enforces complexity rules:
    - Must contain at least one uppercase letter (A-Z)
    - Must contain at least one lowercase letter (a-z)
    - Must contain at least one digit (0-9)
    - Must contain at least one special character (non-alphanumeric)
    """
    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter (A-Z)."),
                code='password_no_upper',
            )
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter (a-z)."),
                code='password_no_lower',
            )
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("Password must contain at least one digit (0-9)."),
                code='password_no_number',
            )
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError(
                _("Password must contain at least one special character (e.g., @$!%*?&)."),
                code='password_no_special',
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character."
        )
