# 06: Wellness Agent (DK_0726 integration)

Replaces v4 Module A. Prereqs: v1.1 shipped (Telegram write-back is the food/supplement logging surface) AND DK_0726 Phase 0 complete (14 consecutive days of manual logging). Do not start Phase 1 code before both gates pass.

## Hardware decision: MADE

Fitbit Air. This unblocks the DK_0726 ingest layer.

## Architecture truths (verified June 2026, re-verify before build)

- Air data syncs to the Google Health app; pull via **Google Health API** (`health.googleapis.com/v4/`), Google OAuth 2.0.
- **NOT the legacy Fitbit Web API.** It shuts down September 2026. Zero code against it.
- **Nutrition data is NOT in the Google Health API.** Macros, food, and supplements can only come from self-logging via the Telegram pipeline. The pipeline is the keystone.
- The Air's Google Health Premium trial includes a Gemini coach that already does generic coaching. This agent exists ONLY for what that coach cannot do: correlate biometrics against YOUR other data (supplements, food, stress notes, golf, mood, work intensity).

## Data model

### From Google Health API (daily poll, SQLite, aggregates only)
Sleep score and stages, Resting HR, HRV, SpO2, Respiratory Rate, Steps, Active Zone Minutes.

### From Telegram logging (new bot commands, extends v1.1)
- `/food chicken bowl, rice, avocado` -> Claude estimates macros (protein/carbs/fat/cals), logs with timestamp. Estimation, not precision; consistency beats accuracy for n-of-1 correlation.
- `/supp creatine 5g` -> supplement log with dose and time. Free text okay; normalizer maps to canonical names.
- `/stress 7 tight IC memo deadline` -> 1-10 rating plus optional note.
- `/workout push day 45min` or auto-detected from Active Zone Minutes.
- Logging burden target: under 60 seconds per day total. If it takes longer, cut fields, not consistency.

## Feature scope by tier

### Tier 1: Tracking + daily insight (build first)
- Daily ingestion job (idempotent, per DK_0726 Phase 2 spec).
- One short daily insight via Telegram: plain language, declines to comment when data is incomplete. Example: "Sleep 82, HRV up 12% vs baseline. Third-best HRV this month; all three followed magnesium + no-screens nights."
- Feeds a health section into the Sunday digest (spec 02).

### Tier 2: Correlation engine (needs 21+ valid days)
- Weekly job: supplement/habit on-days vs off-days against sleep, HRV, RHR. Flag correlations only with n >= 7 per condition; always labeled "observation, not causation."
- One low-risk testable suggestion per week, max. Never stacked changes (can't attribute otherwise).

### Tier 3: Meal planning for school (build in August, ships for fall semester)
- Inputs: macro targets, W&L dining/grocery reality, cooking constraints, weekly schedule.
- Sunday output: 5-day meal plan with a grocery list, sized to hit macro targets.
- **Hard constraint in the system prompt: TREE-NUT ALLERGY. Every plan, every product, every recipe is filtered. No exceptions, no "may contain" ambiguity without a flag.**

### Tier 4: Product recommendations (lowest priority)
- Agent may shortlist products (protein, sleep aids, recovery gear) with the tree-nut filter applied and price comparison via web search.
- **Supplements are surfaced as options with evidence summaries only. New supplement decisions and interactions get the standing line: discuss with your doctor. The agent recommends questions, not doses.**

## Explicitly out of scope
- Anything the Gemini coach already does generically (step nudges, generic sleep tips).
- Medical interpretation, diagnosis, TMS-related analysis.
- Multi-user, SaaS, dashboards beyond DK_0726 Phase 4.
- Raw health data in the repo or in Notion. Aggregates in local SQLite only.

## Done when
- Tier 1: 14 consecutive daily insights delivered, logging streak intact.
- Tier 2: first correlation report with at least one n>=7 finding.
- Tier 3: two consecutive school weeks eating off the generated plan.

## Gotchas
- Google OAuth refresh must run headless on the VPS; tokens in env vars, never committed.
- Apple Health interim data from Phase 0 does not merge into the Fitbit baseline; treat pre-Air data as a separate epoch or discard.
- The real go/no-go was named weeks ago: daily logging discipline. If the Phase 0 streak broke, restart the 14 days before building anything. The gate is the product.
