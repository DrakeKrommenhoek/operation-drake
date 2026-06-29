# Operation Drake

A personal AI agent OS. Send a message — it figures out what you want and handles it.

## What It Does Now

- Receives text messages, URLs, voice notes, and forwarded messages through Telegram or the CLI.
- Stores the original message and metadata in SQLite.
- Transcribes voice notes (mock in testing; OpenAI Whisper in production).
- Detects and normalizes URLs.
- Classifies your likely intent using an LLM.
- Creates a task record with a full status lifecycle.
- Executes safe workflows automatically:
  - Save a note
  - Summarize text
  - Extract action items
  - Create a research brief
  - Capture a link
  - Transcribe and summarize a voice note
- Saves results as Markdown artifacts.
- Returns the result through the original channel.
- Flags anything non-trivial for your approval before acting.

## Message Processing Flow

```
You send a message (Telegram or CLI)
    → Message stored in SQLite
    → Content normalized (stripped, URL-detected, type classified)
    → Router agent classifies intent + confidence
    → Task record created
    → If approval needed: pauses and asks you
    → If safe: workflow executes automatically
    → Markdown artifact saved to data/artifacts/
    → Result returned to you
```

## Running Locally

```bash
# Install
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env — see "Credentials" section below

# Initialize the database and start the API
python -m personal_agent_os.main

# Health check
curl http://localhost:8000/health

# Interactive CLI (no Telegram needed)
python -m personal_agent_os.main --channel cli
```

## Connecting Telegram

1. Message [@BotFather](https://t.me/BotFather) on Telegram and create a new bot.
2. Copy the bot token into `.env` as `TELEGRAM_BOT_TOKEN=`.
3. Start the Telegram adapter:
   ```bash
   python -m personal_agent_os.main --channel telegram
   ```
4. Message your bot. It uses long polling — no domain or webhook required.

## Credentials You Need to Add

| Variable | Required For | Where to Get It |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram messages | @BotFather on Telegram |
| `ANTHROPIC_API_KEY` | Live LLM (Claude) | console.anthropic.com |
| `OPENAI_API_KEY` | Live LLM (GPT) or Whisper | platform.openai.com |
| `OPENAI_WHISPER_API_KEY` | Voice transcription | Same as OpenAI key |

**Without any keys:** The system runs with mock providers. All tests pass. No API calls are made.

**With `ANTHROPIC_API_KEY`:** Set `DEFAULT_LLM_PROVIDER=anthropic` in `.env`.

## Running Tests

```bash
make test        # all tests
make lint        # ruff check
make check       # lint + tests
```

## Docker

```bash
cp .env.example .env   # fill in your values
docker compose up -d   # starts API + Telegram adapter
docker compose logs -f
```

## Reviewing Tasks and Artifacts

- **API:** `GET /tasks` and `GET /tasks/{id}`
- **Artifacts:** `data/artifacts/` — Markdown files named `{task_id}_{title}.md`
- **Database:** `data/database/agent.db` (SQLite, inspectable with any SQLite viewer)

## VPS Deployment

See [docs/vps-deployment.md](docs/vps-deployment.md) for step-by-step instructions.

## What's Planned Next

See [ROADMAP.md](ROADMAP.md).
