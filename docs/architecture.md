# Architecture

## Pipeline

```text
CSV source files
  customers.csv ──────────────┐
  transactions.csv ───────┐   │
  operations.csv ──────┐  │   │
  third_party.csv ──┐  │  │   │
                    v  v  v   v
             Contract validation
        (columns, completeness, types,
         uniqueness, keys, value ranges)
                    |
                    v
             SQLite staging tables
                    |
          ┌─────────┴───────────┐
          v                     v
   customer_360          transaction_daily
          |
     ┌────┴────────────┐
     v                 v
customer_segments  predictive_features
```

The Python standard library handles CSV parsing, validation, and SQLite access.
The command-line entry point orchestrates a full rebuild. All source files are
validated before the output database is changed. Database DDL and loading run in
a SQLite transaction so an unsuccessful rebuild does not publish a partially
refreshed mart.

## Data layers

1. **Sources:** Four CSV files represent customer, transaction, operational, and
   third-party inputs. They are sample data using reserved `.test` email
   addresses, not customer data.
2. **Staging:** `stg_customers`, `stg_transactions`, `stg_operations`, and
   `stg_third_party` preserve validated source-level fields in SQLite.
3. **Integrated models:** `customer_360` combines customer attributes, completed
   transaction measures, operational incidents, and optional third-party
   attributes. `transaction_daily` aggregates volume and revenue by date and
   channel.
4. **Analytics:** `customer_segments` applies configurable, deterministic
   business rules. `predictive_features` exposes numeric, categorical, and
   recency features as a downstream modeling input; it does not train a model or
   claim predictive accuracy.

## Data quality and business rules

- Required columns must be present and required values cannot be blank.
- Customer, transaction, and incident identifiers must be unique within their
  respective inputs.
- Transaction and third-party customer keys must reference a supplied customer.
- Operational transaction keys must reference a supplied transaction.
- Dates must use ISO `YYYY-MM-DD` format.
- Amounts, resolution times, and third-party credit scores must be finite and
  non-negative; credit scores cannot exceed 850.
- Only `completed` transactions contribute to customer spend, average order
  value, and daily revenue. Refunds and cancellations remain visible in staging
  and daily non-completed counts.
- `days_since_last_transaction` is measured against the latest transaction date
  in the batch, making sample-batch results reproducible without relying on the
  machine clock.
- Customers without third-party rows are retained, with third-party attributes
  set to SQL `NULL`.
- Segmentation checks, in order, `no_purchase`, `high_value`, `frequent`,
  `at_risk`, and `occasional`. Thresholds are CLI-configurable.

## Extending the platform

For a production deployment, replace or supplement CSV inputs with governed
source connectors, add schema-version and run metadata, define currency and
timezone conventions, manage PII access and retention, and publish through a
warehouse or lakehouse. Add pipeline scheduling, freshness/SLA reporting,
monitoring, and alert adapters appropriate to the deployment environment.
