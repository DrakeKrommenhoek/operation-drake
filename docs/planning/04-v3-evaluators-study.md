# v3: Evaluators + Study Engine

Effort: 2 weekends. Prereq: v2 passed its 5-brief gate. Two independent modules; build Idea Scorer first.

## Module A: Idea Scorer

### Goal
Every Business Ideas entry gets a rubric score written back to Notion, ranked weekly, with forced kill decisions. Creativity gets stored AND judged, so ideas stop stacking.

### Rubric (0-10 each, one Claude call per idea)
- **Leverage**: revenue potential per hour of Drake's time
- **Effort to first dollar**: inverted, faster = higher
- **Unfair advantage**: existing skills, network, or assets that apply
- **Compliance risk**: inverted, Mountaingate conflicts = low score
- **Energy**: alignment with stated values and genuine interest

Composite = weighted: Leverage 0.3, Effort 0.25, Advantage 0.2, Compliance 0.15, Energy 0.1.

### Implementation
- Add Notion properties to the vault: Score (number), Score Breakdown (text), Last Scored (date), Reviews Survived (number).
- Weekly cron (runs before the Sunday digest): score any unscored or edited Business Ideas entry, increment Reviews Survived on untouched ones.
- Sunday digest gains a section: ranked idea leaderboard + auto-flag any idea with Reviews Survived >= 3 and no status change: "Kill or commit."

## Module B: Study Guide Engine

### Goal
The full learning loop: study, test, teach. Runs on Learning entries.

### Weekly cycle (per one entry at a time)
- **Monday 7 AM**: pick the oldest untouched Learning entry, generate a study guide (key concepts, 5 core questions, one real-world application), write it as a child page, send Telegram summary.
- **Wednesday 7 PM**: send 5 quiz questions via Telegram. User replies with answers; Claude grades and explains misses.
- **Friday 5 PM**: prompt "Explain this topic back in a voice note like you are teaching Callie." Transcribe the reply (existing Telegram Voice pipeline), Claude critiques the explanation for gaps.
- Completion writes Status = Organized and a Retention Score property.

### Pilot
Reactants Theory entry.

## Out of scope
- Spaced repetition scheduling beyond one topic per week
- Flashcard apps or Anki integration

## Done when
- Every Business Ideas entry has a score and the leaderboard has produced at least one kill.
- One full Monday-to-Friday study cycle completed on Reactants Theory.

## Gotchas
- Score writes are property updates only, never touch page content.
- Quiz state machine needs SQLite (question index, answers) keyed by chat id; keep it dumb.
- Voice transcription already exists in the intake pipeline; reuse it, do not rebuild.
