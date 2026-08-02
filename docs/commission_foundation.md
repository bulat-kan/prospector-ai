# Commission Foundation

This document records the current commission foundation rules for future
Opportunities, Sales, and commission-engine work.

## Commission Cycle

Commission cycles run from the 29th through the 28th of the following month.

Examples:

- July 15, 2026 belongs to June 29, 2026 through July 28, 2026.
- July 30, 2026 belongs to July 29, 2026 through August 28, 2026.

Use `app.commission_cycle` for cycle calculation and display formatting.

## Commission Eligibility

Closed Won does not automatically earn commission.

Fixed services become commission eligible when installed. This applies to:

- Internet
- Voice
- TV
- Managed WiFi
- Security
- Seasonal Sports

Mobile becomes commission eligible when activated.

## Shared Statuses

Commission status constants live in `app.constants`:

- Pending Fulfillment
- Commission Eligible
- Commission Paid

Fulfillment status constants live in `app.constants`:

- Pending
- Installed
- Activated
- Cancelled

## Product Catalog

The shared product catalog constants live in `app.constants`:

- Internet
- Mobile
- Voice
- TV
- Seasonal Sports
- EverPass
- Managed WiFi
- Security
- Other

This is a shared constant list only. It is not a new database table.

## Seasonal Sports

Seasonal Sports contributes MRR.

Seasonal Sports commission depends on a minimum of five qualifying installed
HSD sales in the same commission cycle. Threshold logic is documented here for
future commission-engine work but is not implemented in this sprint.
