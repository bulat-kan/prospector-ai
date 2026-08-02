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
