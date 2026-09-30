from django.contrib import admin

from .models import Budget, Expense


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['itinerary', 'total_budget']
    search_fields = ['itinerary__title']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['description', 'itinerary', 'category', 'amount', 'date']
    list_filter = ['category']
    search_fields = ['description']
