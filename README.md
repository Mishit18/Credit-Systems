# Credit Approval System

A Django-based REST API for credit approval and loan management with automated credit scoring and eligibility evaluation.

## Overview

This system provides APIs for customer registration, loan eligibility checking, loan creation, and loan management. It includes background processing for bulk data ingestion from Excel files and implements credit scoring based on loan history and repayment behavior.

## Technology Stack

- Django 4.2+
- Django Rest Framework 3.14+
- PostgreSQL 15
- Redis 7
- Celery (background task processing)
- Gunicorn (WSGI server)
- Docker & Docker Compose

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- Docker Compose installed

### Running the Application

Navigate to the project directory and run:

```bash
docker-compose up --build
```

This single command will:
- Start PostgreSQL database
- Start Redis cache
- Run database migrations automatically
- Start the Django web server on port 8000
- Start the Celery worker for background tasks

The API will be available at `http://localhost:8000`

### Stopping the Application

Press `Ctrl+C` in the terminal, then run:

```bash
docker-compose down
```

## API Endpoints

### 1. Register Customer

**POST** `/register`

Register a new customer and calculate their approved credit limit.

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "age": 30,
  "monthly_income": "50000",
  "phone_number": "1234567890"
}
```

**Response:**
```json
{
  "customer_id": 1,
  "name": "John Doe",
  "age": 30,
  "monthly_income": "50000.00",
  "approved_limit": "1800000",
  "phone_number": "1234567890"
}
```

### 2. Check Loan Eligibility

**POST** `/check-eligibility`

Check if a customer is eligible for a loan without creating it.

**Request Body:**
```json
{
  "customer_id": 1,
  "loan_amount": "100000",
  "interest_rate": "12",
  "tenure": 12
}
```

**Response:**
```json
{
  "customer_id": 1,
  "approval": true,
  "interest_rate": "12.00",
  "corrected_interest_rate": "12.01",
  "tenure": 12,
  "monthly_installment": "8885.35"
}
```

### 3. Create Loan

**POST** `/create-loan`

Create a new loan if the customer is eligible.

**Request Body:**
```json
{
  "customer_id": 1,
  "loan_amount": "100000",
  "interest_rate": "12",
  "tenure": 12
}
```

**Response:**
```json
{
  "loan_id": 1,
  "customer_id": 1,
  "loan_approved": true,
  "message": "Loan approved successfully",
  "monthly_installment": "8885.35"
}
```

### 4. View Loan Details

**GET** `/view-loan/<loan_id>`

Get details of a specific loan.

**Response:**
```json
{
  "loan_id": 1,
  "customer": {
    "id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "1234567890",
    "age": 30
  },
  "loan_amount": "100000.00",
  "interest_rate": "12.00",
  "monthly_installment": "8885.35",
  "tenure": 12
}
```

### 5. View Customer Loans

**GET** `/view-loans/<customer_id>`

Get all active loans for a customer.

**Response:**
```json
[
  {
    "loan_id": 1,
    "loan_amount": "100000.00",
    "interest_rate": "12.00",
    "monthly_installment": "8885.35",
    "repayments_left": 7
  }
]
```

## Credit Scoring System

The system calculates credit scores (0-100) based on:

1. Past loan repayment history (40 points)
2. Number of loans taken (20 points)
3. Loan activity in current year (15 points)
4. Loan approved volume vs limit (25 points)

### Credit Score Slabs

- **Score > 50**: Loan approved at requested interest rate
- **30 < Score ≤ 50**: Loan approved with interest rate > 12%
- **10 < Score ≤ 30**: Loan approved with interest rate > 16%
- **Score ≤ 10**: Loan rejected

### Additional Rules

- Total EMIs cannot exceed 50% of monthly salary
- Active loans cannot exceed approved credit limit
- If active loans exceed approved limit, credit score becomes 0

## EMI Calculation

Monthly installment is calculated using the compound interest formula:

```
EMI = P × r × (1+r)^n / ((1+r)^n − 1)

Where:
  P = Principal (loan amount)
  r = Monthly interest rate (annual_rate / 1200)
  n = Tenure in months
```

## Data Ingestion

The system supports bulk ingestion of customer and loan data from Excel files.

### Excel File Format

**customer_data.xlsx** should contain:
- customer_id
- first_name
- last_name
- phone_number
- monthly_salary
- approved_limit
- current_debt

**loan_data.xlsx** should contain:
- customer_id
- loan_id
- loan_amount
- tenure
- interest_rate
- monthly_repayment
- EMIs_paid_on_time
- start_date
- end_date

### Triggering Ingestion

Place Excel files in the parent directory and run:

```bash
docker-compose exec web python manage.py trigger_ingestion
```

## Testing

Run the test suite:

```bash
docker-compose exec web python manage.py test
```

The test suite includes 23 tests covering:
- EMI calculations
- Credit score calculations
- Loan eligibility evaluation
- API endpoints
- Edge cases and boundary conditions

## Project Structure

```
credit_system/
├── config/              # Django project configuration
│   ├── settings.py      # Application settings
│   ├── urls.py          # URL routing
│   ├── wsgi.py          # WSGI configuration
│   └── celery.py        # Celery configuration
├── core/                # Main application
│   ├── models.py        # Database models
│   ├── views.py         # API views
│   ├── serializers.py   # DRF serializers
│   ├── tasks.py         # Celery tasks
│   ├── tests.py         # Test suite
│   ├── services/        # Business logic
│   │   ├── credit_score_service.py
│   │   ├── eligibility_service.py
│   │   └── emi_service.py
│   ├── management/commands/
│   │   └── trigger_ingestion.py
│   └── migrations/      # Database migrations
├── docker-compose.yml   # Docker orchestration
├── Dockerfile           # Docker image definition
├── requirements.txt     # Python dependencies
└── .env                 # Environment variables
```

## Environment Variables

The application uses the following environment variables (configured in `.env`):

```
DJANGO_SECRET_KEY=dev-secret-key-change-in-production
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_DB=credit_db
POSTGRES_USER=credit_user
POSTGRES_PASSWORD=credit_pass
POSTGRES_HOST=db
POSTGRES_PORT=5432

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

DATA_DIR=/data
CUSTOMER_DATA_PATH=/data/customer_data.xlsx
LOAN_DATA_PATH=/data/loan_data.xlsx
```

## Architecture

The application follows a three-layer architecture:

1. **Views Layer** (`views.py`): Handles HTTP requests and responses
2. **Services Layer** (`services/`): Contains business logic and calculations
3. **Models Layer** (`models.py`): Defines database schema and data access

This separation ensures clean code organization and maintainability.

## Database Schema

### Customer
- id (Primary Key)
- first_name
- last_name
- age
- phone_number
- monthly_salary
- approved_limit
- current_debt

### Loan
- id (Primary Key)
- customer (Foreign Key)
- loan_amount
- tenure
- interest_rate
- monthly_installment
- emis_paid_on_time
- start_date
- end_date

## Development

For local development without Docker:

1. Set up a virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variable: `USE_SQLITE_FOR_TESTS=1`
4. Run migrations: `python manage.py migrate`
5. Start server: `python manage.py runserver`

## Notes

- All financial calculations use Decimal type for precision
- Monetary values in API responses are returned as strings to prevent precision loss
- Database migrations run automatically when containers start
- The system uses PostgreSQL in Docker and can use SQLite for local testing
