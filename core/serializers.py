"""
DRF serializers for Credit Approval System.
"""
from rest_framework import serializers
from decimal import Decimal

from core.models import Customer, Loan, round_to_nearest_lakh


class RegisterCustomerSerializer(serializers.Serializer):
    """Serializer for POST /register request."""
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    age = serializers.IntegerField(min_value=0, max_value=150)
    monthly_income = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0)
    phone_number = serializers.CharField(max_length=20)

    def create(self, validated_data):
        monthly_income = Decimal(str(validated_data["monthly_income"]))
        approved_limit = round_to_nearest_lakh(36 * monthly_income)
        
        return Customer.objects.create(
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            age=validated_data["age"],
            phone_number=validated_data["phone_number"],
            monthly_salary=monthly_income,
            approved_limit=approved_limit,
            current_debt=Decimal("0"),
        )


class CheckEligibilitySerializer(serializers.Serializer):
    """Serializer for POST /check-eligibility request."""
    customer_id = serializers.IntegerField(min_value=1)
    loan_amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal("0.01"))
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    tenure = serializers.IntegerField(min_value=1)


class CreateLoanSerializer(serializers.Serializer):
    """Serializer for POST /create-loan request."""
    customer_id = serializers.IntegerField(min_value=1)
    loan_amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal("0.01"))
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    tenure = serializers.IntegerField(min_value=1)


class CustomerMinimalSerializer(serializers.ModelSerializer):
    """Customer subset for loan detail view."""
    class Meta:
        model = Customer
        fields = ("id", "first_name", "last_name", "phone_number", "age")


class LoanDetailSerializer(serializers.ModelSerializer):
    """Serializer for GET /view-loan/<id> response."""
    customer = CustomerMinimalSerializer(read_only=True)
    loan_id = serializers.IntegerField(source="id", read_only=True)
    loan_amount = serializers.SerializerMethodField()
    interest_rate = serializers.SerializerMethodField()
    monthly_installment = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = (
            "loan_id",
            "customer",
            "loan_amount",
            "interest_rate",
            "monthly_installment",
            "tenure",
        )
    
    def get_loan_amount(self, obj):
        return str(obj.loan_amount)
    
    def get_interest_rate(self, obj):
        return str(obj.interest_rate)
    
    def get_monthly_installment(self, obj):
        return str(obj.monthly_installment)


class LoanListItemSerializer(serializers.ModelSerializer):
    """Serializer for single item in GET /view-loans/<customer_id> list."""
    loan_id = serializers.IntegerField(source="id", read_only=True)
    repayments_left = serializers.IntegerField(read_only=True)
    loan_amount = serializers.SerializerMethodField()
    interest_rate = serializers.SerializerMethodField()
    monthly_installment = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = (
            "loan_id",
            "loan_amount",
            "interest_rate",
            "monthly_installment",
            "repayments_left",
        )
    
    def get_loan_amount(self, obj):
        return str(obj.loan_amount)
    
    def get_interest_rate(self, obj):
        return str(obj.interest_rate)
    
    def get_monthly_installment(self, obj):
        return str(obj.monthly_installment)
