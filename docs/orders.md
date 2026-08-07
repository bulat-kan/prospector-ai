# Sales Orders

Prospector AI presents `Sale` records as Sales Orders and `SaleItem` records as
Order Items. The internal model names remain unchanged for database
compatibility.

## Sales Order Versus Opportunity

An Opportunity is pipeline intent: expected products, estimated quantities,
estimated MRR, stage, and next action. It is not commissionable.

A Sales Order is what the customer actually agreed to purchase: actual ordered
products, ordered quantities, and actual incremental MRR. An order may originate
from an Opportunity, but ordered items can differ from Opportunity estimates.
Creating an order does not automatically change the Opportunity stage.

One Opportunity can have zero, one, or many orders.

## Sales Order Versus Fulfillment

This foundation does not track installation, mobile activation, or item-level
fulfillment. Future fulfillment work will determine when fixed services become
installed and when Mobile becomes activated.

Order statuses are:

- `DRAFT`: Order is being prepared and has not been submitted.
- `SUBMITTED`: Order has been placed.
- `SCHEDULED`: At least one future fulfillment appointment is scheduled.
- `PARTIALLY_FULFILLED`: Future-compatible status for mixed fulfillment.
- `FULFILLED`: Future-compatible status for fully fulfilled orders.
- `CANCELED`: Order will not proceed.
- `INSTALLED`: Legacy status retained for existing demo sales and analytics.
- `DISCONNECTED`: Legacy status retained for historical compatibility.

`CANCELLED` is accepted as an input alias and normalized to `CANCELED`.

## Sales Order Versus Commission

Submitted orders are not commissionable merely because they exist. Closed Won
Opportunities also do not earn commission automatically.

Current monthly analytics still count only legacy `INSTALLED` Sale rows. This
preserves the existing July 2026 demo commission output. Future work will connect
item-level fulfillment to commission eligibility.

Commission cycles run from the 29th through the 28th. Any order-date cycle is
informational only; the eventual earned cycle will come from each item install or
activation date.

## Order Items

Order Items must reference an active Product, have quantity greater than zero,
and have nonnegative incremental MRR. Duplicate product rows in one order are
rejected rather than merged.

New writes prefer `incremental_mrr`. Existing `monthly_revenue` remains as a
legacy analytics fallback.

## Orders UI

The Streamlit Orders page is available from the custom sidebar navigation. It
supports:

- browsing orders by company, status, product, opportunity, date range, and
  external order number;
- opening a detail view without exposing internal database IDs;
- manually creating Draft, Submitted, Scheduled, or Canceled orders with one or
  more product rows;
- converting an Opportunity into an editable order draft using the
  OpportunityProduct rows as the preview source;
- editing order header fields and order items after creation;
- canceling open orders while preserving their historical item detail.

Legacy `INSTALLED` orders are displayed for compatibility with current analytics
and are read-only except for notes.
