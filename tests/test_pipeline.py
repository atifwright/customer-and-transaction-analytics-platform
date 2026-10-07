import csv
import sqlite3
from pathlib import Path

import pytest

from customer_analytics.pipeline import DataQualityError, InputFiles, build_analytics

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DATA = PROJECT_ROOT / "data"


def sample_inputs() -> InputFiles:
    return InputFiles(
        customers=SAMPLE_DATA / "customers.csv",
        transactions=SAMPLE_DATA / "transactions.csv",
        operations=SAMPLE_DATA / "operations.csv",
        third_party=SAMPLE_DATA / "third_party.csv",
    )


def test_builds_integrated_analytics_models(tmp_path: Path) -> None:
    output = tmp_path / "analytics.sqlite"
    counts = build_analytics(sample_inputs(), output)

    assert counts == {
        "stg_customers": 5,
        "stg_transactions": 9,
        "stg_operations": 4,
        "stg_third_party": 5,
        "customer_360": 5,
        "transaction_daily": 9,
        "customer_segments": 5,
        "predictive_features": 5,
    }
    with sqlite3.connect(output) as connection:
        customer = connection.execute(
            """SELECT transaction_count, total_spend, incident_count, credit_score, segment
               FROM predictive_features WHERE customer_id = 'C001'"""
        ).fetchone()
        assert customer == (3, 1295.5, 1, 742.0, "high_value")
        refunded = connection.execute(
            "SELECT total_spend FROM customer_360 WHERE customer_id = 'C003'"
        ).fetchone()
        assert refunded == (210.0,)
        no_purchase = connection.execute(
            "SELECT segment FROM customer_segments WHERE customer_id = 'C005'"
        ).fetchone()
        assert no_purchase == ("occasional",)


def test_rejects_transaction_with_unknown_customer(tmp_path: Path) -> None:
    transactions = tmp_path / "transactions.csv"
    with (SAMPLE_DATA / "transactions.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows[0]["customer_id"] = "UNKNOWN"
    with transactions.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    files = InputFiles(
        customers=sample_inputs().customers,
        transactions=transactions,
        operations=sample_inputs().operations,
        third_party=sample_inputs().third_party,
    )
    with pytest.raises(DataQualityError, match="unknown customer_id UNKNOWN"):
        build_analytics(files, tmp_path / "analytics.sqlite")


def test_rejects_duplicate_transactions(tmp_path: Path) -> None:
    transactions = tmp_path / "transactions.csv"
    with (SAMPLE_DATA / "transactions.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows.append(rows[0])
    with transactions.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    files = InputFiles(
        customers=sample_inputs().customers,
        transactions=transactions,
        operations=sample_inputs().operations,
        third_party=sample_inputs().third_party,
    )
    with pytest.raises(DataQualityError, match="duplicate transaction_id T001"):
        build_analytics(files, tmp_path / "analytics.sqlite")


def test_rejects_invalid_segmentation_threshold(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="frequent_transactions"):
        build_analytics(sample_inputs(), tmp_path / "analytics.sqlite", frequent_transactions=0)
