from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegisterForm, LoginForm


def register_view(request):
    """
    Handles user registration.
    If user is already logged in, redirects to dashboard.
    If POST, validates form, creates user, logs them in, and redirects to dashboard.
    If GET, displays registration form.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to ExpenseWise, {user.username}! Your account has been created.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    """
    Handles user login.
    If user is already logged in, redirects to dashboard.
    If POST, authenticates user credentials, creates session, and redirects.
    If GET, displays login form.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    """
    Handles user logout.
    Terminates the session and redirects to login page.
    """
    if request.method == 'POST':
        logout(request)
        messages.info(request, "You have been logged out successfully.")
        return redirect('login')
    return redirect('dashboard')


@login_required
def dashboard_view(request):
    """
    User dashboard view (full analytics added in Phase 8).
    Protected: only accessible by logged-in users.
    """
    return render(request, 'dashboard/dashboard.html', {'user': request.user})
