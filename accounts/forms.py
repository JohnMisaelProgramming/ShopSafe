from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

class SignUpForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter strong password'}),
        help_text="Must be at least 12 characters, and contain uppercase, lowercase, digits, and special characters."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )
    accept_terms = forms.BooleanField(
        required=True,
        label="I accept the Terms and Conditions",
        error_messages={'required': 'You must accept the Terms and Conditions to register.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
        }

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # Run Django configured validators (Complexity + Length >= 12)
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

