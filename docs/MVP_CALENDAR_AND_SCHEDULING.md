# Prospector AI — MVP Calendar and Scheduling

**Status:** Approved MVP Foundation\
**Purpose:** Define how Prospector AI handles appointments, calendar
commitments, reminders, and calendar-aware daily planning.

> **Prospector AI manages sales context and daily execution. Google Calendar
> manages external appointment visibility and device reminders.**

Prospector AI must not create an isolated appointment system that requires the
app to be running for the AE to know about appointments.

## Responsibility Boundaries

Prospector AI owns:

- prospect relationship;
- Activity history;
- sales context;
- discovery;
- objections;
- Next Actions;
- appointment relationship to prospect/contact;
- daily Mission planning;
- coaching context.

Google Calendar owns/provides:

- external calendar visibility;
- calendar event representation;
- device notifications/reminders;
- visibility while Prospector AI is closed.

Avoid building a second full calendar application inside Prospector AI.
Prospector AI may display today's or tomorrow's commitments as part of Mission
planning and execution.

## Appointment Creation

Appointments may originate from a sales Activity / Next Action.

``` text
Meaningful Conversation
        ↓
Voice Debrief
        ↓
AI Review
        ↓
Next Action
        ↓
Appointment
        ↓
Date / Time
        ↓
Save
        ↓
Prospector AI appointment/follow-up context
        +
Google Calendar event
```

Prospector AI should retain sales-specific context. Google Calendar provides
normal calendar visibility, Android/iOS calendar access, device reminders and
notifications, and availability outside Prospector AI.

This is important because Prospector AI may not be open when an appointment
reminder is needed.

## Calendar Event Content

Keep calendar events useful but not overloaded.

Possible information:

``` text
Title:
ABC Plumbing — Sales Appointment

Date/time

Location/address

Contact:
Mike — Owner

Purpose:
Review mobile pricing
```

Optional concise sales context:

- current provider;
- approximate lines;
- reason for meeting;
- important objection/need.

Do not dump an entire CRM record into Google Calendar.

Be mindful that calendar data may sync outside Prospector AI, so minimize
sensitive/internal information.

## Calendar-Aware Plan Tomorrow

Before Prospector AI builds tomorrow's Mission, it should account for existing
calendar commitments.

Conceptually:

``` text
Google Calendar
        ↓
Read tomorrow's commitments
        ↓
Prospector AI Planning Engine
        ↓
Protect fixed commitments
        ↓
Protect Golden Time where possible
        ↓
Build Calls / Visits / Follow-Ups around commitments
        ↓
Recommended Mission
```

Example Google Calendar:

``` text
10:30 AM — ABC Dental
2:00 PM — Team Meeting
3:30 PM — Customer Appointment
```

Prospector AI may produce:

``` text
8:00–10:00
Golden Time — Calls

10:30
ABC Dental

11:30–1:30
Door Route

2:00
Team Meeting

2:45–3:15
Follow-Ups

3:30
Customer Appointment

4:30
Admin / Plan Tomorrow
```

The planner must not schedule prospecting activities over fixed calendar
commitments.

## Planning Order

The approved planning order is conceptually:

1. Calendar/fixed commitments
2. Explicit appointments
3. Manually pinned/time-constrained work
4. Due/overdue follow-ups
5. Golden Time blocks
6. Ranked call prospects
7. Ranked visit prospects
8. Flexible administrative/review work

Do not treat this list as immutable algorithm code yet. It is a
product-planning principle.

## App Closed / Reminders

The MVP must not depend on the Prospector AI web app remaining open to provide
appointment reminders.

For MVP, Google Calendar/device notifications solve this problem.

Native Prospector AI push notifications may be considered later if a native
mobile application is developed. Native push notifications are not an MVP
requirement.

## External Calendar Events

Prospector AI should account for relevant existing Google Calendar events even
when they were not created by Prospector AI.

Examples:

- Spectrum team meeting;
- training;
- personal blocked time where appropriate;
- existing customer appointment;
- externally created sales meeting.

These events do not necessarily need full Prospect records. For planning
purposes, they primarily function as **fixed / unavailable time**.

## Appointments vs. Follow-Ups

A **Follow-Up** is a Next Action that should happen later.

Examples:

- call Friday;
- return next week;
- send quote;
- research decision maker.

An **Appointment** is a time-specific commitment involving the AE and normally
another person/business.

Examples:

- meet owner Tuesday 10:30;
- scheduled discovery call;
- on-site meeting.

Appointments are stronger scheduling constraints than ordinary flexible
follow-ups.

## Sync Behavior

MVP should support:

- connect one Google account/calendar;
- read relevant calendar commitments;
- create Google Calendar events for Prospector AI appointments;
- maintain a link/reference between the Prospector AI appointment and external
  calendar event;
- update the corresponding calendar event when an appointment created by
  Prospector AI changes;
- handle cancellation clearly;
- avoid duplicate event creation.

Exact conflict-resolution behavior for edits made directly in Google Calendar
versus Prospector AI should be finalized during technical design.

Do not prematurely design a complex bidirectional synchronization engine.

## Mission Capacity and User Control

> **Prospector AI recommends. The AE remains in control.**

The planner should be explainable and overrideable.

The AE should eventually be able to:

- remove a recommended prospect;
- manually add a prospect;
- pin a prospect;
- change Call vs. Visit where eligibility permits;
- rearrange flexible work;
- preserve fixed commitments;
- rebuild/recalculate remaining Mission capacity.

Manual intervention should not corrupt the underlying Prospect Pool.

Pinned work reserves capacity. It does not increase the daily activity target.

## Cost Principle

The initial Prospector AI target is a very low operating cost.

Calendar planning should use deterministic application logic wherever possible.

Do not require LLM/API calls merely to:

- read appointments;
- identify occupied time;
- place fixed commitments;
- calculate remaining capacity;
- construct basic daily blocks.

AI should be reserved for tasks where it provides meaningful value, such as:

- voice transcription interpretation;
- activity structuring;
- coaching;
- summarization;
- later intelligent recommendations.

## MVP Include / Defer

Include in MVP:

- Google Calendar connection;
- read calendar commitments needed for planning;
- create calendar event from Prospector AI appointment;
- update/cancel Prospector AI-created appointment event;
- prevent obvious duplicate creation;
- show relevant appointments in Today's Mission;
- account for fixed calendar commitments during Plan Tomorrow;
- rely on calendar/device notifications when app is closed.

Defer:

- advanced multi-calendar management;
- team calendar management;
- complex bidirectional conflict resolution;
- autonomous rescheduling;
- native mobile push notification infrastructure;
- full calendar UI inside Prospector AI;
- AI scheduling negotiations with prospects;
- enterprise scheduling integrations beyond the MVP requirement.

## Relationship to Other MVP Docs

- [MVP_DAY_IN_THE_LIFE.md](MVP_DAY_IN_THE_LIFE.md) answers: "What should I be
  doing now?"
- [MVP_LEAD_ENGINE.md](MVP_LEAD_ENGINE.md) answers: "Who should I work?"
- This document answers: "When can I work them?"

Activities and Coaching eventually answer: "What happened and how do I improve?"
