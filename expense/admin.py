from django.contrib import admin
from .models import Category, Expense, Income, Budget


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    list_filter = ('user',)
    search_fields = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'amount', 'category', 'user', 'date', 'created_at')
    list_filter = ('category', 'date', 'user')
    search_fields = ('title', 'description')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('source', 'amount', 'user', 'date', 'created_at')
    list_filter = ('date', 'user')
    search_fields = ('source', 'description')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'amount', 'month', 'year', 'user', 'created_at')
    list_filter = ('year', 'month', 'category', 'user')
    search_fields = ('category__name',)
    ordering = ('-year', '-month')
