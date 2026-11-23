from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm


class RegisterForm(UserCreationForm):
    """
    Form for new user registration.
    Inherits from Django's built-in UserCreationForm and adds an email field.
    Applies clean Tailwind CSS classes for mobile-first styling.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
            'placeholder': 'name@example.com'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style username, password1, and password2 fields with Tailwind
        for field_name, field in self.fields.items():
            if field_name != 'email':
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                    'placeholder': field.label
                })


class LoginForm(AuthenticationForm):
    """
    Form for user login.
    Inherits from Django's built-in AuthenticationForm and applies Tailwind styling.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': field.label
            })
