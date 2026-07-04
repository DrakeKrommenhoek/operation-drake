# Social Media & URL Capture — Design Spec (Revised)
_Session 6 · D.R.A.K.E. Second Workflow_
_Date: 2026-07-04 · Revision: 2_

---

## 1. Goal

Enable Drake to forward or paste an Instagram Reel, TikTok, YouTube video, or article URL in Telegram and receive a structured, evidence-grounded summary saved to the D.R.A.K.E. Knowledge Vault and returned as a Telegram reply.

D.R.A.K.E. must never claim to understand a video's content based only on its URL or Drake's profile context. All claims must be grounded in verified evidence. The visual-content limitation applies throughout: a transcript or caption does not establish on-screen text, physical demonstrations, visual design, charts, or editing techniques.

---

## 2. Context

### 2.1 Existing project: Reel Intelligence

`~/reel_analyzer.py` and `~/reel-intelligence/` implement an earlier version:
- `reel_analyzer.py`: standalone script, URL-only Claude speculation → Notion. **Retire speculative default.**
- `reel-intelligence/sync.py`: daemon scraping Instagram saves via browser session cookies → Notion. **Defer + isolate.**

See §16 migration table.

### 2.2 Existing D.R.A.K.E. Notion integration (Session 5, master `0cbb27c`)

The Knowledge Vault foundation is complete on master:
- `integrations/notion/` — classifier, mapper, body_builder, sync_service, live_client, mock_client
- `NotionSyncORM` + `NotionSyncRepository` — idempotency, retry, outbox
- 16-property Knowledge Vault schema in `integrations/notion/setup.py`
- `NOTION_ENABLED=false` default; `--setup-notion` CLI command
- 193 tests passing

This spec extends that foundation. There is **one production Notion sync path**: through `OrchestratorService`. `CaptureContentWorkflow` must not create Notion pages directly.

---

## 3. Architecture Overview

```
Telegram URL message
  → TelegramAdapter._handle_text()
  → OrchestratorService.process()     [intent: save_link]
  → CaptureContentWorkflow.run()
      → ProtectedURLResolver.resolve(url)     # SSRF-safe, all redirects
      → PlatformRouter.identify(url)          # platform, content_id
      → CapturedSourceRepository.get_or_create()   # local dedup
      → SocialAdapter.fetch_metadata()        # caption, creator, title
      → SubtitleAdapter.fetch_subtitles()     # try platform subs first
      → YtdlpExtractor.extract() [if enabled] # audio download
      → TranscriptionProvider.transcribe()    # Whisper
      → SynthesisAgent.analyze()             # only on verified evidence
      → ArtifactService.save()               # local markdown artifact
      → return ContentCaptureResult
  → ProcessResult returned to Orchestrator
  → existing NotionClassifier + NotionSyncService  # unchanged path
  → _format_result() → Telegram reply
```

**Every external network stage is best-effort.** Only URL validation, local persistence, and a truthful fallback are required for task completion. A stage failure produces a structured fallback record, not a task failure.

---

## 4. Feature Branch

```
feature/social-media-capture
```

Branch setup before any implementation:
```bash
git checkout -b feature/social-media-capture
git fetch origin
git rebase origin/master
```

Confirm master contains the completed Notion integration (`0cbb27c`) before touching `orchestration.py`, `setup.py`, `config.py`, or any Notion mapping.

Do not merge to master until:
1. This spec's test suite passes cleanly.
2. Notion schema extensions are reconciled with the existing 16-property schema.
3. No live downloading is deployed.

---

## 5. Intent Wiring

Keep `save_link` as the intent name (no router churn). Replace its execution target from `CaptureNoteWorkflow` → `CaptureContentWorkflow` in `orchestration._execute_workflow()`. Existing behavior for save_link (note capture of link text when URL fetching fails) must remain as the fallback, not be removed.

---

## 6. Platform Identification & Canonicalization

Location: `src/operation_drake/content/social/`

### 6.1 File structure

```
content/social/base.py      — ContentCaptureResult, SocialAdapter ABC, EvidenceProvenance
content/social/resolver.py  — ProtectedURLResolver (SSRF-safe)
content/social/router.py    — PlatformRouter: identify + normalize
content/social/instagram.py — metadata adapter
content/social/tiktok.py    — metadata adapter
content/social/youtube.py   — metadata adapter + subtitle fetch
content/social/generic.py   — article/unknown fallback
```

### 6.2 Platform recognition

| Platform | Recognized patterns | Content type |
|----------|-------------------|--------------|
| `instagram_reel` | `instagram.com/reel/<id>/` | Social video |
| `instagram_post` | `instagram.com/p/<id>/` | May be image, video, or carousel — do not assume reel |
| `tiktok` | `tiktok.com/@*/video/*`, `vm.tiktok.com/*` | Social video |
| `youtube` | `youtube.com/watch?v=*`, `youtu.be/*`, `youtube.com/shorts/*` | Social video |
| `article` | All other HTTP/HTTPS | Article |
| `unknown` | Non-HTTP/HTTPS strings | Reject |

`instagram.com/p/` routes to `instagram_post`. Metadata may later indicate whether a post is video or image. Do not assume video content.

### 6.3 TikTok short-link expansion

Expand `vm.tiktok.com/*` short links using `ProtectedURLResolver`. Derive canonical video ID from the resolved URL. This is required for deduplication correctness. Test with mocked redirects.

### 6.4 ContentCaptureResult

```python
@dataclass
class ContentCaptureResult:
    # Identity
    normalized_url: str
    platform: str
    platform_content_id: str | None
    source_key: str                     # e.g. "instagram_reel:DWyD5gl..."
    creator: str | None
    title: str | None
    published_at: str | None
    thumbnail_url: str | None           # URL only; never fetched without SSRF check

    # Content fields — kept strictly separate
    content_summary: str | None         # from verified evidence only
    user_reason_for_saving: str | None  # Drake's stated reason
    potential_application: str | None   # from verified evidence only
    user_context: str | None            # full raw text Drake provided

    # Evidence
    caption: str | None                 # platform caption/description
    caption_source: str | None          # "platform_metadata" | "og_tag" | None
    transcript: str | None              # Whisper or platform subtitle
    transcript_source: str | None       # "whisper" | "platform_subtitles" | None
    metadata_source: str | None         # "og_tags" | "yt-dlp_info" | "scrape" | None
    evidence_sources: list[str]         # all sources actually used
    evidence_level: str                 # see §9
    visual_evidence_available: bool     # always False until frame analysis is added

    # Pipeline state (runtime only — never persisted to DB or artifact)
    metadata_status: str                # "ok" | "partial" | "failed"
    download_status: str                # "skipped" | "ok" | "failed" | "disabled"
    transcription_status: str           # "skipped" | "ok" | "failed"
    analysis_status: str                # "ok" | "skipped" | "failed"
    failure_stage: str | None           # first stage that failed; None on clean run
    error_category: str | None          # see §11.4

    # Ephemeral paths — runtime only; set to None after cleanup
    _audio_path: str | None             # deleted after transcription or on failure
    _media_path: str | None             # deleted after audio extraction or on failure

    # Classification hints for NotionClassifier — not authoritative
    suggested_project: str | None       # passed as hint, classifier decides
    suggested_content_type: str | None
```

`_audio_path` and `_media_path` are runtime-only. They must be set to `None` after cleanup and must never be written to SQLite, artifact markdown, or Notion.

---

## 7. SSRF-Safe URL Resolver

All external HTTP calls — metadata fetch, redirect following, short-link expansion, thumbnail existence checks — must go through `ProtectedURLResolver`.

### 7.1 Rules

- Allow only `http://` and `https://` schemes. Reject `file:`, `ftp:`, `data:`, and all others.
- Reject URLs with embedded usernames or passwords (`user:pass@host`).
- Reject localhost (`127.0.0.0/8`, `::1`).
- Reject private IPv4 ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
- Reject IPv6 private/link-local: `fc00::/7`, `fe80::/10`.
- Reject loopback: `127.0.0.1`, `[::1]`, `localhost`.
- Reject cloud metadata endpoints: `169.254.169.254`, `fd00:ec2::254`, and equivalents.
- Resolve DNS before the request. Recheck the resolved IP on every redirect.
- Strict redirect limit: 5.
- Connection timeout: 10 seconds. Response timeout: 30 seconds.
- Maximum response body: 5 MB for metadata; 0 bytes for HEAD; bounded GET fallback for HEAD-refusing servers.
- Accepted content types for article extraction: `text/html`, `text/plain`, `application/xhtml+xml`.
- Do not use HEAD exclusively — some servers reject it. Use bounded GET or HEAD-with-GET-fallback.
- Log only safe error categories (never raw URLs containing credentials or tokens).

### 7.2 DNS rebinding defense

After every redirect, re-resolve the destination hostname and re-apply IP blocklist rules. Do not trust cached DNS results across redirects.

### 7.3 Tests

Include dedicated SSRF tests:
- Direct localhost reject
- Direct private IP reject
- Redirect to localhost reject
- Redirect to private IP reject
- Redirect to `169.254.169.254` reject
- Scheme injection reject (`file://`, `ftp://`)
- Credential-in-URL reject
- Redirect loop reject (>5 hops)
- TikTok short-link expansion via protected resolver (mocked)

---

## 8. Evidence Priority Order

For supported platforms, attempt evidence in this order. Stop at the first successful source:

```
1. Platform subtitles or auto-generated captions (yt-dlp --write-subs, YouTube)
2. Audio download → Whisper transcription
3. Platform caption / description (og:description, page metadata)
4. User context (Drake's message text)
5. Metadata only (URL, platform, creator, title)
```

Clearly distinguish:
- Platform speech transcript or subtitles → `transcript_source = "platform_subtitles"`
- Whisper-generated transcript → `transcript_source = "whisper"`
- Post caption or description → `caption_source = "platform_metadata"` (not a speech transcript)

A post caption is not a speech transcript. Do not represent it as one.

---

## 9. Evidence Level Rules

| Level | Condition | May populate |
|-------|-----------|-------------|
| `Verified Transcript` | Whisper transcript or platform subtitles obtained | content_summary, key_ideas, potential_application, Adopt recommendation |
| `Platform Caption and Metadata` | Caption obtained from platform metadata (og:description, API, scrape) — not URL text alone | content_summary (caption-based, labeled as such), key_ideas (caption-based) |
| `Metadata Only` | URL, platform, creator from URL parsing + og:title/thumbnail | Name, Source URL, creator, title only |
| `User Context` | Drake provided explanation text; no platform content verified | user_reason_for_saving, user_context, Project classification, Tags |
| `Unverified Inference` | Claude reasoning from URL + profile alone | **Never set by default. Never used for any content field.** |

**Default Adopt = Needs Review** unless Drake explicitly provides a decision.

Analysis labeled `"Platform Caption and Metadata"` must state in the Notion body that it is caption-based, not transcript-based.

---

## 10. Content Field Separation

Four distinct fields. Never blend without labeling:

| Field | Populated by | Source |
|-------|-------------|--------|
| `content_summary` | Verified transcript or platform caption only | What the content actually says |
| `user_reason_for_saving` | Drake's message text | Why Drake saved it |
| `potential_application` | Synthesis from verified evidence | How it applies to Drake's work |
| `user_context` | Drake's message text (full) | Drake's stated context |

**Notion page body sections:**
```
## Verified Content
[content_summary — only if evidence_level >= Platform Caption and Metadata]

## Drake's Context
[user_reason_for_saving, user_context]

## D.R.A.K.E. Analysis
[potential_application, key_ideas, action_items — only if evidence supports it]
```

Do not populate "Verified Content" from user context. Do not populate "Drake's Context" from platform data.

**Visual limitation statement** — include when material:
```
Analysis is transcript-led. On-screen text, demonstrations, visual design, and 
editing techniques are not captured. visual_evidence_available = false.
```

---

## 11. Pipeline Stage Model

### 11.1 Stage fields (runtime state in ContentCaptureResult)

```
metadata_status       "ok" | "partial" | "failed"
download_status       "skipped" | "ok" | "failed" | "disabled"
transcription_status  "skipped" | "ok" | "failed"
analysis_status       "ok" | "skipped" | "failed"
failure_stage         first failing stage name or None
```

A transcription failure preserves successful metadata and caption. Stage fields communicate exact state without overwriting each other.

### 11.2 High-level Notion terminal status

One `Extraction Status` Notion property with terminal values only:

```
Analyzed             — transcript or caption + analysis complete
Caption Only         — caption available, no transcript
Transcript Available — transcript available, analysis pending or incomplete
Needs Content        — metadata only, no caption or transcript
Failed               — no useful evidence retrieved
```

Transient in-progress states (`Downloading`, `Transcribing`) remain local. Do not write them to Notion unless a demonstrated async need arises.

### 11.3 Notion terminal status derivation

```
analysis_status = "ok"                                → Analyzed
transcript present, analysis_status != "ok"           → Transcript Available
caption present, download_status != "ok"              → Caption Only
all content stages failed or skipped, metadata ok     → Needs Content
metadata_status = "failed"                            → Failed
```

### 11.4 Error categories

```
invalid_url           blocked_url           metadata_failed
auth_required         rate_limited          timeout
network_error         duration_exceeded     size_exceeded
not_found             unsupported           ffmpeg_missing
transcription_failed  analysis_failed
```

`duration_exceeded` and `size_exceeded` are separate. Do not conflate them.

---

## 12. yt-dlp Extraction

### 12.1 Dependency

Use the Python API (`yt_dlp.YoutubeDL`) — not subprocess output parsing. This avoids stdout format instability.

Pin an exact tested version, e.g. `yt-dlp==2025.6.9`. Document a deliberate upgrade process: test against known URLs in a staging environment before bumping. Do not auto-update from inside the running application.

### 12.2 Configuration

```
SOCIAL_MEDIA_DOWNLOAD_ENABLED=false
SOCIAL_MEDIA_MAX_DURATION_SECONDS=900
SOCIAL_MEDIA_MAX_FILE_MB=200
SOCIAL_MEDIA_DOWNLOAD_TIMEOUT_SECONDS=120
SOCIAL_MEDIA_RETRY_LIMIT=1
```

Default `false`. Production downloading disabled until explicitly enabled.

### 12.3 ffmpeg / ffprobe requirement

Audio extraction requires `ffmpeg` and `ffprobe` binaries. Add diagnostics:

```
yt-dlp installed
ffmpeg installed
ffprobe installed
download feature enabled
```

Expose in `--check` diagnostic output. If `ffmpeg` is missing and download is enabled, record `error_category = "ffmpeg_missing"` and fall back gracefully.

### 12.4 Extraction behavior

```python
ydl_opts = {
    "format": "bestaudio/best",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
    "outtmpl": str(tempdir / "audio.%(ext)s"),
    "noplaylist": True,
    "max_filesize": max_file_bytes,
    "match_filter": yt_dlp.utils.match_filter_func(
        f"duration <= {max_duration_seconds}"
    ),
    "socket_timeout": download_timeout_seconds,
    "retries": retry_limit,
    "fragment_retries": 1,
    "ignoreerrors": False,
    "quiet": True,
    "no_warnings": False,
    "ignore_config": True,
}
```

Validate the output file path after download — it must be under the temp directory. Reject any path outside it.

### 12.5 Cleanup

Delete the temp directory (and all contained files) on:
- Transcription success
- Download failure
- Transcription failure
- Cancellation or timeout
- Any unhandled exception (use `finally:`)

After cleanup, set `_audio_path = None` and `_media_path = None`. Never persist these paths.

### 12.6 Retry

Do not retry `auth_required` or `rate_limited` within the same task run. Honor `SOCIAL_MEDIA_RETRY_LIMIT`.

---

## 13. Transcription Integration

Use the existing `TranscriptionProvider` interface. No new provider needed.

Try platform subtitles before Whisper (§8). Pass `audio_path` to `transcriber.transcribe()` only when subtitles are unavailable. On transcription failure, record `transcription_status = "failed"`, `error_category = "transcription_failed"`, and fall to next evidence tier.

---

## 14. Analysis Gating

`SynthesisAgent.run_synthesis()` is called only when `evidence_level` is `Verified Transcript` or `Platform Caption and Metadata`.

`SynthesisAgent` scope: "what it says, key ideas, potential application, adopt recommendation." It does **not** assign Project, Content Type, or Capture Context. Pass `suggested_project` from analysis as a hint only.

`NotionClassifier` scope (existing, unchanged): Project, Content Type, Capture Context, Tags, sync decision. It receives the hint and may accept or override it. Explicit user project instructions remain authoritative.

---

## 15. Local Source Deduplication

`NotionSyncRepository` idempotency key (`notion:{task_id}`) is task-scoped. The same Reel can arrive via multiple tasks. Local source identity is required.

### 15.1 CapturedSourceORM

New ORM model:

```python
class CapturedSourceORM(Base):
    __tablename__ = "captured_sources"
    id = Column(String, primary_key=True)
    source_key = Column(String, unique=True, nullable=False)   # e.g. "instagram_reel:DWyD5gl"
    platform = Column(String, nullable=False)
    platform_content_id = Column(String, nullable=True)
    normalized_url = Column(String, nullable=False)
    first_task_id = Column(String, nullable=False)
    canonical_artifact_id = Column(String, nullable=True)
    notion_page_id = Column(String, nullable=True)
    first_seen_at = Column(DateTime)
    last_seen_at = Column(DateTime)
    capture_count = Column(Integer, default=1)
```

### 15.2 CapturedSourceRepository

- `get_by_source_key(key)` — returns existing record or None
- `create(data)` — create new source
- `update_context(source_id, new_context, idempotency_key)` — append user context with its own idempotency key to prevent double-append on retry
- `update_notion_page_id(source_id, page_id)`

### 15.3 Deduplication keys

```
instagram_reel:<reel_id>
instagram_post:<post_id>
tiktok:<video_id>
youtube:<video_id>
url:<sha256(normalized_url)[:16]>   # articles and unknowns
```

### 15.4 Behavior on duplicate

A repeated capture creates a new intake task (audit trail) but points to the existing `CapturedSourceORM`. New user context appends to the existing Notion page. Returns the existing page URL in `ProcessResult`. Telegram reply confirms: "Already saved. Added your new context."

Deduplication works when Notion is disabled, when Notion is temporarily failing, and across container restarts.

---

## 16. Knowledge Vault Schema Extensions

Extend `integrations/notion/setup.py`. Never replace existing properties or property IDs.

### 16.1 New properties

| Field | Type | Values |
|-------|------|--------|
| Extraction Status | select | Analyzed, Caption Only, Transcript Available, Needs Content, Failed |
| Evidence Level | select | Verified Transcript, Platform Caption and Metadata, Metadata Only, User Context, Unverified Inference |
| Transcript Available | checkbox | — |
| Adopt | select | Adopt, Adapt, Archive, Needs Review |
| Visual Evidence Available | checkbox | — |

### 16.2 Extend existing properties

**Source** — add options:
```
Instagram Reel, Instagram Post, TikTok, YouTube, Social Post,
Telegram Forward, URL, Uploaded Video
```

**Status** — add `Needs Review` if absent.

### 16.3 Reel Intelligence filtered view

"Reel Intelligence" becomes a filtered view of the Knowledge Vault: `Source IN {Instagram Reel, Instagram Post, TikTok}`. Document the manual Notion step if the API does not support view creation.

### 16.4 Idempotent migration command

Extend `--setup-notion` (or add `--migrate-notion-schema`) to:
1. Inspect the existing schema via the Notion API.
2. Add only missing select properties and options — never duplicate.
3. Preserve existing property IDs and pages.
4. Support `--dry-run` (print planned changes without applying).
5. Report planned and completed changes.
6. Run only after a production backup.
7. Be tested with the mock Notion client.

---

## 17. Transcript and Notion-Size Controls

Full transcript → stored in local artifact only.

For Notion:
- Structured summary + bounded transcript excerpt (max 2,000 characters).
- Append in bounded block batches (Notion limits).
- If transcript exceeds excerpt limit, include a note: "Full transcript available in D.R.A.K.E. artifact [artifact_id]."
- Never silently truncate. State the limit was reached.
- Test with a long transcript (>10,000 characters).

---

## 18. No-Content Fallback

When no content evidence is available:

**Local artifact** includes:
```
## What is Known
- Platform: [platform]
- URL: [url]
- Creator: [if available, from verified metadata]
- Caption: [if available]
- Captured: [date]
- Error: [safe error category]

## What is Missing
- Transcript
- Visual content
```

**Notion page** (via Orchestrator → NotionSyncService):
- Extraction Status: Needs Content
- Evidence Level: Metadata Only
- Status: Needs Review
- Adopt: Needs Review
- content_summary: blank
- Visual Evidence Available: false

**Telegram reply** (when media download failed):
```
Saved [platform] link and available metadata, but could not access the video.
Tell me why you saved it so I can complete the analysis, or retry with a direct link.
Task: [task_id]
```

Do not say "forward the video" or "send a screen recording" until Telegram video/document intake is implemented and tested (roadmap item — see §21).

---

## 19. Authentication & Cookies

- No platform credentials required for first version.
- `auth_required` recorded in `error_category`.
- `reel-intelligence/sync.py`: isolated, not imported, not run.
- Future cookie support: disabled-by-default adapter, env var path, outside Git, `600` permissions, immediate disable mechanism. Cookie failure must not stop Telegram or Notion workflows.

---

## 20. Migration Table

| Component | Current purpose | Decision | Destination |
|-----------|----------------|----------|-------------|
| Notion field ideas (Reel Intelligence) | DB schema | Map to Knowledge Vault | §16 |
| `push_to_notion()` | Page creation | Retire | `NotionSyncService` (exists) |
| `analyze_reel()` URL-only speculation | Fake summary | **Retire as default** | `evidence_level=Unverified Inference`; never populated by default |
| `find_or_create_database()` | DB creation | Retire | `--setup-notion` (exists) |
| Notion auth pattern | HTTP client | Reuse concept | `live_client.py` (exists) |
| `sync.py` cookie scraping | Auto-save sync | **Defer + isolate** | Not imported |
| `sync.py` deduplication (`seen_media_ids`) | Prevent re-sync | Reuse concept | `CapturedSourceRepository` |
| `DRAKE_CONTEXT` profile string | Personalization | Replace | `project_classifier` + `user_context` field |

---

## 21. First Milestone Scope

Implement only:

1. `content/social/base.py` — `ContentCaptureResult`, `SocialAdapter` ABC, `EvidenceProvenance`
2. `content/social/resolver.py` — `ProtectedURLResolver` (SSRF-safe, all external fetches)
3. `content/social/router.py` — `PlatformRouter`: identify, normalize, TikTok short-link expansion
4. `content/social/instagram.py` — metadata adapter (no download)
5. `content/social/tiktok.py` — metadata adapter (no download)
6. `content/social/youtube.py` — metadata adapter + subtitle check
7. `content/social/generic.py` — article/unknown fallback (metadata + og-tag extraction via `ProtectedURLResolver`)
8. `models/database.py` — `CapturedSourceORM`
9. `storage/repositories.py` — `CapturedSourceRepository`
10. `workflows/capture_content.py` — `CaptureContentWorkflow` (branching social/article paths; yt-dlp disabled by default; returns `ContentCaptureResult` with classification hints; does NOT call NotionSyncService)
11. `config.py` — 5 new social-media env vars + yt-dlp/ffmpeg diagnostic support
12. `.env.example` — new env vars documented
13. `integrations/notion/setup.py` — extend schema (§16); add idempotent migration
14. `services/orchestration.py` — wire `save_link` → `CaptureContentWorkflow`; pass classification hints to `NotionClassifier`
15. Tests (§22)
16. `docs/social-media-capture.md`

**Not in first milestone:**
- Live yt-dlp downloads in production
- Cookie-based Instagram scraping
- Migration of existing Reel Intelligence Notion records
- Visual/frame analysis
- Telegram video/document upload intake
- Article full-text extraction beyond og-tags (roadmap)

---

## 22. Tests

All external services mocked (yt-dlp, Whisper, Notion, platform sites, DNS).

| Test | Category |
|------|----------|
| `instagram.com/reel/` → `instagram_reel` | Platform routing |
| `instagram.com/p/` → `instagram_post` (not reel) | Platform routing |
| Instagram URL normalized (igsh params stripped) | Platform routing |
| TikTok long URL → `tiktok` | Platform routing |
| TikTok short-link expanded via protected resolver (mocked) | Platform routing |
| YouTube Shorts URL → `youtube` | Platform routing |
| Article URL → generic adapter | Platform routing |
| Non-HTTP string → unknown, rejected | Platform routing |
| Localhost URL → SSRF reject | SSRF |
| Private IP URL → SSRF reject | SSRF |
| Redirect to localhost → SSRF reject | SSRF |
| Redirect to 169.254.169.254 → SSRF reject | SSRF |
| `file://` scheme → SSRF reject | SSRF |
| Credential-in-URL → SSRF reject | SSRF |
| >5 redirects → reject | SSRF |
| Same source_key → existing record returned | Source dedup |
| Duplicate with new context → appends, no second page | Source dedup |
| Idempotent context append (retry safe) | Source dedup |
| Dedup works with Notion disabled | Source dedup |
| Metadata fetch succeeds → metadata_status = ok | Metadata |
| Metadata fetch fails → metadata_status = failed, task not failed | Metadata |
| Platform subtitles preferred over Whisper | Evidence priority |
| Whisper used when no subtitles | Evidence priority |
| Caption used when no audio available | Evidence priority |
| No analysis when evidence_level = Metadata Only | Evidence gating |
| No analysis when evidence_level = User Context | Evidence gating |
| Unverified Inference never set by default | Evidence gating |
| content_summary blank when Metadata Only | Field separation |
| user_context not blended into content_summary | Field separation |
| visual_evidence_available = false always | Visual limitation |
| Default Adopt = Needs Review when no user decision | Adopt default |
| Download success (mocked) → download_status = ok | Extraction |
| Download disabled → download_status = disabled | Extraction |
| Download timeout → error_category = timeout, task not failed | Extraction |
| File size exceeded → error_category = size_exceeded | Extraction |
| Duration exceeded → error_category = duration_exceeded (not size_exceeded) | Extraction |
| Auth required → error_category = auth_required, no retry | Extraction |
| Rate limit → error_category = rate_limited, no retry | Extraction |
| Transcription success → transcript set, transcription_status = ok | Transcription |
| Transcription failure → fallback, task not failed | Transcription |
| _audio_path = None after cleanup | Cleanup |
| _media_path = None after cleanup | Cleanup |
| Temp files deleted on failure | Cleanup |
| Temp files deleted on exception | Cleanup |
| No audio_path in SQLite or artifact | Persistence |
| Notion terminal status derived correctly per §11.3 | Notion |
| NotionSyncService not called inside CaptureContentWorkflow | Notion boundary |
| Existing Orchestrator Notion path unchanged | Regression |
| Long transcript → bounded Notion excerpt + local artifact | Size limits |
| Schema migration adds only missing properties | Migration |
| Schema migration --dry-run prints plan, no changes | Migration |
| No credential or cookie in logs | Security |
| No shell interpolation | Security |
| Existing save_note flow unaffected | Regression |
| Existing Notion sync flow unaffected | Regression |
| Token count tracked through CaptureContentWorkflow | Cost tracking |
| ffmpeg missing → error_category = ffmpeg_missing, graceful fallback | Diagnostics |

---

## 23. Conflict Assessment (Updated)

The Notion foundation is complete on master at `0cbb27c`. This spec owns new files and targeted extensions only.

| File | Change | Risk |
|------|--------|------|
| `content/social/` | New directory | None |
| `models/database.py` | Add CapturedSourceORM | Low — additive |
| `storage/repositories.py` | Add CapturedSourceRepository | Low — additive |
| `workflows/capture_content.py` | New file | None |
| `config.py` | Add 5 env vars | Low — additive |
| `integrations/notion/setup.py` | Extend schema, add migration | Medium — coordinate |
| `services/orchestration.py` | save_link target + classifier hint | Low — one function |
| `channels/telegram.py` | No changes in this spec | None |

No second Notion client, sync service, database, or classification path.

---

## 24. Roadmap Items (Out of Scope)

- Article full-text extraction (beyond og-tags)
- Telegram video/document upload intake
- Visual/frame analysis (multimodal)
- Cookie-based authenticated Instagram access
- Reel Intelligence historical record migration
- Auto-suggest when evidence_level upgrades (e.g. after retry)

---

## 25. Docs

`docs/social-media-capture.md`:
- How to send a URL or reel to D.R.A.K.E.
- Evidence level definitions and what each unlocks
- Visual-content limitation
- How to complete an incomplete capture
- How to enable yt-dlp + ffmpeg on VPS
- Cookie scraping: why deferred, how to enable safely
- How to run `--migrate-notion-schema` safely (backup first)
