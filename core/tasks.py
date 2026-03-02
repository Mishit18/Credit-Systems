"""
Celery tasks for data ingestion from Excel files.
"""
import os
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from celery import shared_task
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Sum, OuterRef, Subquery
from django.db.models.functions import Coalesce

from core.models import Customer, Loan, round_to_nearest_lakh


def _normalize_columns(df):
    """Normalize DataFrame column names: strip, lowercase, replace spaces with underscores."""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _safe_decimal(val, default=Decimal("0")):
    """Safely convert value to Decimal."""
    try:
        return Decimal(str(val))
    except Exception:
        return default


@shared_task(bind=True, name="core.tasks.ingest_customer_and_loan_data")
def ingest_customer_and_loan_data(self, customer_path=None, loan_path=None):
    """
    Ingest customer and loan data from Excel files.
    
    This task:
    1. Reads customer_data.xlsx and loan_data.xlsx
    2. Bulk creates Customer and Loan records
    3. Updates current_debt for all customers
    
    Uses atomic transaction to ensure data consistency.
    """
    import pandas as pd

    # Resolve file paths
    data_dir = getattr(settings, "DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    customer_path = customer_path or getattr(settings, "CUSTOMER_DATA_PATH", None)
    loan_path = loan_path or getattr(settings, "LOAN_DATA_PATH", None)
    
    if not customer_path or not os.path.isabs(customer_path):
        customer_path = os.path.join(data_dir, customer_path or "customer_data.xlsx")
    if not loan_path or not os.path.isabs(loan_path):
        loan_path = os.path.join(data_dir, loan_path or "loan_data.xlsx")

    if not os.path.isfile(customer_path):
        return {"status": "error", "message": f"Customer file not found: {customer_path}"}
    if not os.path.isfile(loan_path):
        return {"status": "error", "message": f"Loan file not found: {loan_path}"}

    # Read and process customer data
    df_customers = pd.read_excel(customer_path, engine="openpyxl")
    df_customers = _normalize_columns(df_customers)

    customers_to_create = []
    existing_customer_ids = set(Customer.objects.values_list("id", flat=True))
    
    for _, row in df_customers.iterrows():
        cid = row.get("customer_id")
        if pd.isna(cid):
            continue
        cid = int(cid)
        if cid in existing_customer_ids:
            continue
        
        first_name = str(row.get("first_name", "")).strip() or "Unknown"
        last_name = str(row.get("last_name", "")).strip() or "Unknown"
        phone_number = str(row.get("phone_number", "")).strip() or "0"
        monthly_salary = _safe_decimal(row.get("monthly_salary", 0))
        approved_limit = _safe_decimal(row.get("approved_limit", 0))
        
        if approved_limit <= 0:
            approved_limit = round_to_nearest_lakh(36 * monthly_salary)
        
        current_debt = _safe_decimal(row.get("current_debt", 0))
        
        customers_to_create.append(
            Customer(
                id=cid,
                first_name=first_name,
                last_name=last_name,
                age=0,
                phone_number=phone_number,
                monthly_salary=monthly_salary,
                approved_limit=approved_limit,
                current_debt=current_debt,
            )
        )

    # Read and process loan data
    df_loans = pd.read_excel(loan_path, engine="openpyxl")
    df_loans = _normalize_columns(df_loans)

    loans_to_create = []
    customer_ids = set(Customer.objects.values_list("id", flat=True))
    existing_loan_ids = set(Loan.objects.values_list("id", flat=True))
    
    for _, row in df_loans.iterrows():
        customer_id = row.get("customer_id")
        if pd.isna(customer_id):
            continue
        customer_id = int(customer_id)
        if customer_id not in customer_ids:
            continue
        
        loan_id = row.get("loan_id") or row.get("id")
        loan_id = int(loan_id) if loan_id is not None and not pd.isna(loan_id) else None
        if loan_id is not None and loan_id in existing_loan_ids:
            continue
        
        loan_amount = _safe_decimal(row.get("loan_amount", 0))
        if loan_amount <= 0:
            continue
        
        tenure = int(row.get("tenure", 12))
        interest_rate = _safe_decimal(row.get("interest_rate", 0))
        
        monthly_repayment = row.get("monthly_repayment") or row.get("emi") or row.get("monthly_installment")
        monthly_installment = _safe_decimal(monthly_repayment, Decimal("0"))
        
        emis_paid = int(row.get("emis_paid_on_time", 0))
        
        # Parse dates
        start_date = row.get("start_date")
        end_date = row.get("end_date")
        
        if pd.isna(start_date):
            start_date = timezone.now().date()
        else:
            if hasattr(start_date, "date"):
                start_date = start_date.date()
            elif isinstance(start_date, datetime):
                start_date = start_date.date()
            else:
                start_date = timezone.now().date()
        
        if pd.isna(end_date):
            end_date = start_date
        else:
            if hasattr(end_date, "date"):
                end_date = end_date.date()
            elif isinstance(end_date, datetime):
                end_date = end_date.date()
            else:
                end_date = start_date
        
        loans_to_create.append(
            Loan(
                id=loan_id,
                customer_id=customer_id,
                loan_amount=loan_amount,
                tenure=tenure,
                interest_rate=interest_rate,
                monthly_installment=monthly_installment,
                emis_paid_on_time=emis_paid,
                start_date=start_date,
                end_date=end_date,
            )
        )

    # Atomic ingestion with table locks
    with transaction.atomic():
        # Lock tables to prevent conflicts with concurrent API operations
        with connection.cursor() as cur:
            cur.execute("LOCK TABLE core_customer IN SHARE ROW EXCLUSIVE MODE")
            cur.execute("LOCK TABLE core_loan IN SHARE ROW EXCLUSIVE MODE")
        
        # Bulk create customers
        if customers_to_create:
            Customer.objects.bulk_create(customers_to_create, ignore_conflicts=True)
            # Reset sequence to avoid ID conflicts
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT setval(pg_get_serial_sequence('core_customer', 'id'), "
                    "(SELECT COALESCE(MAX(id), 1) FROM core_customer));"
                )

        # Bulk create loans
        if loans_to_create:
            Loan.objects.bulk_create(loans_to_create, ignore_conflicts=True)
            # Reset sequence to avoid ID conflicts
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT setval(pg_get_serial_sequence('core_loan', 'id'), "
                    "(SELECT COALESCE(MAX(id), 1) FROM core_loan));"
                )

        # Recompute current_debt for all customers using single bulk update
        today = timezone.now().date()
        active_loan_sum = Loan.objects.filter(
            customer=OuterRef("pk"),
            end_date__gt=today
        ).values("customer").annotate(
            total=Coalesce(Sum("loan_amount"), Decimal("0"))
        ).values("total")

        Customer.objects.update(
            current_debt=Coalesce(Subquery(active_loan_sum), Decimal("0"))
        )

    return {
        "status": "ok",
        "customers_created": len(customers_to_create),
        "loans_created": len(loans_to_create),
    }
