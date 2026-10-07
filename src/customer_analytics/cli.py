"""Command-line interface for building the analytics database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from customer_analytics.pipeline import DataQualityError, InputFiles, build_analytics


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate customer data and build the customer analytics SQLite mart."
    )
    parser.add_argument("--customers", type=Path, default=Path("data/customers.csv"))
    parser.add_argument("--transactions", type=Path, default=Path("data/transactions.csv"))
    parser.add_argument("--operations", type=Path, default=Path("data/operations.csv"))
    parser.add_argument("--third-party", type=Path, default=Path("data/third_party.csv"))
    parser.add_argument("--output", type=Path, default=Path("build/analytics.sqlite"))
    parser.add_argument("--high-value-spend", type=float, default=1000)
    parser.add_argument("--frequent-transactions", type=int, default=3)
    parser.add_argument("--at-risk-recency-days", type=int, default=90)
    return parser


def main() -> int:
    args = _parser().parse_args()
    files = InputFiles(
        customers=args.customers,
        transactions=args.transactions,
        operations=args.operations,
        third_party=args.third_party,
    )
    try:
        counts = build_analytics(
            files,
            args.output,
            high_value_spend=args.high_value_spend,
            frequent_transactions=args.frequent_transactions,
            at_risk_recency_days=args.at_risk_recency_days,
        )
    except (DataQualityError, ValueError) as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    print(f"Analytics database created at {args.output}")
    for table, count in counts.items():
        print(f"  {table}: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
