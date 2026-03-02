"""
Credit score calculation (0-100) based on loan history.

Scoring Components:
1. Past loans paid on time (40 points max)
2. Number of loans taken (15 points max)
3. Loan activity in current year (20 points max)
4. Loan approved volume vs limit (25 points max)

Special Rule: If sum of current loans > approved_limit, score = 0
"""
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce


class CreditScoreService:
    """Calculate credit score out of 100 based on customer loan history."""

    @classmethod
    def calculate_score(cls, customer):
        """
        Calculate credit score for a customer.
        
        :param customer: Customer instance
        :return: float score between 0 and 100
        """
        today = timezone.now().date()
        
        # Check if current loans exceed approved limit
        active_loans_sum = customer.loans.filter(end_date__gt=today).aggregate(
            total=Coalesce(Sum("loan_amount"), Decimal("0"))
        )["total"]
        
        if active_loans_sum > customer.approved_limit:
            return 0.0
        
        # Get loan statistics using database aggregation
        loan_stats = customer.loans.aggregate(
            total_emis=Coalesce(Sum("tenure"), 0),
            paid_on_time=Coalesce(Sum("emis_paid_on_time"), 0),
            num_loans=Count("id"),
            total_volume=Coalesce(Sum("loan_amount"), Decimal("0"))
        )
        
        num_loans = loan_stats["num_loans"]
        
        # No loan history: return baseline score of 40
        if num_loans == 0:
            return 40.0
        
        # Component 1: On-time payment ratio (0-40 points)
        total_emis = loan_stats["total_emis"]
        paid_on_time = loan_stats["paid_on_time"]
        on_time_ratio = Decimal(paid_on_time) / Decimal(total_emis) if total_emis > 0 else Decimal("0")
        on_time_score = min(Decimal("1"), on_time_ratio) * Decimal("40")
        
        # Component 2: Number of loans (0-15 points)
        # More loans with good behavior = more experience
        loan_count_ratio = min(Decimal("1"), Decimal(num_loans) / Decimal("10"))
        loan_count_score = loan_count_ratio * Decimal("15")
        
        # Component 3: Current year activity (0-20 points)
        current_year = timezone.now().year
        current_year_loans = customer.loans.filter(start_date__year=current_year).count()
        current_year_ratio = min(Decimal("1"), Decimal(current_year_loans) / Decimal("2"))
        current_year_score = current_year_ratio * Decimal("20")
        
        # Component 4: Volume utilization (0-25 points)
        # Lower utilization = higher score (encourages responsible borrowing)
        total_volume = loan_stats["total_volume"]
        if customer.approved_limit > 0:
            utilization = min(Decimal("1"), total_volume / customer.approved_limit)
            volume_score = (Decimal("1") - utilization) * Decimal("25")
        else:
            volume_score = Decimal("0")
        
        # Calculate total score
        total = on_time_score + loan_count_score + current_year_score + volume_score
        total = min(Decimal("100"), max(Decimal("0"), total))
        
        return float(total.quantize(Decimal("0.01")))
