"""
Loan eligibility evaluation service.

Evaluates loan applications based on:
1. Credit score slabs (determines minimum interest rate)
2. Approved credit limit
3. 50% EMI-to-salary ratio rule
"""
from decimal import Decimal
from django.utils import timezone

from core.services.emi_service import EMIService
from core.services.credit_score_service import CreditScoreService


class LoanEligibilityService:
    """
    Evaluates loan eligibility and determines corrected interest rate.
    
    Credit Score Slabs:
    - Score > 50: Approve at any rate
    - 30 < Score <= 50: Approve only if rate > 12%
    - 10 < Score <= 30: Approve only if rate > 16%
    - Score <= 10: Reject
    """

    @classmethod
    def evaluate(cls, customer, loan_amount, interest_rate, tenure):
        """
        Evaluate loan eligibility for a customer.
        
        :param customer: Customer instance
        :param loan_amount: Requested loan amount (Decimal)
        :param interest_rate: Requested annual interest rate (Decimal)
        :param tenure: Loan tenure in months (int)
        :return: dict with approval, corrected_interest_rate, monthly_installment, message
        """
        loan_amount = Decimal(str(loan_amount))
        interest_rate = Decimal(str(interest_rate))
        
        # Get active loans
        today = timezone.now().date()
        active_loans = customer.loans.filter(end_date__gt=today)
        total_active_amount = sum(Decimal(str(loan.loan_amount)) for loan in active_loans)
        
        # Check if new loan would exceed approved limit
        if total_active_amount + loan_amount > customer.approved_limit:
            return {
                "approval": False,
                "corrected_interest_rate": interest_rate,
                "monthly_installment": Decimal("0"),
                "message": "Loan amount exceeds approved credit limit"
            }
        
        # Calculate credit score
        score = CreditScoreService.calculate_score(customer)
        
        # Determine approval and corrected interest rate based on credit score slab
        if score > 50:
            # Excellent credit: approve at requested rate
            corrected_rate = interest_rate
            approved = True
        elif score > 30:
            # Good credit: require rate > 12%
            if interest_rate <= Decimal("12"):
                corrected_rate = Decimal("12.01")
            else:
                corrected_rate = interest_rate
            approved = True
        elif score > 10:
            # Fair credit: require rate > 16%
            if interest_rate <= Decimal("16"):
                corrected_rate = Decimal("16.01")
            else:
                corrected_rate = interest_rate
            approved = True
        else:
            # Poor credit: reject
            return {
                "approval": False,
                "corrected_interest_rate": interest_rate,
                "monthly_installment": Decimal("0"),
                "message": "Credit score too low"
            }
        
        # Calculate EMI with corrected rate
        monthly_installment = EMIService.calculate_emi(loan_amount, corrected_rate, tenure)
        
        # Check 50% EMI-to-salary rule
        total_current_emis = sum(Decimal(str(loan.monthly_installment)) for loan in active_loans)
        total_emis_with_new = total_current_emis + monthly_installment
        
        if total_emis_with_new > customer.monthly_salary * Decimal("0.5"):
            return {
                "approval": False,
                "corrected_interest_rate": corrected_rate,
                "monthly_installment": monthly_installment,
                "message": "EMIs exceed 50% of monthly salary"
            }
        
        return {
            "approval": approved,
            "corrected_interest_rate": corrected_rate,
            "monthly_installment": monthly_installment,
            "message": ""
        }
