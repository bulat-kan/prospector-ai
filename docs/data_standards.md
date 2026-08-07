# Prospector AI Data Standards

This document defines the shared data-entry rules for Prospector AI. UI pages,
CRUD functions, scripts, imports, and future APIs must reuse `app.constants` for
controlled values and `app.validation` for normalization, validation, and display
helpers.

## Phone

- Optional unless a workflow explicitly requires it.
- When supplied, phone values must contain exactly 10 digits.
- Stored values use digits only.
- Display values use `(222) 111-1111` formatting via `format_phone_display`.

## Email

- Optional unless a workflow explicitly requires it.
- When supplied, values must match a valid email shape such as
  `name@company.com`.
- Values are trimmed and stored lowercase.

## Names

- Person names are trimmed and repeated spaces are collapsed.
- Common capitalization is normalized.
- Apostrophes and hyphens are preserved, such as `O'Connor` and `Smith-Jones`.
- Contacts require at least a first name or last name.
- Referral partners require at least one identity value: first name, last name,
  organization, phone, or email.

## Website

- Optional unless a workflow explicitly requires it.
- Bare domains are normalized to `https://`.
- Invalid domains, email-shaped input, and whitespace are rejected.

## ZIP

- ZIP codes must contain exactly 5 digits.
- Stored values use digits only.

## State

- States must be valid USPS abbreviations from `US_STATES`.
- Stored values use uppercase two-letter abbreviations.

## City

- City values are required for locations.
- Values are trimmed, repeated spaces are collapsed, and common capitalization is
  normalized.
- `land o lakes` is normalized to `Land O' Lakes`.

## Location Label

- A provided label is preserved after trimming.
- Blank labels generate `{City} Office`.
- If no valid city is available, the fallback is `Main Office`.

## Decision Role

- Decision roles come from `ContactRole`.
- Current options are Unknown, Decision Maker, Influencer, and Gatekeeper.
- Decision Role is independent from Primary Contact.

## Lead Source

- Lead sources come from `LEAD_SOURCES`.
- Current values are `AE_FOUND` and `REFERRAL`.
- Referral companies require a referral partner.

## Location Type

- Location type options come from `LOCATION_TYPES`.
- Current MVP entry options are SMB, SOHO, and B&R.

## Industry

- Industry options come from `INDUSTRIES`.
- `Other` requires a custom industry value.

## Referral Partners

- Phone and email use the same shared validators as company/contact data.
- Phone is optional, but supplied values must be stored as 10 digits.
- Email is optional, but supplied values must be valid and stored lowercase.
- Source metadata requires `source_system` and `external_id` together.
- CRUD operations roll back on validation failure and must not partially save
  referral partners or companies.

## Opportunities

- Opportunity stages come from `OPPORTUNITY_STAGES`.
- Legacy stages are normalized by the opportunity service and `init_db`:
  `CONTACT_ATTEMPTED`, `APPOINTMENT`, `QUOTE`, `WON`, `LOST`, and `RESEARCHING`
  map to the current standard stages.
- Open opportunities require a next action and next action date.
- Closed Lost requires a lost reason.
- Closed Won is not commissionable; future Sales/SaleItems determine commission
  eligibility.
- New opportunities require an active company. Provided locations and primary
  contacts must belong to the company and be active.
- Product detail belongs in `OpportunityProduct` rows backed by the Product
  catalog. Legacy opportunity estimate fields remain compatibility summaries.

## Sales Orders

- The app presents `Sale` as Sales Order and `SaleItem` as Order Item.
- Orders may optionally originate from an Opportunity, but actual ordered
  products, quantities, and incremental MRR may differ from Opportunity
  estimates.
- New orders require an active company. Provided locations and contacts must
  belong to the company and be active.
- Company and Opportunity source links are fixed after order creation in this
  MVP.
- Order items require an active Product, quantity greater than zero, and
  nonnegative incremental MRR.
- Duplicate product rows on the same order are rejected.
- Submitted, Draft, and Scheduled orders are not commissionable. Current
  analytics continue to count only legacy `INSTALLED` rows until fulfillment
  work is integrated.
