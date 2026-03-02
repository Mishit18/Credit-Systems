"""
Core models for Credit Approval System.
"""
from decimal import Decimal
from datetime import date

from django.db import models


def round_to_nearest_lakh(value):
    """
    Round a numeric value to the nearest lakh (100,000).
    Example: 1,740,000 -> 1,700,000
    """
    from decimal import ROUND_HALF_UP
    if value is None:
        return Decimal("0")
    v = Decimal(str(value))
    lakh = Decimal("100000")
    return (v / lakh).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * lakh


class Customer(models.Model):
    """
    Customer with credit limit derived from monthly salary.
    approved_limit = 36 * monthly_salary, rounded to nearest lakh.
    """
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    age = models.IntegerField(default=0)
    phone_number = models.CharField(max_length=20)
    monthly_salary = models.DecimalField(max_digits=15, decimal_places=2)
    approved_limit = models.DecimalField(max_digits=15, decimal_places=2)
    current_debt = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0"))

    class Meta:
        db_table = "core_customer"
        ordering = ["id"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (ID: {self.id})"


class Loan(models.Model):
    """
    Loan tied to a customer.
    Active when current date < end_date.
    """
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    loan_amount = models.DecimalField(max_digits=15, decimal_places=2)
    tenure = models.IntegerField()  # months
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    monthly_installment = models.DecimalField(max_digits=15, decimal_places=2)
    emis_paid_on_time = models.IntegerField(default=0)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = "core_loan"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["customer", "end_date"], name="core_loan_cust_end_idx"),
        ]

    def __str__(self):
        return f"Loan {self.id} for Customer {self.customer_id}"

    @property
    def repayments_left(self):
        """Calculate remaining EMI payments."""
        return max(0, self.tenure - self.emis_paid_on_time)
