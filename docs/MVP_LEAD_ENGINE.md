# Prospector AI — MVP Lead Engine

**Status:** Approved Foundation\
**Purpose:** Define how Prospector AI acquires, classifies, stores,
prioritizes, replenishes, and selects prospects for daily Missions.

> **Prospect Pool = inventory. Mission = today's selected work.**

> **Lead Supply ≠ Prospecting Execution.**

> **Salesforce = corporate system of record. Prospector AI = prospecting
> execution, lead intelligence, follow-up, planning, and coaching.**

Prospector AI should not depend on an unavailable Salesforce bulk
existing-customer export with services and contact-person information.

## Lead Sources

MVP lead sources:

1. **Salesforce Territory Address Import**\
   Address/location lists available to the AE for assigned physical prospecting
   territory. This primarily feeds the physical visit pool.

2. **Researched Public-Business Lead Import**\
   Clean CSV created from publicly available business information. It may
   include company name, public phone, public address, website, industry, and
   publicly listed contact when available.

3. **Manual Lead**\
   Business found while driving, networking, prospecting, or through other AE
   discovery.

4. **Referral Lead**\
   Introduction from a customer, referral partner, contact, networking source,
   or other relationship source.

5. **Prior Field Discovery**\
   A business first discovered through a visit may later become call-eligible
   if useful phone, contact, or decision-maker information is learned.

6. **Existing Prospect / Follow-Up**\
   Existing prospects re-enter work queues when their next action becomes due.

## Where Import Lives

CSV importing belongs under **Prospects**, not Mission.

Mission is for execution. Prospects manages lead supply and inventory.

Suggested mobile navigation remains:

- Mission
- Activity
- Voice / central Log action
- Prospects
- Coach

Inside Prospects, include **Import Leads**.

Initial import modes:

- Territory Addresses
- Researched Business Leads

Manual and Referral lead creation should also exist.

## Import Pipeline

``` text
CSV / Manual / Referral
        ↓
Validate
        ↓
Normalize
        ↓
Dedupe / match existing prospect
        ↓
Classify lead source
        ↓
Determine call eligibility
        ↓
Determine visit eligibility
        ↓
Prospect Pool
```

Imported rows do **not** automatically become tomorrow's Mission.

## Lead Source vs. Prospecting Mode

Lead Source and prospecting mode eligibility must be separate concepts.

Examples:

``` text
Lead Source:
Salesforce Territory Import

Call Eligible:
Yes / No

Visit Eligible:
Yes
```

``` text
Lead Source:
Public Business Research

Call Eligible:
Yes

Visit Eligible:
Depends on territory
```

``` text
Lead Source:
Referral

Call Eligible:
Yes

Visit Eligible:
Depends on territory
```

A prospect may be eligible for both Call and Visit.

## Call-Eligible Pool

Possible call candidates:

- due follow-ups where next action is Call;
- requested callbacks;
- referral leads;
- open or qualified prospects;
- researched public businesses with usable public phone/contact information;
- prospects discovered through prior visits;
- older prospects whose retry rules make them eligible again.

Physical door knocking is restricted to the AE's assigned territory.

Remote calling/email prospecting may cover eligible Spectrum service areas
beyond that physical territory, subject to applicable company rules.

## Visit-Eligible Pool

A prospect is physically visit-eligible only when:

- location is inside the AE's approved door-knocking territory;
- business is otherwise appropriate for a visit.

Visit ranking may consider:

- promised return visit;
- due or overdue follow-up;
- known decision-maker availability;
- business hours;
- prospect priority/potential;
- previous visit outcome;
- time since last attempt;
- location/proximity;
- route efficiency;
- appointment schedule;
- industry.

## Follow-Ups

Follow-ups originate from previous activities and explicit next actions.

Examples:

- Call
- Return Visit
- Email
- Text
- Send Quote
- Send Proposal
- Research Decision Maker
- Check Contract Timing
- Appointment

Due or overdue follow-ups normally outrank ordinary cold prospects.

Fixed appointments and explicitly promised callback/visit times are schedule
commitments, not just high-scoring suggestions.

## Daily Mission Selection

For MVP, use a deterministic and explainable planner.

AI is not required to rank every lead.

Conceptual pipeline:

``` text
ALL PROSPECT INVENTORY
        ↓
Eligibility filters
        ↓
Calendar / fixed commitments
        ↓
Pinned / time-constrained work
        ↓
Due / overdue follow-ups
        ↓
Score remaining candidates
        ↓
Rank
        ↓
Apply daily capacity
        ↓
Call Mission + Visit Mission
```

Calendar and scheduling constraints answer **when** work can happen. Lead Engine
rules answer **who** should be worked. See
[MVP_CALENDAR_AND_SCHEDULING.md](MVP_CALENDAR_AND_SCHEDULING.md).

## Manual Mission Pinning

Prospector AI recommends prospects for daily Missions, but the AE always retains
control.

The AE must be able to manually add or pin a specific prospect to tomorrow's
Mission with actions such as:

- Add to Tomorrow -> Call
- Add to Tomorrow -> Visit

This should be possible from:

1. Prospect Detail
2. Recommended Mission / Plan Tomorrow
3. Review Calls / Review Route where appropriate

A manually pinned prospect is a **user override**. It should not merely receive a
higher ranking score.

Conceptually:

``` text
Pinned / fixed work
        ↓
Planner reserves capacity
        ↓
Planner fills remaining capacity
        ↓
Final Mission
```

Examples:

- Daily Call Target = 30. AE manually pins 2 prospects. Planner selects 28
  additional call prospects. Final Call Mission = 30.
- Daily Visit Target = 15. AE manually pins 1 eligible visit. Planner selects 14
  additional visit prospects. Final Visit Mission = 15.

Manual pinning does **not** increase the daily activity target.

The AE may optionally attach useful context such as preferred time, priority, or
note/reason.

Example:

``` text
Owner usually arrives after 2 PM.
```

### Manual Call vs. Manual Visit

Manual Call and Manual Visit are not equivalent.

A manually pinned Call may be allowed anywhere the AE is permitted to remotely
prospect or sell, subject to company rules.

A manually pinned Visit must pass physical prospecting territory eligibility.
If a prospect is outside the AE's approved physical prospecting territory:

- do not allow it to be added as a physical Visit;
- explain why;
- where appropriate, offer Call as an alternative.

Example UX concept:

``` text
This prospect is outside your physical prospecting territory.

You can still add it to tomorrow's Call Mission if remote prospecting is
permitted.
```

Do not hard-code current cities into the product architecture. Territory must
eventually be configurable.

## Ranking Signals

Possible ranking signals:

Strong urgency:

- requested callback / return visit;
- overdue follow-up;
- follow-up due today;
- appointment.

Relationship / qualification:

- decision maker previously reached;
- meaningful prior conversation;
- qualified need;
- open opportunity;
- known contract/timing trigger;
- referral introduction.

Potential:

- mobile lines;
- employee count;
- multi-location business;
- product opportunity;
- vertical/business fit.

Retry / recency:

- time since last attempt;
- No Answer;
- Gatekeeper outcome;
- retry cooldown;
- never attempted.

Visit-specific:

- decision maker expected in time window;
- business open;
- distance;
- route cluster efficiency.

Do not lock final point values yet. Weights should be configurable and tuned
from actual usage.

## Explainability

Recommendations should show why, not just a numeric score.

Example Call recommendation:

``` text
ABC Plumbing
Follow-up due today
Owner previously reached
8 mobile lines
Last contact: 6 days ago
Recommended: Call
```

Example Visit recommendation:

``` text
Sunshine Dental
Near next route stop
Office manager usually available mornings
Return visit promised
Recommended: Visit
```

The AE must always be able to override recommendations.

Override actions should eventually include removing a recommended prospect,
manually adding a prospect, pinning a prospect, changing Call vs. Visit where
eligibility permits, rearranging flexible work, preserving fixed commitments,
and rebuilding/recalculating remaining Mission capacity. Manual intervention
must not corrupt the underlying Prospect Pool.

## Unfinished Work

Daily goals reset. Untouched call prospects return to the call pool. Untouched
visit prospects return to the visit pool. The system creates no fake activity.
During the next planning cycle, the entire eligible pool is re-ranked, and an
untouched prospect may or may not be selected again.

Core rule:

> **Goals do not roll over. Unfinished prospect actions do.**

## Pool Replenishment

Prospector AI should monitor inventory health.

Example future warning:

``` text
Call inventory getting low
73 usable prospects remaining

[ Import / Add Leads ]
```

For MVP, do **not** build automatic Google/Yelp scraping.

Initial practical workflow:

``` text
External public-business research
        ↓
Clean CSV
        ↓
Prospector AI Import
```

Automatic enrichment/research can be considered after the workflow proves
useful.

## Data Handling / Privacy

Public-business research and internal/customer data are different.

Prospector AI should:

- minimize storage of internal/company customer data;
- not send internal Salesforce/customer datasets to external AI services by
  default;
- use public-business enrichment workflows separately;
- require approval before AI-generated research becomes trusted prospect data
  when applicable.

## Relationship to Day-in-the-Life

``` text
Lead Supply
   ↓
Prospect Pools
   ↓
Plan Tomorrow
   ↓
Calendar / fixed commitments
   ↓
Today's Mission
   ↓
Activities
   ↓
Outcomes + Next Actions
   ↓
Updated Prospect Pools
   ↓
Next Planning Cycle
```

The Lead Engine should be mostly invisible during Golden Time and active field
execution.

## MVP Include / Defer

Include in MVP:

- CSV import foundation;
- lead-source tracking;
- call eligibility;
- visit eligibility;
- prospect pools;
- follow-up priority;
- deterministic scoring/ranking;
- re-planning untouched prospects;
- basic inventory-health indicator;
- AE override.

Defer:

- automated Google/Yelp scraping;
- expensive AI ranking for every prospect;
- sophisticated autonomous route optimization;
- bulk Salesforce existing-customer/service synchronization;
- autonomous AI changes to trusted prospect data.
