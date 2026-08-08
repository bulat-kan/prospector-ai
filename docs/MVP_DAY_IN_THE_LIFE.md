# Prospector AI --- MVP Day in the Life

**Status:** Approved\
**Purpose:** Product and UX specification for the Prospector AI MVP\
**Primary design target:** Samsung Galaxy S23 Ultra first; tablet/iPad
second; desktop third\
**Core product identity:** Field Sales Operating System + Personal Sales
Coach

## 1. Core Daily Loop

**PLAN → EXECUTE → CAPTURE → FOLLOW UP → LEARN → REPLAN**

> **Plan tonight. Execute tomorrow.**

Morning prospecting time is for execution rather than deciding what to
do.

> **A salesperson should be able to get through an entire productive
> workday without needing to open a traditional CRM-style screen.**

Companies, contacts, locations, opportunities, and orders may exist
underneath the experience, but they should not dominate the AE's daily
workflow.

------------------------------------------------------------------------

## 2. Evening --- Plan Tomorrow

Tomorrow's Mission begins at the end of the current workday.

Prospector AI surfaces:

-   Overdue follow-ups
-   Tomorrow's appointments
-   Prospects ready for callback
-   Territory prospects available for physical visits
-   High-priority opportunities
-   Unfinished activities worth carrying forward

Example:

``` text
Tomorrow — Friday, Aug 8

⚠ 3 overdue follow-ups
📅 2 appointments
☎ 11 prospects ready for callback
📍 34 territory prospects available
🔥 4 high-priority opportunities
```

Fixed commitments are placed first. Prospecting blocks are built around
them.

### Tomorrow's behavior goals

``` text
☎ Calls                 30
🚪 Visits                15
👤 Decision Makers        5
📅 Appointments           1
🤝 Referral Requests      2
```

These emphasize controllable prospecting behaviors rather than only
outcomes.

------------------------------------------------------------------------

## 3. Build Tomorrow's Call List

Recommended buckets:

-   Follow-ups due
-   Previous meaningful conversations
-   Open opportunities
-   High-priority prospects
-   New remote prospects
-   Older prospects worth retrying

The AE can accept, remove, add, and reorder prospects.

Remote calling/email prospecting may cover eligible Spectrum service
areas beyond the physical door-knocking territory.

------------------------------------------------------------------------

## 4. Build Tomorrow's Door-Knock Route

Physical prospecting is separate from remote prospecting. Only
businesses eligible for physical prospecting in the assigned territory
should appear.

Future prioritization can consider geography, business hours, priority,
previous attempts, promised follow-ups, appointments, industry, and
likelihood of reaching a decision maker.

``` text
TERRITORY ROUTE

Suggested prospects: 18
Estimated route: 2h 35m
```

------------------------------------------------------------------------

## 5. Tomorrow Is Ready

``` text
TOMORROW IS READY ✓

☎ 32 calls prepared
🚪 18 visits prepared
📅 2 appointments
🔥 3 priority follow-ups
🗺 Route ready

[ Finish Day ]
```

**MVP target:** planning tomorrow should take under 10 minutes.

------------------------------------------------------------------------

## 6. Morning --- Today's Mission

The default home screen is **Today's Mission**.

``` text
TODAY'S MISSION

CALLS       VISITS       APPTS
0/30         0/15         0/2

🟡 GOLDEN TIME
8:00 – 10:00

Current Mission:
COLD CALLING

NEXT BEST ACTION

☎ Mario's Pizza
Owner requested callback

[ CALL ]
```

The screen should make the next action obvious.

------------------------------------------------------------------------

## 7. Golden Time --- Call Block

Starting a Call Block simplifies the interface and removes distractions.

``` text
GOLDEN TIME

18 prospects remaining
1h 42m remaining

ABC Plumbing
Owner: Mike

Last activity:
Visited Tuesday

Note:
Receptionist said owner
usually arrives before 9 AM.

[ ☎ CALL ]

Skip      Prospect Info
```

During Golden Time, execution comes before analytics, coaching, and
administration.

------------------------------------------------------------------------

## 8. Quick Call Outcomes

``` text
HOW DID IT GO?

○ No Answer
○ Gatekeeper
○ Decision Maker
○ Interested
○ Appointment
○ Not Interested
```

Simple outcomes should be extremely fast.

**No Answer → one tap → Next Call**

Voice logging is not required for trivial interactions.

------------------------------------------------------------------------

## 9. Meaningful Conversation --- Voice Debrief

For a meaningful conversation:

``` text
Conversation completed

🎤 Tell me what happened

[ Hold to Record ]
```

Example debrief:

> Talked to Mike, owner. They're using Frontier for Internet and Verizon
> for eight phones. Internet is okay but Verizon costs around \$500.
> He's interested in seeing mobile pricing. He said switching sounds
> like a headache. I told him I'd help coordinate it. Appointment
> Tuesday at ten.

The goal is minimal typing.

------------------------------------------------------------------------

## 10. AI Activity Review

AI transcribes the debrief and prepares a structured draft for AE
approval.

``` text
AI ACTIVITY REVIEW

👤 Mike — Owner
✓ Decision Maker

OUTCOME
Interested

DISCOVERY
✓ Current Internet: Frontier
✓ Current Mobile: Verizon
✓ Mobile lines: 8
✓ Current spend: ~$500

NEED
Reduce mobile expense

PRODUCT
Business Mobile

OBJECTION
Switching inconvenience

HANDLING
Partially addressed

NEXT ACTION
Appointment
Tuesday • 10:00 AM

[ Edit ]        [ ✓ Save ]
```

**AI proposes. The AE confirms.**

AI-generated information should not silently become trusted prospect
data without review.

------------------------------------------------------------------------

## 11. Administrative Automation

After approval, Prospector AI should perform related administrative
actions where appropriate:

``` text
Activity saved ✓
Contact updated ✓
Opportunity suggested ✓
Appointment created ✓
Follow-up scheduled ✓
Coaching data captured ✓
```

The same information should not need to be entered repeatedly.

------------------------------------------------------------------------

## 12. Golden Time Completion

``` text
GOLDEN TIME COMPLETE ✓

32 Calls
11 Conversations
6 Decision Makers
3 Follow-ups
2 Appointments
1 Opportunity
```

Then transition to the next Mission.

------------------------------------------------------------------------

## 13. Field Prospecting --- Door-Knock Route

``` text
DOOR-KNOCK ROUTE

Stop 4 of 16

📍 Sunshine Dental
0.7 miles

Priority ★★★★☆
Never visited

[ NAVIGATE ]
[ VIEW PROSPECT ]
```

External navigation software may handle driving directions. Prospector
AI handles sales execution and activity history.

An optional **Start Visit** may timestamp a visit. GPS automation is not
required for MVP.

------------------------------------------------------------------------

## 14. Gatekeeper Scenario

``` text
WHO DID YOU REACH?

○ No one
● Gatekeeper
○ Decision Maker
```

Then:

``` text
OUTCOME

○ Left Card
● Decision Maker Unavailable
○ Got Contact Info
○ Follow-up Needed
```

Example voice debrief:

> Receptionist Sarah said office manager Jennifer handles Internet.
> Jennifer is usually here Tuesday mornings.

AI draft:

``` text
Contact:
Sarah — Receptionist

Possible decision maker:
Jennifer — Office Manager

Best visit:
Tuesday morning

Next action:
Return visit
Tuesday 9:30 AM
```

Then **Next Stop →**

------------------------------------------------------------------------

## 15. Successful Discovery Visit

When the decision maker is reached:

``` text
VISIT
 ↓
Decision Maker
 ↓
Discovery
 ↓
Need
 ↓
Products
 ↓
Objections
 ↓
Outcome
 ↓
Next Action
```

Most structured information should come from the voice debrief rather
than a long manual form.

------------------------------------------------------------------------

## 16. Discovery Assessment

For meaningful conversations, Prospector AI should capture or
infer---subject to AE confirmation:

-   Was the decision maker reached?
-   Were discovery questions asked?
-   Was a real problem or need uncovered?
-   Did the prospect describe the problem in their own words?
-   Was the current provider learned?
-   Were current products/services learned?
-   Were employee/mobile-line counts learned when relevant?
-   Was contract timing learned when relevant?
-   Was the decision process identified?

The purpose is better selling and coaching, not administrative scoring
for its own sake.

------------------------------------------------------------------------

## 17. Product and Solution Tracking

An Activity may distinguish products that were:

-   Discussed
-   Qualified
-   Recommended
-   Quoted
-   Included in a proposal

Possible products include Internet, Mobile, Voice, TV, Seasonal Sports,
applicable sports offerings, Backup Internet, Managed WiFi, and other
applicable services.

A product merely mentioned is not equivalent to a solution tied to a
discovered need.

Track whether:

-   A solution was presented
-   Pricing was provided
-   A formal quote/proposal was sent
-   The recommendation was connected to an identified need

The desired behavior is consultative: help the prospect determine
whether an appropriate Spectrum solution solves a real business problem
rather than pushing unnecessary products.

------------------------------------------------------------------------

## 18. Objection Tracking

Common categories:

-   Happy with current provider
-   Price
-   Contract
-   No perceived need
-   Corporate decision
-   Decision maker unavailable
-   Bad past Spectrum experience
-   Service-quality concern
-   Installation concern
-   Switching inconvenience
-   Wants to think about it
-   Timing
-   Competitor preference
-   Not interested
-   Other

Where practical, capture:

``` text
Objection:
Happy with current provider

How did I respond?
[AI-extracted response]

Result:
○ Overcame
○ Partially handled
○ Did not overcome
○ Conversation ended before handling

Confidence:
1  2  3  4  5
```

This becomes part of the salesperson's coaching history.

------------------------------------------------------------------------

## 19. Lost / Not Interested

A lost lead should not simply disappear.

Structured lost reasons can include:

-   No perceived problem
-   No value established
-   Price
-   Contract
-   Chose competitor
-   Corporate decision
-   Spectrum reputation
-   Service availability
-   Technical limitation
-   Timing
-   Could not reach decision maker
-   Customer stopped responding
-   Product not appropriate
-   Other

Also capture revisit potential:

``` text
REVISIT?

○ 3 months
○ 6 months
○ 12 months
● Don't revisit
```

A timing issue should be distinguishable from permanent
disqualification.

------------------------------------------------------------------------

## 20. Outcome Taxonomy

Not every unsuccessful interaction is **Lost**.

### Not Reached

Examples: owner unavailable, corporate contact unknown, business closed,
wrong time.

### Not Now / Nurture

Examples: under contract, call next quarter, opening delayed, budget
unavailable today.

### Disqualified

Examples: invalid business, outside applicable service area, no viable
Spectrum opportunity, or no useful local path.

### Lost

The decision maker meaningfully evaluated the situation and declined,
selected another solution, or no viable path remains after discovery.

------------------------------------------------------------------------

## 21. Next Action

A viable interaction should generally conclude with a next action:

-   Call
-   Return visit
-   Email
-   Text
-   Send quote
-   Send proposal
-   Research decision maker
-   Check contract timing
-   Appointment
-   No follow-up

Store date/time, priority, and reason/context.

The Activity should create the follow-up automatically where possible.

------------------------------------------------------------------------

## 22. Schedule Disruption

Real field-sales days change. Prospector AI should support replanning
without treating schedule changes as failure.

Future experience:

``` text
SCHEDULE CHANGED

New appointment
1:45 PM

Door route adjusted.

4 remaining visits moved
to later today.
```

Manual rearrangement is sufficient for MVP.

------------------------------------------------------------------------

## 23. Follow-Up Mission

``` text
FOLLOW-UP MISSION

7 due today

3 calls
2 emails
1 text
1 proposal
```

Present one prospect/action at a time rather than a large CRM table.

------------------------------------------------------------------------

## 24. Referral Behavior

Prospector AI should help build the habit of asking for referrals and
introductions.

``` text
💡 REFERRAL OPPORTUNITY

Good conversation with Mike.

Would this be a good time
to ask for an introduction?

[ Add to Follow-Up ]
[ Not Now ]
```

Referral behavior can become part of daily goals and coaching.

------------------------------------------------------------------------

## 25. Coach Works Quietly

Throughout the day, Prospector AI may collect:

-   Objections encountered
-   Discovery performed
-   Decision-maker conversations
-   Questions missed
-   Products recommended
-   Lost reasons
-   Referral asks
-   Follow-up behavior
-   Outcomes

> **Coaching should not interrupt Golden Time or active prospecting
> blocks.**

Coaching belongs primarily in review, reflection, preparation, and
learning moments.

------------------------------------------------------------------------

## 26. End-of-Day Review

``` text
TODAY COMPLETE

Calls             34 / 30 ✓
Visits            13 / 15
Decision Makers    7 / 5 ✓
Appointments       2 / 1 ✓
Referral Asks      1 / 2

FOLLOW-UPS CREATED
8

NEW OPPORTUNITIES
3
```

The app should use context rather than treating every missed numeric
target as failure.

------------------------------------------------------------------------

## 27. Daily Reflection

**Target:** about 60 seconds. Voice should be available.

``` text
TODAY'S REFLECTION

🎤 What did you learn today?
```

AI may surface patterns and coaching suggestions, such as noticing a
recurring objection and recommending a better discovery question.

The goal is improvement in questioning, listening, discovery, objection
handling, and solution alignment---not simply memorizing rebuttals.

------------------------------------------------------------------------

## 28. Salesperson Development Loop

``` text
Activity
   ↓
Discovery data
   ↓
Objections encountered
   ↓
How the AE responded
   ↓
Outcome
   ↓
Reflection
   ↓
Pattern Detection
   ↓
Coach
   ↓
Practice
   ↓
Next Conversations
   ↓
Better Activity Data
```

> **Every meaningful sales interaction should improve both the prospect
> record and the salesperson.**

------------------------------------------------------------------------

## 29. Complete Day-in-the-Life Map

``` text
EVENING
   ↓
Review Today
   ↓
Coach
   ↓
Plan Tomorrow
   ↓
Call List + Visit Route + Appointments
   ↓
TOMORROW READY
   ↓
MORNING
   ↓
Today's Mission
   ↓
Golden Time
   ↓
Calls
   ↓
Quick Outcome OR Meaningful Conversation
                    ↓
                 Voice Log
                    ↓
                 AI Review
                    ↓
                 Next Action
                    ↓
          Follow-Up / Opportunity
                    ↓
              Territory Block
                    ↓
                Visit Route
                    ↓
                   Visit
                    ↓
                Voice Log
                    ↓
                 AI Review
                    ↓
          Nurture / Qualified / Lost
                    ↓
               Next Prospect
                    ↓
                END OF DAY
                    ↓
                Daily Review
                    ↓
              Coaching Insight
                    ↓
               Plan Tomorrow
                    ↓
                    ↺
```

------------------------------------------------------------------------

## 30. First Clickable Figma Prototype

The first complete prototype should cover:

**Plan Tomorrow → Today's Mission → Call Block → Log Conversation → AI
Review → Follow-Up → Door Route → Log Visit → AI Review → End-of-Day
Review → Plan Tomorrow**

This is the backbone of the MVP.

Detailed prospect management, Opportunities, Orders, commission
information, and deeper Knowledge/Coach capabilities should attach to
this operating loop rather than dictate it.

------------------------------------------------------------------------

## 31. Mobile UX Requirements

-   Samsung Galaxy S23 Ultra is the primary initial design target
-   Tablet/iPad is secondary
-   Desktop remains usable
-   Large touch targets
-   One-handed operation where practical
-   Minimal typing
-   Voice-first meaningful activity capture
-   High readability outdoors
-   Card-based mobile layouts rather than dense tables
-   Progressive disclosure
-   One obvious primary action per screen
-   Quick outcomes should require one or two taps
-   Meaningful post-conversation logging should generally target under
    30 seconds
-   Tomorrow planning should target under 10 minutes

------------------------------------------------------------------------

## 32. MVP Product Principles

1.  Prospector AI is not a traditional CRM.
2.  Today's Mission is the operational home screen.
3.  Plan tomorrow tonight.
4.  Protect Golden Time.
5.  Activities are the center of the operating model.
6.  Follow-up should be generated from the interaction, not remembered
    manually.
7.  Voice should replace unnecessary typing.
8.  AI drafts; the AE confirms.
9.  Every meaningful interaction should improve both the prospect record
    and salesperson.
10. The system should reduce administrative work, not create it.
11. Coaching should support execution, never interrupt it.
12. Mobile field execution comes before desktop CRM-style reporting.

------------------------------------------------------------------------

## 33. Approval and Change Control

This document represents the **approved MVP Day-in-the-Life workflow**
and should be treated as a product-design reference for:

-   Information architecture
-   Figma wireframes
-   Clickable prototype
-   UX testing
-   MVP backlog
-   Data-model decisions
-   AI workflow design
-   Future implementation

Changes to the core flow should be deliberate and documented rather than
introduced casually during implementation.

---

## 34. Daily Targets vs. Unfinished Prospect Work

Daily numerical activity goals and individual prospect actions are different
product concepts.

Daily goals reset every day. They do **not** accumulate as numerical debt.

Examples:

- If the goal is 30 calls and the AE completes 5, tomorrow does **not** become
  55 calls.
- If the goal is 15 visits and the AE completes 5, tomorrow does **not** become
  25 visits.
- Missed Decision Maker and Referral Ask targets also do not numerically roll
  over.

Core rule:

> **Goals do not roll over. Unfinished prospect actions do.**

### Untouched Planned Prospects

If a prospect was selected for today's Mission but the AE never attempted the
planned action, no fake Activity or failed attempt is created.

- Untouched planned call prospects return to the call-eligible pool.
- Untouched planned visit prospects return to the visit-eligible territory pool.
- They are **not** automatically copied into tomorrow's Mission.
- During the next planning cycle, the entire eligible pool is re-evaluated and
  re-ranked.
- Previously planned but untouched prospects may be selected again if they still
  rank highly enough.
- Other prospects may replace them because of urgency, follow-up commitments,
  decision-maker availability, geography, business hours, priority,
  opportunity/need signals, retry timing, or route efficiency.

> **Mission lists are temporary daily selections. Prospects are the persistent
> source of truth.**

### Untouched vs. Attempted

- **Never attempted:** remains eligible for future selection.
- **Called -> No Answer:** Activity is recorded and retry rules determine future
  eligibility.
- **Visited -> Gatekeeper:** Activity is recorded and known decision-maker
  availability or explicit follow-up affects future visit priority.
- **Decision maker says "Call Friday":** creates an explicit Friday follow-up
  and receives very high planning priority.

### Conceptual Flow

``` text
ALL ELIGIBLE PROSPECTS
        ↓
Fixed commitments / follow-ups
        ↓
Eligibility filters
        ↓
Score + rank
        ↓
Build today's Call and Visit Missions
        ↓
Execute
        ↓
Completed -> Activity + Next Action
Untouched -> Return to eligible pool
        ↓
Re-score during next planning cycle
```

This keeps prospects from disappearing while preventing an ever-growing rollover
backlog.

## 35. Lead Supply and Prospect Pool

> **Prospect Pool = inventory. Mission = today's selected work.**

> **Lead Supply ≠ Prospecting Execution.**

Salesforce remains the corporate system of record. Prospector AI focuses on
prospecting execution, lead intelligence, follow-up, daily planning, activity
history, and coaching.

Important correction: Salesforce does **not** allow the AE to export a
convenient bulk existing-customer dataset containing services and contact-person
information. Prospector AI must not depend on such an export.

Lead supply, import location, pool replenishment, ranking, and daily Mission
selection rules are defined in [MVP_LEAD_ENGINE.md](MVP_LEAD_ENGINE.md).
