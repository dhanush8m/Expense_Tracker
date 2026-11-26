import calendar
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone

from .models import Expense, Category, Income, Budget
from .forms import RegisterForm, LoginForm, ExpenseForm, IncomeForm, CategoryForm, BudgetForm


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


# ---------------------------------------------------------------------------
# Category Views
# ---------------------------------------------------------------------------

@login_required
def category_list(request):
    """
    Displays system default categories and user-created custom categories.
    Annotates custom categories with how many expenses are linked to them.
    """
    default_categories = Category.objects.filter(user__isnull=True).order_by('name')
    user_categories = (
        Category.objects.filter(user=request.user)
        .annotate(expense_count=Count('expenses'))
        .order_by('name')
    )

    context = {
        'default_categories': default_categories,
        'user_categories': user_categories,
    }
    return render(request, 'categories/category_list.html', context)


@login_required
def category_create(request):
    """
    Handles creating a new custom category for the logged-in user.
    """
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f"Category '{category.name}' created successfully.")
            return redirect('category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm(user=request.user)

    context = {
        'form': form,
        'page_title': 'Add Custom Category',
        'submit_btn_text': 'Create Category',
        'is_edit': False,
    }
    return render(request, 'categories/category_form.html', context)


@login_required
def category_update(request, pk):
    """
    Handles editing a user's custom category.
    Security: get_object_or_404 ensures only custom categories belonging to request.user
    can be edited. System default categories (user=None) cannot be edited!
    """
    category = get_object_or_404(Category, pk=pk, user=request.user)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated successfully.")
            return redirect('category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm(instance=category, user=request.user)

    context = {
        'form': form,
        'category': category,
        'page_title': 'Edit Category',
        'submit_btn_text': 'Save Changes',
        'is_edit': True,
    }
    return render(request, 'categories/category_form.html', context)


@login_required
def category_delete(request, pk):
    """
    Handles deleting a user's custom category.
    Security: get_object_or_404 ensures system defaults cannot be deleted.
    Warns the user if expenses are currently using this category.
    """
    category = get_object_or_404(Category, pk=pk, user=request.user)
    linked_expenses_count = category.expenses.filter(user=request.user).count()

    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted successfully.")
        return redirect('category_list')

    context = {
        'category': category,
        'linked_expenses_count': linked_expenses_count,
    }
    return render(request, 'categories/category_confirm_delete.html', context)


# ---------------------------------------------------------------------------
# Budget Views
# ---------------------------------------------------------------------------

@login_required
def budget_list(request):
    """
    Displays the user's monthly budgets for a selected month/year.
    Computes spent amount, remaining amount, percentage, and exceeded alerts.
    """
    today = timezone.now().date()

    # Get selected month and year from GET params or default to current
    try:
        selected_month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        selected_month = today.month

    try:
        selected_year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        selected_year = today.year

    # Ensure month is within 1-12
    if selected_month < 1 or selected_month > 12:
        selected_month = today.month

    month_name = calendar.month_name[selected_month]

    # Query budgets for selected month/year
    budgets = Budget.objects.filter(
        user=request.user,
        month=selected_month,
        year=selected_year
    ).select_related('category')

    budget_items = []
    total_budgeted = Decimal('0.00')
    total_spent = Decimal('0.00')

    for b in budgets:
        # Sum expenses in this category for this month/year
        spent = Expense.objects.filter(
            user=request.user,
            category=b.category,
            date__year=selected_year,
            date__month=selected_month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        remaining = b.amount - spent
        percent = min(int((spent / b.amount) * 100), 100) if b.amount > 0 else 0
        raw_percent = int((spent / b.amount) * 100) if b.amount > 0 else 0
        is_exceeded = spent > b.amount

        total_budgeted += b.amount
        total_spent += spent

        budget_items.append({
            'budget': b,
            'spent': spent,
            'remaining': remaining,
            'percent': percent,
            'raw_percent': raw_percent,
            'is_exceeded': is_exceeded,
        })

    total_remaining = total_budgeted - total_spent
    overall_percent = min(int((total_spent / total_budgeted) * 100), 100) if total_budgeted > 0 else 0

    # Month and Year selection options for dropdown filters
    months_list = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years_list = range(today.year - 2, today.year + 3)

    context = {
        'budget_items': budget_items,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'month_name': month_name,
        'total_budgeted': total_budgeted,
        'total_spent': total_spent,
        'total_remaining': total_remaining,
        'overall_percent': overall_percent,
        'months_list': months_list,
        'years_list': years_list,
    }
    return render(request, 'budgets/budget_list.html', context)


@login_required
def budget_create(request):
    """
    Handles creating a new monthly budget limit for a category.
    """
    today = timezone.now().date()
    if request.method == 'POST':
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, f"Budget of ₹{budget.amount} set for '{budget.category.name}'.")
            return redirect(f"/budgets/?month={budget.month}&year={budget.year}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        month_param = request.GET.get('month', today.month)
        year_param = request.GET.get('year', today.year)
        form = BudgetForm(user=request.user, initial={'month': month_param, 'year': year_param})

    context = {
        'form': form,
        'page_title': 'Create Monthly Budget',
        'submit_btn_text': 'Set Budget',
        'is_edit': False,
    }
    return render(request, 'budgets/budget_form.html', context)


@login_required
def budget_update(request, pk):
    """
    Handles updating an existing budget.
    Security: get_object_or_404 ensures the budget belongs to request.user.
    """
    budget = get_object_or_404(Budget, pk=pk, user=request.user)

    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Budget for '{budget.category.name}' updated successfully.")
            return redirect(f"/budgets/?month={budget.month}&year={budget.year}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BudgetForm(instance=budget, user=request.user)

    context = {
        'form': form,
        'budget': budget,
        'page_title': 'Edit Budget',
        'submit_btn_text': 'Save Changes',
        'is_edit': True,
    }
    return render(request, 'budgets/budget_form.html', context)


@login_required
def budget_delete(request, pk):
    """
    Handles deleting an existing budget.
    Security: get_object_or_404 ensures the budget belongs to request.user.
    """
    budget = get_object_or_404(Budget, pk=pk, user=request.user)

    if request.method == 'POST':
        cat_name = budget.category.name
        month = budget.month
        year = budget.year
        budget.delete()
        messages.success(request, f"Budget for '{cat_name}' removed.")
        return redirect(f"/budgets/?month={month}&year={year}")

    return render(request, 'budgets/budget_confirm_delete.html', {'budget': budget})


# ---------------------------------------------------------------------------
# Transaction History Views (Phase 11)
# ---------------------------------------------------------------------------

@login_required
def transaction_history(request):
    """
    Unified transaction history combining Expense and Income records.
    Filters at the database level using Django querysets:
      - Type: 'all', 'expense', 'income'
      - Category: category ID
      - Date Range: start_date to end_date
      - Search keyword: q (title/source or description)
      - Sorting: newest, oldest, highest, lowest amount
    """
    trans_type = request.GET.get('type', 'all').strip()
    if trans_type not in ['all', 'expense', 'income']:
        trans_type = 'all'

    q = request.GET.get('q', '').strip()
    selected_category = request.GET.get('category', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    sort = request.GET.get('sort', '-date').strip()

    allowed_sorts = {
        '-date': 'Newest first',
        'date': 'Oldest first',
        '-amount': 'Highest amount',
        'amount': 'Lowest amount',
    }
    if sort not in allowed_sorts:
        sort = '-date'

    # Base Querysets with user ownership enforced
    exp_qs = Expense.objects.filter(user=request.user).select_related('category')
    inc_qs = Income.objects.filter(user=request.user)

    # Apply database filters to Expenses
    if q:
        exp_qs = exp_qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if selected_category:
        exp_qs = exp_qs.filter(category_id=selected_category)
    if start_date:
        exp_qs = exp_qs.filter(date__gte=start_date)
    if end_date:
        exp_qs = exp_qs.filter(date__lte=end_date)

    # Apply database filters to Income
    if selected_category:
        # Income doesn't belong to an expense category; exclude when filtering by category
        inc_qs = inc_qs.none()
    else:
        if q:
            inc_qs = inc_qs.filter(Q(source__icontains=q) | Q(description__icontains=q))
        if start_date:
            inc_qs = inc_qs.filter(date__gte=start_date)
        if end_date:
            inc_qs = inc_qs.filter(date__lte=end_date)

    transactions = []
    total_expense = Decimal('0.00')
    total_income = Decimal('0.00')

    if trans_type in ['all', 'expense']:
        total_expense = exp_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        for e in exp_qs:
            transactions.append({
                'id': e.id,
                'type': 'expense',
                'title': e.title,
                'category': e.category.name,
                'category_initial': e.category.name[:1],
                'amount': e.amount,
                'date': e.date,
                'description': e.description,
                'url': f'/expenses/{e.id}/',
                'created_at': e.created_at,
            })

    if trans_type in ['all', 'income']:
        total_income = inc_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        for i in inc_qs:
            transactions.append({
                'id': i.id,
                'type': 'income',
                'title': i.source,
                'category': 'Income',
                'category_initial': '+',
                'amount': i.amount,
                'date': i.date,
                'description': i.description,
                'url': f'/income/{i.id}/',
                'created_at': i.created_at,
            })

    # Sort the combined transactions
    if sort == 'date':
        transactions.sort(key=lambda x: (x['date'], x['created_at']))
    elif sort == '-amount':
        transactions.sort(key=lambda x: x['amount'], reverse=True)
    elif sort == 'amount':
        transactions.sort(key=lambda x: x['amount'])
    else:  # '-date'
        transactions.sort(key=lambda x: (x['date'], x['created_at']), reverse=True)

    net_difference = total_income - total_expense

    categories = Category.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('name')

    has_active_filters = bool(
        q or selected_category or start_date or end_date or trans_type != 'all' or sort != '-date'
    )

    context = {
        'transactions': transactions,
        'total_expense': total_expense,
        'total_income': total_income,
        'net_difference': net_difference,
        'trans_type': trans_type,
        'q': q,
        'selected_category': selected_category,
        'start_date': start_date,
        'end_date': end_date,
        'current_sort': sort,
        'allowed_sorts': allowed_sorts,
        'categories': categories,
        'has_active_filters': has_active_filters,
    }
    return render(request, 'transactions/transaction_list.html', context)


# ---------------------------------------------------------------------------
# Reports & Analytics View (Phase 12)
# ---------------------------------------------------------------------------

@login_required
def reports_view(request):
    """
    Computes comprehensive analytics and reports for the user:
      - KPI Summary (Income, Expenses, Net Balance, Savings Rate)
      - Category-wise spending breakdown with percentages
      - Monthly trends (Income vs Expenses over the year)
      - Formatted JSON data for lightweight Chart.js rendering
    """
    today = timezone.now().date()

    # Default to 2026 or whatever year is requested
    try:
        selected_year = int(request.GET.get('year', 2026))
    except (ValueError, TypeError):
        selected_year = 2026

    # 1. High-Level KPIs for the selected year
    year_income = Income.objects.filter(user=request.user, date__year=selected_year)
    year_expenses = Expense.objects.filter(user=request.user, date__year=selected_year)

    total_income = year_income.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expenses = year_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_savings = total_income - total_expenses

    if total_income > 0:
        savings_rate = min(max(int((net_savings / total_income) * 100), 0), 100)
    else:
        savings_rate = 0

    # 2. Category-Wise Spending Breakdown
    cat_qs = (
        year_expenses.values('category__name')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    category_breakdown = []
    chart_cat_labels = []
    chart_cat_values = []

    for item in cat_qs:
        amount = item['total']
        percent = int((amount / total_expenses) * 100) if total_expenses > 0 else 0
        category_breakdown.append({
            'name': item['category__name'],
            'amount': amount,
            'percent': percent,
            'count': item['count'],
        })
        chart_cat_labels.append(item['category__name'])
        chart_cat_values.append(float(amount))

    # 3. Monthly Trends (12 Months of the selected year)
    monthly_labels = []
    monthly_income_data = []
    monthly_expense_data = []
    monthly_summary_table = []

    for m in range(1, 13):
        m_name = calendar.month_abbr[m]
        m_inc = year_income.filter(date__month=m).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        m_exp = year_expenses.filter(date__month=m).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        m_net = m_inc - m_exp

        monthly_labels.append(m_name)
        monthly_income_data.append(float(m_inc))
        monthly_expense_data.append(float(m_exp))

        if m_inc > 0 or m_exp > 0:
            monthly_summary_table.append({
                'month': calendar.month_name[m],
                'income': m_inc,
                'expense': m_exp,
                'net': m_net,
            })

    # Dynamically extract all years from this user's expenses and income
    user_expense_years = Expense.objects.filter(user=request.user).dates('date', 'year')
    user_income_years = Income.objects.filter(user=request.user).dates('date', 'year')

    available_years = set()
    for d in user_expense_years:
        available_years.add(d.year)
    for d in user_income_years:
        available_years.add(d.year)

    # Always ensure 2026, today's year, and next upcoming year are available
    available_years.add(2026)
    available_years.add(today.year)
    available_years.add(today.year + 1)
    if selected_year:
        available_years.add(selected_year)

    # Sorted newest year first (e.g. 2027, 2026, 2025...)
    years_list = sorted(list(available_years), reverse=True)

    context = {
        'selected_year': selected_year,
        'years_list': years_list,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_savings': net_savings,
        'savings_rate': savings_rate,
        'category_breakdown': category_breakdown,
        'monthly_summary_table': monthly_summary_table,
        'chart_cat_labels_json': json.dumps(chart_cat_labels),
        'chart_cat_values_json': json.dumps(chart_cat_values),
        'monthly_labels_json': json.dumps(monthly_labels),
        'monthly_income_json': json.dumps(monthly_income_data),
        'monthly_expense_json': json.dumps(monthly_expense_data),
    }
    return render(request, 'reports/reports.html', context)





