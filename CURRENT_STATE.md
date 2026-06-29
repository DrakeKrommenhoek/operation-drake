# CURRENT_STATE.md

Last updated: 2026-06-29 (Session 3 — pre-deployment close)

## Verified Facts

### Local Environment
- Python 3.12.10
- Docker 29.2.1
- Docker Compose v5.0.2
- Git 2.52.0
- OS: Windows 11 (development machine)

### Repository Status
- Location (local): `C:\Users\drake\Desktop\operation-drake\`
- GitHub: `https://github.com/DrakeKrommenhoek/operation-drake.git`
- Branch: `master`
- Latest commit: `75c21f8 fix: auto-create db directory, localhost-only port, non-root container user`
- Git working tree: clean
- Local and remote are in sync

### Local Application Status
- **95 tests pass**, zero failures, zero warnings
- `ruff check`: all checks passed
- `ruff format --check`: all files formatted
- `docker compose config`: validates cleanly
- `python -m operation_drake.main --check`: all checks passed (openai, openai_whisper)

### VPS Status (DigitalOcean, Ubuntu 24.04 LTS)

**Verified:**
- Hostname: `drake`, accessible via `ssh drake-vps`
- Ubuntu 24.04.4 LTS
- 67 GB disk, 1.9 GB RAM
- 1 GB swap added and persisted in `/etc/fstab`
- Docker 29.6.1 and Docker Compose v5.2.0 installed
- Only services running: SSH, DigitalOcean agent, standard Ubuntu services
- No conflicting applications found
- User `drake` (UID 1000) exists and is in the `docker` group

**Repository on VPS:**
- Location: `/opt/operation-drake/`
- Owner: `drake:drake`, permissions `750`
- Deployed commit: `75c21f8` (matches local and GitHub)

**Persistent data directories (created, owned by drake:drake):**
- `/opt/operation-drake/data/database/`
- `/opt/operation-drake/data/artifacts/`
- `/opt/operation-drake/data/inbox/`
- `/opt/operation-drake/backups/`

**Production `.env`:**
- Location: `/opt/operation-drake/.env`
- Owner: `drake:drake`, permissions `600`
- `TELEGRAM_BOT_TOKEN` — SET
- `TELEGRAM_ALLOWED_USER_IDS` — SET
- `OPENAI_API_KEY` — SET
- `OPENAI_WHISPER_API_KEY` — SET
- `DEFAULT_LLM_PROVIDER=openai` — SET, exactly 1 definition
- `DEFAULT_TRANSCRIPTION_PROVIDER=openai_whisper` — SET, exactly 1 definition
- Secret values were never displayed, logged, or committed

**NOT YET DONE:**
- Docker image build not attempted
- Containers not started
- Health endpoint not tested on VPS
- Persistence and restart not verified
- Live Telegram messages not tested
- Unauthorized-user test not run
- Operational scripts not validated against VPS
- No backup performed yet

## Credentials Needed

All production credentials are now in `/opt/operation-drake/.env` on the VPS.
Local `.env` contains working credentials for local development.
Neither file is committed to Git.

## Recent Changes (Sessions 1–3)

### Session 1 — Foundation
- Full project scaffold, schemas, ORM, repositories, LLM/transcription abstractions
- Five workflows, orchestration service, CLI and Telegram adapters, FastAPI app
- 41 tests

### Session 2 — Audit and Corrections
- Renamed package `personal_agent_os` → `operation_drake`
- Full approval loop: `/approve`, `/reject`, `/correct`, `/task`, `/inbox`
- `TELEGRAM_ALLOWED_USER_IDS` auth guard
- `--check` diagnostic command
- Dead code removed
- 56 tests

### Session 3 — Telegram Fixes and Pre-Deployment
- Fixed root cause of Telegram `BadRequest`: `_safe_text()` no longer strips characters; plain text used throughout with no `parse_mode`
- `_split_message()` added for 4,096-character Telegram limit
- Fixed `.env` duplicate key bug (mock overriding openai)
- Provider factories raise `ValueError` on unknown provider names (no silent mock fallback)
- `init_db()` auto-creates database directory
- `docker-compose.yml`: port 8000 bound to `127.0.0.1` only
- `Dockerfile`: non-root `drake` user (UID 1000)
- VPS prepared: Docker installed, user configured, directories created, swap added, repo cloned, `.env` configured
- 95 tests

## Next Milestone

**Deploy and validate.** Resume with:

```
Continue Operation D.R.A.K.E. deployment from CURRENT_STATE.md.
VPS is prepared. Repository is at /opt/operation-drake. Production .env is configured.
Begin at Step 6: build the Docker image, start containers, verify health endpoint, confirm OpenAI is active, and run live Telegram validation.
```
