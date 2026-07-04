"""Telegram channel adapter.

Reply policy
------------
All text sent to Telegram uses plain text (no parse_mode). Without parse_mode,
Telegram treats every character literally: underscores, asterisks, backticks,
brackets, URLs, and filenames are safe and must be preserved unchanged.

_safe_text() is the send boundary — it ensures the text is a str and
performs no character stripping. _reply() handles message splitting for
Telegram's 4,096-character limit, sending multiple plain-text messages when
needed.
"""

import asyncio
import os
import tempfile

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from operation_drake.channels.base import ChannelAdapter
from operation_drake.config import get_settings
from operation_drake.llm import get_llm_provider
from operation_drake.observability.logging import get_logger
from operation_drake.services.orchestration import OrchestratorService
from operation_drake.storage.database import get_session
from operation_drake.storage.repositories import AgentRunRepository
from operation_drake.transcription import get_transcription_provider

# gpt-4o-mini blended cost rate (75% input at $0.15/1M, 25% output at $0.60/1M)
_COST_PER_TOKEN = 0.0000002625

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Text safety and message splitting
# ---------------------------------------------------------------------------

TELEGRAM_MAX_LEN = 4096


def _safe_text(text: str) -> str:
    """Return text unchanged for plain-text Telegram sending.

    No parse_mode is used, so Markdown characters (* _ ` [ ] and others)
    are rendered literally by Telegram. Stripping them would corrupt content
    such as filenames, URLs, intent names, and user-supplied text.

    This function exists as the explicit send boundary so callers signal that
    content safety has been considered. It makes no character modifications.
    """
    return text


def _split_message(text: str, max_len: int = TELEGRAM_MAX_LEN) -> list[str]:
    """Split text into chunks that each fit within max_len characters.

    Prefers splitting at the last newline within the window, then the last
    space. Falls back to a hard cut only when no whitespace exists in the
    window. The split delimiter is consumed and does not appear at the start
    of the next chunk.
    """
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    while len(text) > max_len:
        window = text[:max_len]
        cut = window.rfind("\n")
        if cut <= 0:
            cut = window.rfind(" ")
        if cut <= 0:
            # No whitespace in window — hard cut with no delimiter to consume
            chunks.append(text[:max_len])
            text = text[max_len:]
        else:
            chunks.append(text[:cut])
            text = text[cut + 1 :]  # consume the newline or space
    if text:
        chunks.append(text)
    return chunks


async def _reply(update: Update, text: str) -> None:
    """Send a plain-text reply, splitting across multiple messages if needed."""
    for chunk in _split_message(_safe_text(text)):
        await update.message.reply_text(chunk)


# ---------------------------------------------------------------------------
# Result formatting (plain text only)
# ---------------------------------------------------------------------------


def _format_result(result) -> str:
    lines = [
        f"Intent: {result.intent} ({result.confidence:.0%} confident)",
        f"Action: {result.proposed_action}",
        f"Status: {result.status}",
    ]
    if result.status == "awaiting_approval":
        if result.session_tokens:
            cost = result.session_tokens * _COST_PER_TOKEN
            lines.append(f"Session spend so far: ~${cost:.4f} ({result.session_tokens:,} tokens)")
        lines.append(f"Requires approval -- task {result.task_id}")
        lines.append(f"Use /approve {result.task_id} to execute")
        lines.append(f"Use /reject {result.task_id} to cancel")
    if result.clarification_question:
        lines.append(f"Question: {result.clarification_question}")
    if result.status == "completed" and result.result_summary:
        lines.append(f"Result: {result.result_summary}")
    if result.artifact_path:
        lines.append("Artifact saved.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator factory
# ---------------------------------------------------------------------------


def _make_orchestrator(artifacts_dir: str) -> OrchestratorService:
    return OrchestratorService(
        session=get_session(),
        llm=get_llm_provider(),
        transcriber=get_transcription_provider(),
        artifacts_dir=artifacts_dir,
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class TelegramAdapter(ChannelAdapter):
    channel_name = "telegram"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._app = Application.builder().token(self._settings.telegram_bot_token).build()
        self._setup_handlers()

    def send(self, text: str, reply_to: str | None = None) -> None:
        pass

    def _is_allowed(self, user_id: str) -> bool:
        return self._settings.is_user_allowed(user_id)

    def _setup_handlers(self) -> None:
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("approve", self._cmd_approve))
        self._app.add_handler(CommandHandler("reject", self._cmd_reject))
        self._app.add_handler(CommandHandler("correct", self._cmd_correct))
        self._app.add_handler(CommandHandler("task", self._cmd_task))
        self._app.add_handler(CommandHandler("inbox", self._cmd_inbox))
        self._app.add_handler(CommandHandler("projects", self._cmd_projects))
        self._app.add_handler(CommandHandler("cost", self._cmd_cost))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        self._app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
        self._app.add_error_handler(self._error_handler)

    # -----------------------------------------------------------------------
    # Error handler
    # -----------------------------------------------------------------------

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        error = context.error
        error_type = type(error).__name__
        # Log type and safe truncated message — never log token, keys, or message content
        logger.error(
            {"action": "telegram_error", "error_type": error_type, "detail": str(error)[:120]}
        )

        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    f"Something went wrong ({error_type}). "
                    "Your request was processed if it reached the workflow. "
                    "Check /inbox for any tasks awaiting approval."
                )
            except Exception:
                pass  # delivery failure — polling must continue

    # -----------------------------------------------------------------------
    # Commands
    # -----------------------------------------------------------------------

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        await _reply(
            update,
            "D.R.A.K.E. is online.\n"
            "Send me any message, voice note, or URL and I will handle it.\n\n"
            "/help -- commands\n/status -- system status\n/inbox -- pending approvals",
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        await _reply(
            update,
            "/start -- greet\n"
            "/status -- system status\n"
            "/inbox -- tasks awaiting approval\n"
            "/task <id> -- task details\n"
            "/approve <id> -- approve and execute a pending task\n"
            "/reject <id> -- reject a pending task\n"
            "/correct <id> <new instruction> -- re-interpret a pending task\n"
            "/projects -- list known projects\n\n"
            "Or just send any message, voice note, or link.",
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        from operation_drake.storage.database import check_db

        db_ok = check_db()
        s = self._settings
        lines = [
            "D.R.A.K.E. status:",
            f"Database: {'connected' if db_ok else 'ERROR'}",
            f"LLM provider: {s.default_llm_provider}",
            f"Transcription: {s.default_transcription_provider}",
            f"Environment: {s.app_env}",
        ]
        await _reply(update, "\n".join(lines))

    async def _cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        if not context.args:
            await _reply(update, "Usage: /approve <task_id>")
            return
        task_id = context.args[0]
        await _reply(update, f"Approving task {task_id[:8]}...")
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self._do_approve, task_id)
        await _reply(update, reply)

    async def _cmd_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        if not context.args:
            await _reply(update, "Usage: /reject <task_id>")
            return
        task_id = context.args[0]
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self._do_reject, task_id)
        await _reply(update, reply)

    async def _cmd_correct(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        if not context.args or len(context.args) < 2:
            await _reply(update, "Usage: /correct <task_id> <new instruction>")
            return
        task_id = context.args[0]
        correction = " ".join(context.args[1:])
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self._do_correct, task_id, correction)
        await _reply(update, reply)

    async def _cmd_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        if not context.args:
            await _reply(update, "Usage: /task <task_id>")
            return
        task_id = context.args[0]
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self._do_task_detail, task_id)
        await _reply(update, reply)

    async def _cmd_inbox(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(None, self._do_inbox)
        await _reply(update, reply)

    async def _cmd_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        from operation_drake.services.project_classifier import get_registry

        projects = get_registry()
        lines = ["Known projects:\n"]
        for p in projects:
            lines.append(f"{p['id']} ({p['name']})")
            lines.append(f"  {p['description'][:80]}")
        await _reply(update, "\n".join(lines))

    async def _cmd_cost(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(str(update.effective_user.id)):
            return
        with get_session() as session:
            total_tokens = AgentRunRepository(session).get_total_tokens()
        cost_usd = total_tokens * _COST_PER_TOKEN
        lines = [
            "Usage",
            f"Total tokens tracked: {total_tokens:,}",
            f"Estimated spend: ~${cost_usd:.4f}",
            f"Model: gpt-4o-mini (blended rate)",
        ]
        await _reply(update, "\n".join(lines))

    # -----------------------------------------------------------------------
    # Message handlers
    # -----------------------------------------------------------------------

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        uid = str(update.effective_user.id)
        if not self._is_allowed(uid):
            logger.info({"action": "unauthorized_telegram_user", "user_id": uid})
            return
        text = update.message.text or ""
        forwarded_from = None
        msg_type = "text"
        if update.message.forward_origin:
            forwarded_from = str(type(update.message.forward_origin).__name__)
            msg_type = "forwarded"
        await update.message.reply_text("Processing...")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self._process_sync,
            text,
            msg_type,
            uid,
            forwarded_from,
            str(update.message.message_id),
        )
        await _reply(update, response)

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        uid = str(update.effective_user.id)
        if not self._is_allowed(uid):
            logger.info({"action": "unauthorized_telegram_user", "user_id": uid})
            return
        await update.message.reply_text("Voice note received. Downloading...")
        file = await context.bot.get_file(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self._process_voice_sync,
            tmp_path,
            uid,
            str(update.message.message_id),
        )
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        await _reply(update, response)

    # -----------------------------------------------------------------------
    # Sync helpers (run in executor)
    # -----------------------------------------------------------------------

    def _process_sync(
        self, text: str, msg_type: str, sender_id: str, forwarded_from: str | None, ext_id: str
    ) -> str:
        result = _make_orchestrator(self._settings.artifacts_dir).process(
            channel="telegram",
            raw_text=text,
            message_type=msg_type,
            sender_id=sender_id,
            forwarded_from=forwarded_from,
            external_message_id=ext_id,
        )
        return _format_result(result)

    def _process_voice_sync(self, audio_path: str, sender_id: str, ext_id: str) -> str:
        result = _make_orchestrator(self._settings.artifacts_dir).process(
            channel="telegram",
            raw_text="[Voice note]",
            message_type="voice",
            sender_id=sender_id,
            external_message_id=ext_id,
            attachment_path=audio_path,
        )
        return f"Voice note: {result.result_summary}"

    def _do_approve(self, task_id: str) -> str:
        result = _make_orchestrator(self._settings.artifacts_dir).execute_approved_task(task_id)
        if result.status == "not_found":
            return f"Task {task_id} not found."
        lines = ["Task approved and executed.", f"Status: {result.status}"]
        if result.result_summary:
            lines.append(f"Result: {result.result_summary}")
        if result.artifact_path:
            lines.append("Artifact saved.")
        return "\n".join(lines)

    def _do_reject(self, task_id: str) -> str:
        result = _make_orchestrator(self._settings.artifacts_dir).reject_task(task_id)
        if result.status == "not_found":
            return f"Task {task_id} not found."
        if "not awaiting" in result.result_summary:
            return result.result_summary
        return f"Task {task_id} rejected and cancelled."

    def _do_correct(self, task_id: str, correction: str) -> str:
        result = _make_orchestrator(self._settings.artifacts_dir).correct_task(task_id, correction)
        if result.status == "not_found":
            return f"Task {task_id} not found."
        lines = [
            "Re-interpreted:",
            f"Intent: {result.intent} ({result.confidence:.0%} confident)",
            f"Proposed: {result.proposed_action}",
            f"Use /approve {task_id} to execute or /reject {task_id} to cancel.",
        ]
        return "\n".join(lines)

    def _do_task_detail(self, task_id: str) -> str:
        from operation_drake.storage.repositories import ArtifactRepository, TaskRepository

        session = get_session()
        task = TaskRepository(session).get(task_id)
        if not task:
            return f"Task {task_id} not found."
        artifacts = ArtifactRepository(session).get_by_task(task_id)
        lines = [
            f"Task {task_id[:8]}",
            f"Type: {task.task_type}",
            f"Status: {task.status}",
            f"Project: {task.project or 'none'}",
            f"Action: {task.requested_action[:120]}",
        ]
        if task.error_message:
            lines.append(f"Error: {task.error_message[:120]}")
        if artifacts:
            lines.append(f"Artifacts: {len(artifacts)}")
        if task.status == "awaiting_approval":
            lines.append(f"/approve {task_id} -- execute")
            lines.append(f"/reject {task_id} -- cancel")
            lines.append(f"/correct {task_id} <new instruction> -- re-interpret")
        return "\n".join(lines)

    def _do_inbox(self) -> str:
        from operation_drake.storage.repositories import TaskRepository

        pending = TaskRepository(get_session()).list_awaiting_approval()
        if not pending:
            return "No tasks awaiting approval."
        lines = [f"{len(pending)} task(s) awaiting approval:\n"]
        for t in pending[:10]:
            lines.append(f"[{t.id[:8]}] {t.task_type} -- {t.requested_action[:60]}")
            lines.append(f"  /approve {t.id} | /reject {t.id}")
        return "\n".join(lines)

    def run(self) -> None:
        logger.info({"action": "telegram_polling_start"})
        self._app.run_polling()
