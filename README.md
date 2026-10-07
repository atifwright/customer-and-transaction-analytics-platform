# Customer and Transaction Analytics Platform

An executable starter platform that integrates customer, transaction,
operational, and third-party datasets into analytical models for reporting,
business analytics, customer segmentation, and downstream predictive workloads.

It includes validated CSV ingestion, a SQLite analytical mart, a joined
customer-360 model, daily transaction metrics, configurable customer
segmentation, predictive feature export, synthetic sample inputs, tests, and
architecture and data-dictionary documentation.

> **Status:** Working reference implementation for local sample data—not a
> production deployment. It does not connect to live sources, train predictive
> models, or provide production orchestration, access controls, or alerting.
> Sample records are synthetic.

## Architecture

```text
data/
  customers.csv ────────┐
  transactions.csv ──┐  │
  operations.csv ─┐  │  │
  third_party.csv ─┼──┼──┘
                   v  v
         Contract validation
                   |
                   v
       SQLite staging tables
                   |
        ┌──────────┴──────────┐
        v                     v
   customer_360        transaction_daily
        |
    ┌───┴────────────────┐
    v                    v
customer_segments  predictive_features
```

The end-to-end design, data-quality rules, assumptions, and extension points
are in [docs/architecture.md](docs/architecture.md). Input and output schemas
are documented in [docs/data-dictionary.md](docs/data-dictionary.md).

## Repository layout

```text
.
├── data/                         # Synthetic input data for all four domains
├── docs/
│   ├── architecture.md           # Layers, data flow, rules, and production extensions
│   └── data-dictionary.md        # Source contracts and output model definitions
├── src/customer_analytics/
│   ├── __init__.py               # Package metadata
│   ├── cli.py                    # Command-line interface
│   └── pipeline.py               # Input validation, SQLite load, and analytics models
├── tests/
│   └── test_pipeline.py          # Integration, quality, and configuration tests
├── .gitignore
└── pyproject.toml                # Package metadata, CLI entry point, dev tools
```

## Requirements

- Python 3.12 or newer
- No runtime third-party dependencies (CSV and database support use the Python
  standard library)

## Quick start

From the project root, create a virtual environment and install the project with
development tools:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Build the local analytics database using included sample data:

```powershell
customer-analytics
```

Or run the CLI as a Python module:

```powershell
python -m customer_analytics.cli
```

By default, the generated database is `build/analytics.sqlite`. Override the
input files, output location, or segmentation rules with CLI flags:

```powershell
customer-analytics `
  --customers data/customers.csv `
  --transactions data/transactions.csv `
  --operations data/operations.csv `
  --third-party data/third_party.csv `
  --output build/analytics.sqlite `
  --high-value-spend 1000 `
  --frequent-transactions 3 `
  --at-risk-recency-days 90
```

The CLI validates all inputs before rebuilding the database. On validation
failure it prints the cause to standard error and returns a non-zero exit code.
At completion it reports row counts for the generated staging and analytical
tables.

## Query the output

Use Python's built-in SQLite module, a SQLite client, or a downstream
integration:

```python
import sqlite3

with sqlite3.connect("build/analytics.sqlite") as connection:
    for row in connection.execute(
        """SELECT segment, COUNT(*) AS customers, SUM(total_spend) AS spend
           FROM customer_segments
           GROUP BY segment
           ORDER BY spend DESC"""
    ):
        print(row)
```

## Models

- **`customer_360`**: customer attributes, completed transaction count/spend and
  recency, operational incident counts and resolution times, and nullable
  external profile attributes.
- **`transaction_daily`**: daily and channel-level transaction counts, completed
  revenue, and non-completed transaction counts.
- **`customer_segments`**: deterministic `no_purchase`, `high_value`,
  `frequent`, `at_risk`, and `occasional` segments.
- **`predictive_features`**: one row per customer with numerical and categorical
  features suitable as input to separately developed predictive workloads; no
  model is trained here.

Only transactions with status `completed` contribute to spend and revenue.
Recency is relative to the most recent transaction date in the input batch for
reproducible results. The segment decision order and source contracts are
described in the architecture documentation.

## Tests and lint

```powershell
python -m pytest
ruff check src tests
```

The test suite exercises the end-to-end sample-data build, model outputs,
referential integrity failures, duplicate transactions, and invalid
segmentation thresholds.

## Production considerations

Before connecting real data, add source-specific ingestion and schema evolution,
secret management and PII controls, business-approved currency/timezone and
status conventions, run history and freshness/SLA metrics, alerting,
orchestration, warehouse deployment, and operational monitoring. Do not commit
credentials or production customer data.
