"""
REST API views for Credit Approval System.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from datetime import date
import calendar

from core.models import Customer, Loan
from core.serializers import (
    RegisterCustomerSerializer,
    CheckEligibilitySerializer,
    CreateLoanSerializer,
    LoanDetailSerializer,
    LoanListItemSerializer,
)
from core.services.eligibility_service import LoanEligibilityService


def _add_months(d: date, months: int) -> date:
    """Add months to a date, handling month-end edge cases."""
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


class RegisterView(APIView):
    """
    POST /register
    Register a new customer with approved_limit = 36 * monthly_income (rounded to nearest lakh).
    """

    def post(self, request):
        serializer = RegisterCustomerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        customer = serializer.save()
        
        return Response(
            {
                "customer_id": customer.id,
                "name": f"{customer.first_name} {customer.last_name}",
                "age": customer.age,
                "monthly_income": str(customer.monthly_salary),
                "approved_limit": str(customer.approved_limit),
                "phone_number": customer.phone_number,
            },
            status=status.HTTP_201_CREATED,
        )


class CheckEligibilityView(APIView):
    """
    POST /check-eligibility
    Check loan eligibility without creating a loan.
    """

    def post(self, request):
        serializer = CheckEligibilitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        customer = get_object_or_404(Customer, id=data["customer_id"])
        
        result = LoanEligibilityService.evaluate(
            customer=customer,
            loan_amount=data["loan_amount"],
            interest_rate=data["interest_rate"],
            tenure=data["tenure"],
        )
        
        return Response(
            {
                "customer_id": customer.id,
                "approval": result["approval"],
                "interest_rate": str(data["interest_rate"]),
                "corrected_interest_rate": str(result["corrected_interest_rate"]),
                "tenure": data["tenure"],
                "monthly_installment": str(result["monthly_installment"]),
            },
            status=status.HTTP_200_OK,
        )


class CreateLoanView(APIView):
    """
    POST /create-loan
    Create a loan if customer is eligible.
    """

    def post(self, request):
        serializer = CreateLoanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        customer_id = data["customer_id"]
        
        # Use transaction with row-level lock to prevent race conditions
        with transaction.atomic():
            customer = Customer.objects.select_for_update().get(id=customer_id)
            
            # Evaluate eligibility
            result = LoanEligibilityService.evaluate(
                customer=customer,
                loan_amount=data["loan_amount"],
                interest_rate=data["interest_rate"],
                tenure=data["tenure"],
            )
            
            # If not approved, return rejection
            if not result["approval"]:
                return Response(
                    {
                        "loan_id": None,
                        "customer_id": customer.id,
                        "loan_approved": False,
                        "message": result["message"],
                        "monthly_installment": str(result["monthly_installment"]),
                    },
                    status=status.HTTP_200_OK,
                )
            
            # Create loan
            start_date = date.today()
            end_date = _add_months(start_date, data["tenure"])
            
            loan = Loan.objects.create(
                customer=customer,
                loan_amount=data["loan_amount"],
                tenure=data["tenure"],
                interest_rate=result["corrected_interest_rate"],
                monthly_installment=result["monthly_installment"],
                emis_paid_on_time=0,
                start_date=start_date,
                end_date=end_date,
            )
            
            # Update customer's current debt
            from decimal import Decimal
            from django.utils import timezone
            from django.db.models import Sum
            today = timezone.now().date()
            active_loans_sum = customer.loans.filter(end_date__gt=today).aggregate(
                total=Sum("loan_amount")
            )["total"] or Decimal("0")
            customer.current_debt = active_loans_sum
            customer.save(update_fields=["current_debt"])
        
        return Response(
            {
                "loan_id": loan.id,
                "customer_id": customer.id,
                "loan_approved": True,
                "message": "Loan approved successfully",
                "monthly_installment": str(loan.monthly_installment),
            },
            status=status.HTTP_201_CREATED,
        )


class ViewLoanView(APIView):
    """
    GET /view-loan/<loan_id>
    Get details of a specific loan.
    """

    def get(self, request, loan_id):
        loan = get_object_or_404(Loan, id=loan_id)
        serializer = LoanDetailSerializer(loan)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ViewLoansByCustomerView(APIView):
    """
    GET /view-loans/<customer_id>
    Get all active loans for a customer.
    """

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)
        loans = customer.loans.filter(end_date__gt=date.today())
        serializer = LoanListItemSerializer(loans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
