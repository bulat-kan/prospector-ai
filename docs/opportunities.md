# Opportunities

An Opportunity represents a potential agreement or account expansion before it
becomes an actual Sale. It is used for pipeline tracking, follow-up discipline,
estimated product interest, and future conversion workflows.

## Opportunity Versus Sale

Closed Won means the agreement was secured. It is not commissionable by itself.
Commission begins only after future Sale and SaleItem fulfillment rules mark
products as installed or activated.

This sprint does not auto-create Sales from Opportunities.

## Stages

Current standard stages:

- New
- Attempting Contact
- Connected
- Qualified
- Appointment Set
- Needs Analysis
- Proposal Sent
- Negotiation
- Pending Install
- Closed Won
- Closed Lost

Legacy stage mappings are normalized when `python -m app.init_db` runs:

- `CONTACT_ATTEMPTED` -> `ATTEMPTING_CONTACT`
- `APPOINTMENT` -> `APPOINTMENT_SET`
- `QUOTE` -> `PROPOSAL_SENT`
- `WON` -> `CLOSED_WON`
- `LOST` -> `CLOSED_LOST`
- `RESEARCHING` -> `NEW`

## Open And Closed Rules

Open stages require both `next_action` and `next_action_date` through the
opportunity service layer.

Closed Won allows no next action. Closed Lost allows no next action but requires
`lost_reason`.

Archive status is separate from stage. Open and closed opportunities can remain
active. Archiving hides an opportunity by default while preserving history.

## Product Rows

`OpportunityProduct` is the detailed future source of truth for estimated
products. It links to the Product catalog, stores a stable `product_code`, and
captures estimated quantity and estimated incremental MRR.

The legacy Opportunity summary fields, such as `primary_product`,
`estimated_mobile_lines`, and `estimated_mrr`, remain for compatibility. New
backend code should prefer OpportunityProduct rows for product detail.

Duplicate product rows on the same opportunity are rejected by product code.

## Relationship Rules

New opportunities require an active company. If selected, location and primary
contact must belong to that company and must be active for new creation.

Existing opportunities may preserve inactive company, location, or contact links
historically. A contact assigned to one location may still be the primary contact
for an opportunity at another location within the same company.

## Future Conversion

Future work can convert a Closed Won opportunity into Sales and SaleItems, but
that conversion is intentionally deferred.

## UI Workflow

The Opportunities page has three sections:

- Browse opportunities
- Add opportunity
- Opportunity detail

Browse supports search, company, stage, product, follow-up status, archived
visibility, expected close date range, and minimum priority score filters. The
display uses friendly labels and hides raw database IDs.

Follow-up labels use the current local date:

- Overdue
- Due today
- Due this week
- Future
- No follow-up date

Closed opportunities are not treated as overdue.

## Add And Edit Forms

The Add Opportunity form stores only scalar values in Streamlit session state.
Validation failures preserve company, location, contact, dates, scores, notes,
and unsaved product rows. The form resets only after successful creation.

Company is read-only in the edit workflow for this version. Location and primary
contact can be changed within the same company.

## Product Editor

New opportunities require at least one product in the UI. Product options come
from active Product catalog rows.

The detail product editor supports adding, updating, and removing product rows.
Duplicate products are rejected and are not silently merged. Product removal
requires confirmation.

## Closed Won Warning

The UI displays this warning for Closed Won opportunities:

Agreement secured. Commission is not earned until qualifying services are
installed or mobile lines are activated.

Closed Won does not create a Sale automatically and does not change dashboard
commission output.
