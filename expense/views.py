from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Expense, Category, Income, Budget
from .forms import RegisterForm, LoginForm, ExpenseForm, IncomeForm


# ---------------------------------------------------------------------------
# Authentication Views
# ---------------------------------------------------------------------------

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
    User dashboard: computes financial summaries, current month stats,
    top category spending, budget status, and recent activity feed.
    """
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month
    month_name = today.strftime('%B')

    # 1. Total Income, Total Expenses, and Net Balance
    total_income = Income.objects.filter(user=request.user).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expenses = Expense.objects.filter(user=request.user).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_balance = total_income - total_expenses

    # 2. Current Month Spending
    this_month_expenses = Expense.objects.filter(
        user=request.user,
        date__year=current_year,
        date__month=current_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # 3. Top Spending Category this Month
    top_cat = (
        Expense.objects.filter(user=request.user, date__year=current_year, date__month=current_month)
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
        .first()
    )
    if not top_cat:
        # Fall back to all-time top category if none this month
        top_cat = (
            Expense.objects.filter(user=request.user)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
            .first()
        )
    top_category_name = top_cat['category__name'] if top_cat else None
    top_category_amount = top_cat['total'] if top_cat else Decimal('0.00')

    # 4. Active Budgets for this month
    budgets = Budget.objects.filter(
        user=request.user,
        month=current_month,
        year=current_year
    ).select_related('category')
    budget_summary = []
    for b in budgets:
        spent = Expense.objects.filter(
            user=request.user,
            category=b.category,
            date__year=current_year,
            date__month=current_month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        percent = min(int((spent / b.amount) * 100), 100) if b.amount > 0 else 0
        budget_summary.append({
            'category_name': b.category.name,
            'budget_amount': b.amount,
            'spent': spent,
            'remaining': b.amount - spent,
            'percent': percent,
            'is_exceeded': spent > b.amount,
        })

    # 5. Recent Combined Activity (Latest 5 items)
    recent_exp = list(Expense.objects.filter(user=request.user).select_related('category')[:5])
    recent_inc = list(Income.objects.filter(user=request.user)[:5])
    recent_transactions = []
    for e in recent_exp:
        recent_transactions.append({
            'title': e.title,
            'amount': e.amount,
            'category': e.category.name,
            'date': e.date,
            'type': 'expense',
            'url': f'/expenses/{e.id}/'
        })
    for i in recent_inc:
        recent_transactions.append({
            'title': i.source,
            'amount': i.amount,
            'category': 'Income',
            'date': i.date,
            'type': 'income',
            'url': f'/income/{i.id}/'
        })
    recent_transactions.sort(key=lambda x: x['date'], reverse=True)
    recent_transactions = recent_transactions[:5]

    context = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_balance': net_balance,
        'this_month_expenses': this_month_expenses,
        'month_name': month_name,
        'top_category_name': top_category_name,
        'top_category_amount': top_category_amount,
        'budget_summary': budget_summary,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'dashboard/dashboard.html', context)


# ---------------------------------------------------------------------------
# Expense CRUD Views
# ---------------------------------------------------------------------------

@login_required
def expense_list(request):
    """
    Displays the list of expenses for the currently logged-in user.
    Supports search (title/description), category filter, and sorting.
    Calculates total amount for the currently filtered results.
    """
    # 1. Base Queryset - Strictly filtered by logged-in user
    queryset = Expense.objects.filter(user=request.user).select_related('category')

    # 2. Search query (title or description)
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(description__icontains=q))

    # 3. Filter by category
    selected_category = request.GET.get('category', '').strip()
    if selected_category:
        queryset = queryset.filter(category_id=selected_category)

    # 4. Sorting
    sort = request.GET.get('sort', '-date').strip()
    allowed_sorts = {
        '-date': 'Newest first',
        'date': 'Oldest first',
        '-amount': 'Highest amount',
        'amount': 'Lowest amount',
        'title': 'Title (A-Z)'
    }
    if sort in allowed_sorts:
        queryset = queryset.order_by(sort)
    else:
        sort = '-date'
        queryset = queryset.order_by('-date')

    # 5. Aggregate total for current filtered view
    total_amount = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # 6. Categories available to this user for the filter dropdown
    categories = Category.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('name')

    context = {
        'expenses': queryset,
        'categories': categories,
        'total_amount': total_amount,
        'q': q,
        'selected_category': selected_category,
        'current_sort': sort,
        'allowed_sorts': allowed_sorts,
    }
    return render(request, 'expenses/expense_list.html', context)


@login_required
def expense_create(request):
    """
    Handles creating a new expense.
    Assigns the logged-in user automatically on save.
    """
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            # commit=False creates the model instance without saving to PostgreSQL yet
            expense = form.save(commit=False)
            # Ensure the user is ALWAYS the logged-in user
            expense.user = request.user
            expense.save()
            messages.success(request, f"Expense '{expense.title}' of ₹{expense.amount} added successfully.")
            return redirect('expense_list')
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        # Default date to today
        form = ExpenseForm(user=request.user, initial={'date': timezone.now().date()})

    context = {
        'form': form,
        'page_title': 'Add Expense',
        'submit_btn_text': 'Add Expense',
        'is_edit': False,
    }
    return render(request, 'expenses/expense_form.html', context)


@login_required
def expense_detail(request, pk):
    """
    Displays full details of a single expense.
    Security: get_object_or_404 ensures the expense belongs to request.user.
    """
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    return render(request, 'expenses/expense_detail.html', {'expense': expense})


@login_required
def expense_update(request, pk):
    """
    Handles updating an existing expense.
    Security: get_object_or_404 ensures the expense belongs to request.user.
    """
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Expense '{expense.title}' updated successfully.")
            return redirect('expense_list')
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = ExpenseForm(instance=expense, user=request.user)

    context = {
        'form': form,
        'expense': expense,
        'page_title': 'Edit Expense',
        'submit_btn_text': 'Save Changes',
        'is_edit': True,
    }
    return render(request, 'expenses/expense_form.html', context)


@login_required
def expense_delete(request, pk):
    """
    Handles deleting an existing expense.
    Security: get_object_or_404 ensures the expense belongs to request.user.
    Requires POST request to perform the actual deletion.
    """
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == 'POST':
        title = expense.title
        amount = expense.amount
        expense.delete()
        messages.success(request, f"Expense '{title}' (₹{amount}) deleted successfully.")
        return redirect('expense_list')

    return render(request, 'expenses/expense_confirm_delete.html', {'expense': expense})


# ---------------------------------------------------------------------------
# Income CRUD Views
# ---------------------------------------------------------------------------

@login_required
def income_list(request):
    """
    Displays the list of income records for the currently logged-in user.
    Supports search (source/description) and sorting.
    Calculates total income for the currently filtered results.
    """
    queryset = Income.objects.filter(user=request.user)

    # Search query (source or description)
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(Q(source__icontains=q) | Q(description__icontains=q))

    # Sorting
    sort = request.GET.get('sort', '-date').strip()
    allowed_sorts = {
        '-date': 'Newest first',
        'date': 'Oldest first',
        '-amount': 'Highest amount',
        'amount': 'Lowest amount',
        'source': 'Source (A-Z)'
    }
    if sort in allowed_sorts:
        queryset = queryset.order_by(sort)
    else:
        sort = '-date'
        queryset = queryset.order_by('-date')

    # Aggregate total income
    total_amount = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'incomes': queryset,
        'total_amount': total_amount,
        'q': q,
        'current_sort': sort,
        'allowed_sorts': allowed_sorts,
    }
    return render(request, 'income/income_list.html', context)


@login_required
def income_create(request):
    """
    Handles adding a new income record.
    Assigns the logged-in user automatically on save.
    """
    if request.method == 'POST':
        form = IncomeForm(request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            messages.success(request, f"Income '{income.source}' of ₹{income.amount} added successfully.")
            return redirect('income_list')
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = IncomeForm(initial={'date': timezone.now().date()})

    context = {
        'form': form,
        'page_title': 'Add Income',
        'submit_btn_text': 'Add Income',
        'is_edit': False,
    }
    return render(request, 'income/income_form.html', context)


@login_required
def income_detail(request, pk):
    """
    Displays full details of a single income record.
    Security: get_object_or_404 ensures the income belongs to request.user.
    """
    income = get_object_or_404(Income, pk=pk, user=request.user)
    return render(request, 'income/income_detail.html', {'income': income})


@login_required
def income_update(request, pk):
    """
    Handles editing an existing income record.
    Security: get_object_or_404 ensures the income belongs to request.user.
    """
    income = get_object_or_404(Income, pk=pk, user=request.user)

    if request.method == 'POST':
        form = IncomeForm(request.POST, instance=income)
        if form.is_valid():
            form.save()
            messages.success(request, f"Income '{income.source}' updated successfully.")
            return redirect('income_list')
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = IncomeForm(instance=income)

    context = {
        'form': form,
        'income': income,
        'page_title': 'Edit Income',
        'submit_btn_text': 'Save Changes',
        'is_edit': True,
    }
    return render(request, 'income/income_form.html', context)


@login_required
def income_delete(request, pk):
    """
    Handles deleting an existing income record.
    Security: get_object_or_404 ensures the income belongs to request.user.
    Requires POST request to perform the actual deletion.
    """
    income = get_object_or_404(Income, pk=pk, user=request.user)

    if request.method == 'POST':
        source = income.source
        amount = income.amount
        income.delete()
        messages.success(request, f"Income '{source}' (₹{amount}) deleted successfully.")
        return redirect('income_list')

    return render(request, 'income/income_confirm_delete.html', {'income': income})

