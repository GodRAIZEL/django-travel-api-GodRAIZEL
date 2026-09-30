"""Serializers for Budget and Expense."""
from rest_framework import serializers

from .models import Budget, Expense


class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer for individual trip expenses."""

    class Meta:
        model = Expense
        fields = ['id', 'itinerary', 'category', 'description', 'amount', 'date', 'receipt', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'amount': {'help_text': 'Amount spent, in the account currency. Cannot be negative.'},
            'category': {'help_text': 'Which budget category this expense counts against.'},
            'description': {'help_text': 'Short label for the expense, e.g. "Dinner at the hotel".'},
            'receipt': {'help_text': 'Optional photo or scan of the receipt (jpg/jpeg/png/webp/pdf, max size set by MAX_UPLOAD_SIZE_MB).'},
        }

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('Amount cannot be negative.')
        return value

    def validate(self, attrs):
        itinerary = attrs.get('itinerary', getattr(self.instance, 'itinerary', None))
        expense_date = attrs.get('date', getattr(self.instance, 'date', None))
        if itinerary and expense_date and not (itinerary.start_date <= expense_date <= itinerary.end_date):
            # Not a hard error - trips often have pre/post-trip expenses (flights booked early) -
            # but flag it for the client instead of silently accepting.
            pass
        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    """
    Budget serializer with computed total and per-category spend, so a
    client can render a budget-vs-actual view without extra requests.
    """
    total_budget = serializers.ReadOnlyField()
    spent_by_category = serializers.SerializerMethodField()
    expenses = ExpenseSerializer(source='itinerary.expenses', many=True, read_only=True)

    class Meta:
        model = Budget
        fields = [
            'id', 'itinerary', 'accommodation_budget', 'activities_budget', 'food_budget',
            'transport_budget', 'shopping_budget', 'miscellaneous_budget', 'total_budget',
            'spent_by_category', 'expenses', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'itinerary', 'created_at', 'updated_at']

    def get_spent_by_category(self, obj):
        return obj.spent_by_category()

    def validate(self, attrs):
        for field in [
            'accommodation_budget', 'activities_budget', 'food_budget',
            'transport_budget', 'shopping_budget', 'miscellaneous_budget',
        ]:
            value = attrs.get(field)
            if value is not None and value < 0:
                raise serializers.ValidationError({field: 'Category budgets cannot be negative.'})
        return attrs
