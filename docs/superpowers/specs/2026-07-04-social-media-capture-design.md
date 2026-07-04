# Social Media & URL Capture — Design Spec
_Session 6 · D.R.A.K.E. Second Workflow_
_Date: 2026-07-04_

---

## 1. Goal

Enable Drake to forward or paste an Instagram Reel, TikTok, YouTube video, or article URL in Telegram and receive a structured, evidence-grounded summary saved to the D.R.A.K.E. Knowledge Vault and returned as a Telegram reply.

D.R.A.K.E. must never claim to understand a video's content based only on its URL or Drake's profile context. All analysis must be grounded in verified evidence (transcript, caption, or user-provided context).

---

## 2. Context

### 2.1 Existing project: Reel Intelligence

`~/reel_analyzer.py` and `~/reel-intelligence/` implement an earlier version of this idea:
- `reel_analyzer.py`: standalone script, hardcoded URLs, Claude speculates about reel content from URL alone → Notion
- `reel-intelligence/sync.py`: daemon that scrapes Instagram saved-posts using browser session cookies → Notion

Neither is integrated with D.R.A.K.E. The speculative-analysis approach in `reel_analyzer.py` must not become a default behavior. The cookie scraping daemon is deferred and isolated.

### 2.2 Existing D.R.A.K.E. Notion integration (Session 5)

The parallel session built the Knowledge Vault foundation:
- `integrations/notion/` — classifier, mapper, body_builder, sync_service, live_client, mock_client
- `NotionSyncORM` — idempotency, retry, outbox tracking
- 16-property Knowledge Vault schema in `setup.py`
- `NOTION_ENABLED=false` default; `--setup-notion` CLI command
- 193 tests passing on master

This workflow is a **focused extension** of that foundation. No parallel Notion schemas are created.

---

## 3. Architecture Overview

```
Telegram URL message
  → TelegramAdapter._handle_text()
  → OrchestratorService.process()  [intent: capture_media or save_link upgrade]
  → MediaCaptureWorkflow.run()
      → PlatformRouter.identify(url)         # platform + normalized_url
      → SocialAdapter.fetch_metadata()       # caption, creator, title, published_at
      → yt-dlp extract (best-effort)         # audio_path or failure
      → OpenAI Whisper transcribe            # transcript or skip
      → SynthesisAgent.analyze()             # only on verified evidence
      → ArtifactService.save()               # local markdown artifact
      → NotionSyncService.sync()             # Knowledge Vault page
  → ProcessResult → _format_result()
  → Telegram reply
```

All stages after metadata fetch are best-effort. A stage failure produces a structured fallback record, not a task failure.

---

## 4. Feature Branch

All work for this spec lives on:

```
feature/social-media-capture
```

Do not merge to master until:
1. The Knowledge Vault Notion branch (Session 5) is fully merged and stable.
2. Notion schema extensions from this spec are reviewed for conflicts.
3. This spec's test suite passes cleanly.

Do not deploy live downloading to the VPS during this session.

---

## 5. New Intent

Upgrade the existing `save_link` intent to `capture_media` (or keep `save_link` as the name but replace its workflow). The router already detects URLs and sets `message_type = "url"`. The routing keyword `save_link` already exists as a SAFE_INTENT.

**Decision**: Keep `save_link` as the intent name to avoid router churn. Replace `CaptureNoteWorkflow` as its execution target with the new `CaptureMediaWorkflow`.

---

## 6. Source Adapters

Location: `src/operation_drake/content/social/`

### 6.1 Base contract

```
content/social/base.py     — MediaCaptureResult dataclass + SocialAdapter ABC
content/social/router.py   — PlatformRouter: identifies platform from URL
content/social/instagram.py
content/social/tiktok.py
content/social/youtube.py
content/social/generic.py  — fallback for articles and unknown URLs
```

### 6.2 MediaCaptureResult

```python
@dataclass
class MediaCaptureResult:
    normalized_url: str
    platform: str                     # "instagram_reel" | "tiktok" | "youtube" | "article" | "unknown"
    creator: str | None
    caption: str | None
    title: str | None
    published_at: str | None
    thumbnail_url: str | None
    media_path: str | None            # local temp path after download; None if failed
    audio_path: str | None            # extracted audio path; None if failed
    transcript: str | None            # Whisper output; None if not attempted
    metadata: dict                    # raw platform-specific data
    extraction_status: str            # see §8.3
    evidence_level: str               # see §8.4
    error_category: str | None        # "auth_required" | "rate_limited" | "timeout" | "size_exceeded" | "not_found" | "unsupported" | None
    user_context: str | None          # text Drake included with the URL
```

### 6.3 Platform detection (URL normalization)

| Platform | Recognized patterns |
|----------|-------------------|
| Instagram Reel | `instagram.com/reel/`, `instagram.com/p/` |
| TikTok | `tiktok.com/@*/video/*`, `vm.tiktok.com/*` (short-link expand) |
| YouTube | `youtube.com/watch`, `youtu.be/`, `youtube.com/shorts/` |
| Article | All other HTTP/HTTPS URLs |
| Unknown | Non-HTTP strings |

Short-link expansion (TikTok `vm.tiktok.com`) uses a HEAD request with redirect following, no cookies.

---

## 7. yt-dlp Extraction

### 7.1 Installation

Add to `pyproject.toml` dependencies:
```
yt-dlp>=2024.1.0
```

Pin major version. Do not auto-update. Document intentional upgrade path.

### 7.2 Configuration (new env vars)

```
SOCIAL_MEDIA_DOWNLOAD_ENABLED=false
SOCIAL_MEDIA_MAX_DURATION_SECONDS=900
SOCIAL_MEDIA_MAX_FILE_MB=200
SOCIAL_MEDIA_DOWNLOAD_TIMEOUT_SECONDS=120
SOCIAL_MEDIA_RETRY_LIMIT=1
```

Default is `false` — production downloading is disabled until explicitly enabled. Set to `true` in `.env` after VPS testing is complete.

Add to `config.py` with these defaults. Add `.env.example` entries.

### 7.3 Subprocess safety rules

- Always use argument arrays (`subprocess.run([...], ...)`) — never shell string interpolation.
- Never execute filenames, captions, titles, or metadata as shell instructions.
- Never pass user-controlled values directly into argument positions that accept shell metacharacters.
- Validate the output file path after download (must be inside the temp directory).

### 7.4 Extraction flow

```
1. Create isolated temp directory (platform_<uuid>)
2. yt-dlp --extract-audio --audio-format mp3
         --max-filesize <max_mb>M
         --match-filter "duration < <max_sec>"
         --no-playlist
         --timeout <timeout_sec>
         -o <tempdir>/audio.%(ext)s
         <normalized_url>
3. On success: set audio_path, extraction_status = "downloaded"
4. On timeout: error_category = "timeout", extraction_status = "failed"
5. On size exceeded: error_category = "size_exceeded"
6. On auth required: error_category = "auth_required"
7. On rate limit: error_category = "rate_limited", do not retry immediately
8. On any failure: extraction_status = "failed", preserve error_category
9. Delete temp directory after transcription (or on failure)
10. Never retain audio files unless explicit retention is configured
```

### 7.5 Retry behavior

`SOCIAL_MEDIA_RETRY_LIMIT=1`. On failure, record error_category. Do not retry `auth_required` or `rate_limited` without a configurable cooldown. A failed download must not retry the same URL within the same task run.

---

## 8. Transcription

Use the existing `TranscriptionProvider` interface (OpenAI Whisper). No new transcription provider is needed.

Pass `audio_path` to `transcriber.transcribe(audio_path)`. On success, set `transcript` and `extraction_status = "transcribed"`. On failure, set `extraction_status = "failed"` with error logged; proceed to fallback.

---

## 9. Analysis

Only executed when `evidence_level` is `"Verified Transcript"` or `"Verified Caption and Metadata"`.

**Evidence level assignment rules:**
- `Verified Transcript`: transcript obtained from Whisper transcription of downloaded audio
- `Verified Caption and Metadata`: caption obtained from platform page metadata (og:description, API response, or page scrape) — not from the URL string alone
- `Metadata Only`: only URL, platform, creator name from URL parsing, thumbnail
- `User Context`: user explained the content in their message; no platform content verified
- `Unverified Inference`: Claude reasoning from URL alone — **never set by default, never used for Summary/Adopt fields**

Input to `SynthesisAgent.run_synthesis()`:
- Transcript (if available)
- Caption (if available)
- Creator, title, platform, URL
- User context (if provided)
- Drake's classification context (from project_classifier)

Output maps to the artifact and Notion page as:
```
What It Says       → Summary field
Why It Matters     → Potential Application field
Key Ideas          → key_points
Action Items       → action_items
Adopt/Adapt/Archive/Needs Review → Adopt field
Project            → Project field
```

Do not populate `Why It Matters` or `Adopt` when `evidence_level` is `"Metadata Only"` or `"User Context"`.

---

## 10. Knowledge Vault Schema Extensions

Extend the existing `setup.py` schema with the following additional properties. Do not replace or break existing properties.

### New properties

| Field | Type | Values |
|-------|------|--------|
| Extraction Status | select | Metadata Only, Downloading, Downloaded, Transcribed, Analyzed, Needs Content, Failed |
| Evidence Level | select | Verified Transcript, Verified Caption and Metadata, Metadata Only, User Context, Unverified Inference |
| Transcript Available | checkbox | — |
| Adopt | select | Adopt, Adapt, Archive, Needs Review |

### Extend existing properties

**Source** — add options:
```
Instagram Reel
TikTok
YouTube
Social Post
Telegram Forward
URL
Uploaded Video
```

**Status** — add `Needs Review` if not already present.

### Mapping from Reel Intelligence fields

| Reel Intelligence | Knowledge Vault |
|------------------|-----------------|
| Title | Name |
| URL | Source URL |
| What | Summary |
| Why | Next Action (or body: Potential Application) |
| Adopt? (YES/MAYBE/NO) | Adopt (Adopt/Adapt/Archive/Needs Review) |
| Priority | (Tags or manual) |
| Tags | Tags |
| Date Saved | Captured At |
| Status | Status |
| Adopt Reason | Capture Context / body section |

"Reel Intelligence" becomes a **Notion filtered view** of the Knowledge Vault, filtered by `Source IN {Instagram Reel, TikTok}`.

---

## 11. No-Content Fallback

When `extraction_status` is `"Needs Content"` or `"Failed"` and no user context is available:

**Notion page state:**
- Extraction Status: Needs Content
- Evidence Level: Metadata Only
- Status: Needs Review
- Summary: leave blank
- Adopt: Needs Review

**Notion page body includes:**
```
## What is Known
- Platform: [platform]
- URL: [url]
- Creator: [if available]
- Caption: [if available]
- Captured: [date]

## What is Missing
- Transcript
- Visual content
- Reliable summary
- Adopt/Adapt decision
```

**Telegram reply:**
```
Saved [platform] and available metadata, but could not access the video.
Forward the video, send a screen recording, or tell me why you saved it
so I can complete the analysis.
Task: [task_id]
```

---

## 12. User-Provided Context

Detect user context in the message when a URL is accompanied by explanation text (e.g. "save this reel, I like how they do X"). Store the non-URL portion as `user_context` on `MediaCaptureResult`.

- If user context present + no transcript → `evidence_level = "User Context"`
- Populate Summary/Why with user context clearly prefixed: `[User context] ...`
- Allows classification and routing even without video content
- Never merge user context into `Summary` without a label indicating its source

---

## 13. Duplicate Prevention

**Deduplication key**: `platform + ":" + platform_content_id`
- Instagram: `instagram_reel:<reel_id>` (extracted from URL)
- TikTok: `tiktok:<video_id>`
- YouTube: `youtube:<video_id>`
- Article: `url:<normalized_url>`

Before creating a new Notion page, check `NotionSyncRepository.get_by_idempotency_key()`. If found:
- Do not create a duplicate page
- Attach new user context to the existing record (Notion page body append)
- Return the existing page URL in ProcessResult
- Telegram reply: "Already saved. Updated with your new context."

---

## 14. Authentication & Cookies

- No platform credentials required for first version
- `auth_required` error category recorded when download fails due to login wall
- Existing `reel-intelligence/sync.py` cookie scraper: **isolated, not imported, not run as a daemon**
- Future cookie support, if added:
  - Disabled by default (`SOCIAL_MEDIA_INSTAGRAM_COOKIES_ENABLED=false`)
  - Cookie file path set via env var, outside Git, `600` permissions
  - Immediate disable mechanism via env var
  - Cookie failure must not stop Telegram or Notion workflows

---

## 15. Migration Table (reel_analyzer.py and sync.py)

| Component | Current purpose | Decision | Destination |
|-----------|----------------|----------|-------------|
| Notion DB schema (Reel Intelligence) | Field definitions | Reuse, mapped | Knowledge Vault via §10 mapping |
| `push_to_notion()` logic | Create Notion pages | Rewrite | `NotionSyncService` (already exists) |
| `analyze_reel()` URL-only Claude speculation | Fake reel summary | **Retire as default** | Disabled; `evidence_level = Unverified Inference` label only |
| `find_or_create_database()` | DB creation | Rewrite | `--setup-notion` CLI command (already exists) |
| `NOTION_TOKEN`, API headers | Auth pattern | Reuse concept | `integrations/notion/live_client.py` (already exists) |
| `sync.py` Instagram cookie scraping | Automated saves sync | **Defer + isolate** | Not imported; reviewed later |
| `sync.py` deduplication via `seen_media_ids` | Prevent re-sync | Reuse concept | `NotionSyncRepository.get_by_idempotency_key()` |
| `DRAKE_CONTEXT` profile string | Personalization | Replace | `project_classifier` + user context field |

---

## 16. First Milestone Scope (This Session)

Implement only:

1. `content/social/base.py` — `MediaCaptureResult`, `SocialAdapter` ABC
2. `content/social/router.py` — `PlatformRouter` (URL identification, normalization)
3. `content/social/instagram.py` — metadata-only adapter (no download)
4. `content/social/tiktok.py` — metadata-only adapter (no download)
5. `content/social/youtube.py` — metadata-only adapter (no download)
6. `content/social/generic.py` — article/unknown fallback
7. `workflows/capture_media.py` — `CaptureMediaWorkflow` with yt-dlp interface (download disabled by default), fallback, synthesis gating
8. Config additions: 5 new env vars in `config.py` and `.env.example`
9. Knowledge Vault schema extensions (§10) — extend `setup.py` only; do not re-run against production DB
10. `orchestration.py` — wire `save_link` → `CaptureMediaWorkflow`
11. Tests (see §17)
12. Docs: `docs/social-media-capture.md`

**Not in first milestone:**
- Live yt-dlp downloads enabled in production
- Cookie-based Instagram scraping
- Migration of existing Reel Intelligence Notion records
- Visual/frame analysis
- Short-link expansion for vm.tiktok.com (placeholder only)

---

## 17. Tests

All external services (yt-dlp, Whisper, Notion, platform sites) mocked.

| Test | Category |
|------|----------|
| Instagram Reel URL recognized | Platform routing |
| Instagram URL normalized (igsh params stripped) | Platform routing |
| TikTok URL recognized | Platform routing |
| TikTok short-link → resolution attempted | Platform routing |
| YouTube Shorts URL recognized | Platform routing |
| Article URL → generic adapter | Platform routing |
| Unknown non-HTTP string → unknown platform | Platform routing |
| Duplicate URL detected via idempotency key | Dedup |
| Duplicate → existing page returned, no new page | Dedup |
| Metadata fetch succeeds → extraction_status = Metadata Only | Metadata |
| Media download succeeds (mocked) → extraction_status = Downloaded | Extraction |
| Download timeout → error_category = timeout, task not failed | Extraction |
| File size exceeded → error_category = size_exceeded | Extraction |
| Duration exceeded → error_category = size_exceeded | Extraction |
| Auth required → error_category = auth_required, no retry | Extraction |
| Rate limit → error_category = rate_limited, no retry | Extraction |
| Transcription success → extraction_status = Transcribed, transcript set | Transcription |
| Transcription failure → fallback page, task not failed | Transcription |
| Metadata-only fallback → correct Notion page state | Fallback |
| User context fallback → evidence_level = User Context | Fallback |
| No speculative summary when evidence_level = Metadata Only | Evidence gating |
| evidence_level = Unverified Inference never set by default | Evidence gating |
| Notion property mapping → correct field values | Notion |
| Existing-page update when duplicate | Notion |
| Temp audio file deleted after transcription | Cleanup |
| Temp file deleted on download failure | Cleanup |
| No credential or cookie leakage in logs | Security |
| No subprocess shell interpolation | Security |
| Existing Telegram save_note flow unaffected | Regression |
| Existing Notion sync flow unaffected | Regression |
| Token count tracked through CaptureMediaWorkflow | Cost tracking |

---

## 18. Parallel-Development Conflict Assessment

The Notion session (Session 5, master branch) owns:
- `integrations/notion/` — all files
- `models/database.py` — NotionSyncORM
- `models/schemas.py` — NotionSyncCreate
- `storage/repositories.py` — NotionSyncRepository
- `services/orchestration.py` — notion_sync_service wiring
- `channels/telegram.py` — /notion, /sync commands
- `config.py` — notion_enabled, notion_api_token, notion_db_id

This spec owns:
- `content/social/` — new directory, no conflicts
- `workflows/capture_media.py` — new file, no conflicts
- `integrations/notion/setup.py` — extend schema properties only; no wholesale replacement
- `config.py` — add 5 new env vars; no changes to Notion vars
- `services/orchestration.py` — change `save_link` target workflow; touch one line in `_execute_workflow`

**Conflict risk**: low. `orchestration.py` and `setup.py` will need a clean merge. Use `feature/social-media-capture` branch and merge after Session 5 changes are stable.

---

## 19. Docs

Create `docs/social-media-capture.md` covering:
- How to send a URL or reel to D.R.A.K.E.
- What D.R.A.K.E. can and cannot do with each platform
- How to enable yt-dlp downloads
- Evidence level definitions
- How to complete an incomplete capture (Needs Content)
- Cookie scraping: why it is deferred and how to enable it safely if needed
