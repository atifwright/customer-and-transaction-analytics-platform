"""Validated CSV ingestion and SQLite customer analytics mart construction."""

from __future__ import annotations

import csv
import math
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class DataQualityError(ValueError):
    """Raised when source data violates the input contract."""


@dataclass(frozen=True)
class InputFiles:
    customers: Path
    transactions: Path
    operations: Path
    third_party: Path


CUSTOMER_FIELDS = ("customer_id", "first_name", "last_name", "email", "region", "signup_date")
TRANSACTION_FIELDS = (
    "transaction_id",
    "customer_id",
    "transaction_date",
    "amount",
    "channel",
    "status",
)
OPERATION_FIELDS = ("incident_id", "transaction_id", "incident_type", "resolution_hours", "status")
THIRD_PARTY_FIELDS = ("customer_id", "credit_score", "risk_band", "market_segment")


def _read_csv(path: Path, required_fields: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise DataQualityError(f"{path}: CSV is empty or has no header.")
            missing = sorted(set(required_fields) - set(reader.fieldnames))
            if missing:
                raise DataQualityError(f"{path}: missing required columns: {', '.join(missing)}.")
            rows = []
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    raise DataQualityError(
                        f"{path}:{line_number}: more values than header columns."
                    )
                rows.append({key: (value or "").strip() for key, value in row.items() if key})
            return rows
    except OSError as exc:
        raise DataQualityError(f"Unable to read {path}: {exc}") from exc


def _required(row: dict[str, str], field: str, source: str, row_number: int) -> str:
    value = row.get(field, "")
    if not value:
        raise DataQualityError(f"{source} row {row_number}: {field} must not be blank.")
    return value


def _date_value(value: str, source: str, row_number: int, field: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise DataQualityError(
            f"{source} row {row_number}: {field} must be an ISO date (YYYY-MM-DD)."
        ) from exc


def _number_value(
    value: str, source: str, row_number: int, field: str, *, minimum: float = 0
) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise DataQualityError(f"{source} row {row_number}: {field} must be numeric.") from exc
    if not math.isfinite(number) or number < minimum:
        raise DataQualityError(f"{source} row {row_number}: {field} must be at least {minimum}.")
    return number


def _validate_inputs(
    files: InputFiles,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    customers = _read_csv(files.customers, CUSTOMER_FIELDS)
    transactions = _read_csv(files.transactions, TRANSACTION_FIELDS)
    operations = _read_csv(files.operations, OPERATION_FIELDS)
    third_party = _read_csv(files.third_party, THIRD_PARTY_FIELDS)
    if not customers:
        raise DataQualityError("Customers input must contain at least one record.")
    if not transactions:
        raise DataQualityError("Transactions input must contain at least one record.")

    customer_ids: set[str] = set()
    for index, row in enumerate(customers, start=2):
        customer_id = _required(row, "customer_id", "customers", index)
        if customer_id in customer_ids:
            raise DataQualityError(f"customers row {index}: duplicate customer_id {customer_id}.")
        customer_ids.add(customer_id)
        for field in CUSTOMER_FIELDS[1:]:
            _required(row, field, "customers", index)
        row["signup_date"] = _date_value(row["signup_date"], "customers", index, "signup_date")

    transaction_ids: set[str] = set()
    for index, row in enumerate(transactions, start=2):
        transaction_id = _required(row, "transaction_id", "transactions", index)
        if transaction_id in transaction_ids:
            raise DataQualityError(
                f"transactions row {index}: duplicate transaction_id {transaction_id}."
            )
        transaction_ids.add(transaction_id)
        customer_id = _required(row, "customer_id", "transactions", index)
        if customer_id not in customer_ids:
            raise DataQualityError(f"transactions row {index}: unknown customer_id {customer_id}.")
        row["transaction_date"] = _date_value(
            _required(row, "transaction_date", "transactions", index),
            "transactions",
            index,
            "transaction_date",
        )
        row["amount"] = str(
            _number_value(
                _required(row, "amount", "transactions", index),
                "transactions",
                index,
                "amount",
            )
        )
        for field in ("channel", "status"):
            _required(row, field, "transactions", index)

    incident_ids: set[str] = set()
    for index, row in enumerate(operations, start=2):
        incident_id = _required(row, "incident_id", "operations", index)
        if incident_id in incident_ids:
            raise DataQualityError(f"operations row {index}: duplicate incident_id {incident_id}.")
        incident_ids.add(incident_id)
        transaction_id = _required(row, "transaction_id", "operations", index)
        if transaction_id not in transaction_ids:
            raise DataQualityError(
                f"operations row {index}: unknown transaction_id {transaction_id}."
            )
        _required(row, "incident_type", "operations", index)
        _required(row, "status", "operations", index)
        row["resolution_hours"] = str(
            _number_value(
                _required(row, "resolution_hours", "operations", index),
                "operations",
                index,
                "resolution_hours",
            )
        )

    third_party_ids: set[str] = set()
    for index, row in enumerate(third_party, start=2):
        customer_id = _required(row, "customer_id", "third_party", index)
        if customer_id not in customer_ids:
            raise DataQualityError(f"third_party row {index}: unknown customer_id {customer_id}.")
        if customer_id in third_party_ids:
            raise DataQualityError(f"third_party row {index}: duplicate customer_id {customer_id}.")
        third_party_ids.add(customer_id)
        row["credit_score"] = str(
            _number_value(
                _required(row, "credit_score", "third_party", index),
                "third_party",
                index,
                "credit_score",
                minimum=0,
            )
        )
        if float(row["credit_score"]) > 850:
            raise DataQualityError(f"third_party row {index}: credit_score must not exceed 850.")
        for field in ("risk_band", "market_segment"):
            _required(row, field, "third_party", index)

    return customers, transactions, operations, third_party


def build_analytics(
    files: InputFiles,
    output: Path,
    *,
    high_value_spend: float = 1000,
    frequent_transactions: int = 3,
    at_risk_recency_days: int = 90,
) -> dict[str, int]:
    """Validate source CSVs and atomically rebuild the analytical SQLite database."""
    if not math.isfinite(high_value_spend) or high_value_spend < 0:
        raise ValueError("high_value_spend must be a finite, non-negative number.")
    if frequent_transactions < 1:
        raise ValueError("frequent_transactions must be at least 1.")
    if at_risk_recency_days < 0:
        raise ValueError("at_risk_recency_days must not be negative.")

    customers, transactions, operations, third_party = _validate_inputs(files)
    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output) as connection:
        connection.execute("BEGIN")
        for statement in (
            "DROP TABLE IF EXISTS predictive_features",
            "DROP TABLE IF EXISTS customer_segments",
            "DROP TABLE IF EXISTS transaction_daily",
            "DROP TABLE IF EXISTS customer_360",
            "DROP TABLE IF EXISTS stg_operations",
            "DROP TABLE IF EXISTS stg_third_party",
            "DROP TABLE IF EXISTS stg_transactions",
            "DROP TABLE IF EXISTS stg_customers",
            """
            CREATE TABLE stg_customers (
                customer_id TEXT PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
                email TEXT NOT NULL, region TEXT NOT NULL, signup_date TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE stg_transactions (
                transaction_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
                transaction_date TEXT NOT NULL, amount REAL NOT NULL, channel TEXT NOT NULL,
                status TEXT NOT NULL, FOREIGN KEY (customer_id) REFERENCES stg_customers(customer_id)
            )
            """,
            """
            CREATE TABLE stg_operations (
                incident_id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL,
                incident_type TEXT NOT NULL, resolution_hours REAL NOT NULL, status TEXT NOT NULL,
                FOREIGN KEY (transaction_id) REFERENCES stg_transactions(transaction_id)
            )
            """,
            """
            CREATE TABLE stg_third_party (
                customer_id TEXT PRIMARY KEY, credit_score REAL NOT NULL,
                risk_band TEXT NOT NULL, market_segment TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES stg_customers(customer_id)
            )
            """,
        ):
            if statement.strip():
                connection.execute(statement)
        connection.executemany(
            "INSERT INTO stg_customers VALUES (:customer_id, :first_name, :last_name, :email, :region, :signup_date)",
            customers,
        )
        connection.executemany(
            "INSERT INTO stg_transactions VALUES (:transaction_id, :customer_id, :transaction_date, :amount, :channel, :status)",
            transactions,
        )
        connection.executemany(
            "INSERT INTO stg_operations VALUES (:incident_id, :transaction_id, :incident_type, :resolution_hours, :status)",
            operations,
        )
        connection.executemany(
            "INSERT INTO stg_third_party VALUES (:customer_id, :credit_score, :risk_band, :market_segment)",
            third_party,
        )
        connection.execute(
            """
            CREATE TABLE customer_360 AS
            WITH transaction_summary AS (
                SELECT customer_id, COUNT(*) AS transaction_count,
                       SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) AS total_spend,
                       AVG(CASE WHEN status = 'completed' THEN amount END) AS avg_order_value,
                       MAX(CASE WHEN status = 'completed' THEN transaction_date END)
                           AS last_transaction_date
                FROM stg_transactions GROUP BY customer_id
            ),
            operations_summary AS (
                SELECT t.customer_id, COUNT(o.incident_id) AS incident_count,
                       AVG(o.resolution_hours) AS avg_resolution_hours
                FROM stg_transactions t
                LEFT JOIN stg_operations o ON o.transaction_id = t.transaction_id
                GROUP BY t.customer_id
            )
            SELECT c.customer_id, c.first_name, c.last_name, c.email, c.region, c.signup_date,
                   COALESCE(ts.transaction_count, 0) AS transaction_count,
                   COALESCE(ts.total_spend, 0.0) AS total_spend,
                   COALESCE(ts.avg_order_value, 0.0) AS avg_order_value,
                   ts.last_transaction_date,
                   CASE WHEN ts.last_transaction_date IS NULL THEN NULL
                        ELSE CAST(julianday((SELECT MAX(transaction_date) FROM stg_transactions))
                                  - julianday(ts.last_transaction_date) AS INTEGER)
                   END AS days_since_last_transaction,
                   COALESCE(os.incident_count, 0) AS incident_count,
                   COALESCE(os.avg_resolution_hours, 0.0) AS avg_resolution_hours,
                   tp.credit_score, tp.risk_band, tp.market_segment
            FROM stg_customers c
            LEFT JOIN transaction_summary ts ON ts.customer_id = c.customer_id
            LEFT JOIN operations_summary os ON os.customer_id = c.customer_id
            LEFT JOIN stg_third_party tp ON tp.customer_id = c.customer_id
            """
        )
        connection.execute(
            """
            CREATE TABLE transaction_daily AS
            SELECT transaction_date, channel, COUNT(*) AS transaction_count,
                   SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) AS gross_revenue,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
                   SUM(CASE WHEN status != 'completed' THEN 1 ELSE 0 END) AS non_completed_count
            FROM stg_transactions GROUP BY transaction_date, channel;
            """
        )
        connection.execute(
            """
            CREATE TABLE customer_segments AS
            SELECT customer_id,
                   CASE
                       WHEN transaction_count = 0 THEN 'no_purchase'
                       WHEN total_spend >= ? THEN 'high_value'
                       WHEN transaction_count >= ? THEN 'frequent'
                       WHEN days_since_last_transaction >= ? THEN 'at_risk'
                       ELSE 'occasional'
                   END AS segment,
                   transaction_count, total_spend, days_since_last_transaction
            FROM customer_360
            """,
            (high_value_spend, frequent_transactions, at_risk_recency_days),
        )
        connection.execute(
            """
            CREATE TABLE predictive_features AS
            SELECT c.customer_id, c.region, c.signup_date, c.transaction_count,
                   c.total_spend, c.avg_order_value, c.days_since_last_transaction,
                   c.incident_count, c.avg_resolution_hours, c.credit_score, c.risk_band,
                   c.market_segment, s.segment
            FROM customer_360 c
            JOIN customer_segments s USING (customer_id);
            """
        )
        connection.execute(
            "CREATE INDEX idx_transactions_customer ON stg_transactions(customer_id)"
        )
        connection.execute(
            "CREATE INDEX idx_transactions_date ON stg_transactions(transaction_date)"
        )
        connection.execute(
            "CREATE INDEX idx_customer_segments_segment ON customer_segments(segment)"
        )
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "stg_customers",
                "stg_transactions",
                "stg_operations",
                "stg_third_party",
                "customer_360",
                "transaction_daily",
                "customer_segments",
                "predictive_features",
            )
        }
    return counts
