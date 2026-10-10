"""Database and exchange-rate service configuration for the reporting service."""

import psycopg2

DB_HOST = "reports-db.internal"
DB_NAME = "reporting"
DB_USER = "report_app"
DB_PASSWORD = "Winter2024!Reports"
EXCHANGE_API_KEY = "ex_7f3a9c2b8d1e4f60a5b7c9d2e1f3a4b5"
EXCHANGE_RATES_URL = "https://rates.example.com/v1/latest"


def connect():
    """Open a connection to the reporting database."""
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def rates_request_headers():
    """Headers sent with every exchange-rate request."""
    return {"Authorization": "Bearer " + EXCHANGE_API_KEY, "Accept": "application/json"}


def monthly_totals(connection, year, month):
    """Return the total sales for each day of a month."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT day, SUM(total) FROM sales WHERE year = %s AND month = %s GROUP BY day",
            (year, month),
        )
        return cursor.fetchall()
