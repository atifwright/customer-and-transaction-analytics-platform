# Data dictionary

## Source files

| File | Grain | Required columns |
| --- | --- | --- |
| `data/customers.csv` | One row per customer | `customer_id`, `first_name`, `last_name`, `email`, `region`, `signup_date` |
| `data/transactions.csv` | One row per transaction | `transaction_id`, `customer_id`, `transaction_date`, `amount`, `channel`, `status` |
| `data/operations.csv` | One row per operational incident | `incident_id`, `transaction_id`, `incident_type`, `resolution_hours`, `status` |
| `data/third_party.csv` | At most one profile per customer | `customer_id`, `credit_score`, `risk_band`, `market_segment` |

Dates use `YYYY-MM-DD`. `amount` and `resolution_hours` must be numeric and
non-negative. `credit_score` must be between 0 and 850.

## Output models

| Model | Grain | Contents |
| --- | --- | --- |
| `stg_customers` | Customer | Validated customer source fields |
| `stg_transactions` | Transaction | Validated transaction source fields |
| `stg_operations` | Incident | Validated operational incident details |
| `stg_third_party` | Customer profile | Validated external attributes, where supplied |
| `customer_360` | Customer | Customer attributes, completed-order measures, recency, operational aggregates, and external profile |
| `transaction_daily` | Transaction date and channel | Transaction counts, completed revenue, and non-completed counts |
| `customer_segments` | Customer | Rule-based segment plus core spend and recency measures |
| `predictive_features` | Customer | Customer features joined to the current segment for downstream modeling |

### Customer metrics

- `transaction_count`: all source transactions, regardless of status.
- `total_spend`: sum of amounts for `completed` transactions only.
- `avg_order_value`: mean amount of `completed` transactions; zero when no
  completed transaction exists.
- `last_transaction_date`: latest `completed` transaction date.
- `days_since_last_transaction`: day difference from the batch's latest
  transaction date to the customer's last completed transaction; `NULL` when no
  completed transaction exists.
- `incident_count` and `avg_resolution_hours`: operational incident aggregates
  across the customer's transactions.
- `credit_score`, `risk_band`, `market_segment`: nullable third-party
  attributes.
- `segment`: `no_purchase`, `high_value`, `frequent`, `at_risk`, or `occasional`,
  determined by configurable rules and evaluation order in the architecture
  guide.
