import calendar
from django import forms
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Expense, Category, Income, Budget

MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]


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


class ExpenseForm(forms.ModelForm):
    """
    ModelForm for adding and editing an Expense.
    Automatically generates form fields matching the Expense model.
    """
    class Meta:
        model = Expense
        fields = ['title', 'amount', 'category', 'date', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': 'e.g. Grocery shopping, Metro pass'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-white'
            }),
            'date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'type': 'date'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': 'Optional notes or receipt details...',
                'rows': 3
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter categories: system defaults (user=None) + user's custom categories
        if user is not None:
            self.fields['category'].queryset = Category.objects.filter(
                Q(user=user) | Q(user__isnull=True)
            ).order_by('name')
        else:
            self.fields['category'].queryset = Category.objects.filter(user__isnull=True).order_by('name')


class IncomeForm(forms.ModelForm):
    """
    ModelForm for adding and editing an Income record.
    Automatically generates form fields matching the Income model.
    """
    class Meta:
        model = Income
        fields = ['source', 'amount', 'date', 'description']
        widgets = {
            'source': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': 'e.g. Monthly Salary, Freelance project, Dividend'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'type': 'date'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': 'Optional details or notes...',
                'rows': 3
            }),
        }


class CategoryForm(forms.ModelForm):
    """
    ModelForm for adding or editing custom categories.
    Validates that category names are unique per user and don't clash with defaults.
    """
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': 'e.g. Gym, Subscriptions, Pets, Books'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Category name cannot be empty.")

        # Check for duplicate in system defaults or user's custom categories
        query = Q(name__iexact=name) & (Q(user__isnull=True) | Q(user=self.user))
        if self.instance and self.instance.pk:
            exists = Category.objects.filter(query).exclude(pk=self.instance.pk).exists()
        else:
            exists = Category.objects.filter(query).exists()

        if exists:
            raise forms.ValidationError(f"A category named '{name}' already exists.")
        return name


class BudgetForm(forms.ModelForm):
    """
    ModelForm for setting and editing monthly budgets per category.
    """
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-white'
        })
    )

    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month', 'year']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-white'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'year': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition',
                'placeholder': 'YYYY',
                'min': '2020',
                'max': '2099'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['category'].queryset = Category.objects.filter(
                Q(user=user) | Q(user__isnull=True)
            ).order_by('name')
        else:
            self.fields['category'].queryset = Category.objects.filter(user__isnull=True).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')

        if category and month and year and self.user:
            query = Budget.objects.filter(
                user=self.user,
                category=category,
                month=int(month),
                year=year
            )
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                month_name = calendar.month_name[int(month)]
                raise forms.ValidationError(
                    f"A budget for '{category.name}' in {month_name} {year} already exists. Please edit that budget instead."
                )

        return cleaned_data




