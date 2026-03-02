"""
EMI calculation using compound interest formula.

Formula: EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)
Where:
  P = Principal (loan amount)
  r = Monthly interest rate (annual_rate / 1200)
  n = Tenure in months
"""
from decimal import Decimal, ROUND_HALF_UP


class EMIService:
    """Service for computing monthly installment with Decimal precision."""

    @staticmethod
    def calculate_emi(loan_amount, interest_rate, tenure):
        """
        Compute EMI using compound interest formula.
        
        :param loan_amount: Principal amount (Decimal or float)
        :param interest_rate: Annual interest rate (e.g., 12 for 12%)
        :param tenure: Number of months (int)
        :return: EMI as Decimal, rounded to 2 decimal places
        """
        P = Decimal(str(loan_amount))
        R = Decimal(str(interest_rate))
        n = int(tenure)
        
        if n <= 0:
            return Decimal("0")
        
        # Convert annual rate to monthly rate: r = R / (12 * 100)
        r = R / Decimal("1200")
        
        # Handle zero interest edge case
        if r == Decimal("0"):
            emi = P / Decimal(n)
            return emi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Calculate (1 + r)^n
        one_plus_r = Decimal("1") + r
        one_plus_r_n = one_plus_r ** n
        
        # Apply EMI formula
        emi = P * r * one_plus_r_n / (one_plus_r_n - Decimal("1"))
        return emi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
