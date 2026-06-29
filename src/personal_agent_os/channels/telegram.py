import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from personal_agent_os.channels.base import ChannelAdapter
from personal_agent_os.config import get_settings
from personal_agent_os.llm import get_llm_provider
from personal_agent_os.observability.logging import get_logger
from personal_agent_os.services.orchestration import OrchestratorService
from personal_agent_os.storage.database import get_session
from personal_agent_os.transcription import get_transcription_provider

logger = get_logger(__name__)


class TelegramAdapter(ChannelAdapter):
    channel_name = "telegram"

    def __init__(self):
        self._settings = get_settings()
        self._app = Application.builder().token(self._settings.telegram_bot_token).build()
        self._setup_handlers()

    def send(self, text: str, reply_to: str | None = None) -> None:
        pass

    def _setup_handlers(self) -> None:
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("approve", self._cmd_approve))
        self._app.add_handler(CommandHandler("reject", self._cmd_reject))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        self._app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Operation Drake is online. Send me a message, voice note, or URL and I'll handle it."
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "/start — greet\n"
            "/status — system status\n"
            "/approve <task_id> — approve a pending task\n"
            "/reject <task_id> — reject a pending task\n\n"
            "Or just send any message, voice note, or link."
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from personal_agent_os.storage.database import check_db
        db_ok = check_db()
        await update.message.reply_text(f"Operation Drake running. Database: {'connected' if db_ok else 'error'}.")

    async def _cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Approval flow: coming soon. Task ID support in next milestone.")

    async def _cmd_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Rejection flow: coming soon.")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            str(update.effective_user.id),
            forwarded_from,
            str(update.message.message_id),
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Voice note received. Downloading...")
        import os
        import tempfile
        file = await context.bot.get_file(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self._process_voice_sync,
            tmp_path,
            str(update.effective_user.id),
            str(update.message.message_id),
        )
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        await update.message.reply_text(response)

    def _process_sync(
        self, text: str, msg_type: str, sender_id: str, forwarded_from: str | None, ext_id: str
    ) -> str:
        session = get_session()
        orch = OrchestratorService(
            session=session,
            llm=get_llm_provider(),
            transcriber=get_transcription_provider(),
            artifacts_dir=self._settings.artifacts_dir,
        )
        result = orch.process(
            channel="telegram",
            raw_text=text,
            message_type=msg_type,
            sender_id=sender_id,
            forwarded_from=forwarded_from,
            external_message_id=ext_id,
        )
        lines = [f"*Intent:* {result.intent} ({result.confidence:.0%} confident)", f"_{result.proposed_action}_"]
        if result.clarification_question:
            lines.append(f"\n*Question:* {result.clarification_question}")
        if result.status == "completed" and result.result_summary:
            lines.append(f"\n*Result:* {result.result_summary}")
        if result.artifact_path:
            lines.append("Artifact saved ✓")
        return "\n".join(lines)

    def _process_voice_sync(self, audio_path: str, sender_id: str, ext_id: str) -> str:
        session = get_session()
        orch = OrchestratorService(
            session=session,
            llm=get_llm_provider(),
            transcriber=get_transcription_provider(),
            artifacts_dir=self._settings.artifacts_dir,
        )
        result = orch.process(
            channel="telegram",
            raw_text="[Voice note]",
            message_type="voice",
            sender_id=sender_id,
            external_message_id=ext_id,
            attachment_path=audio_path,
        )
        return f"Voice processed: {result.result_summary}"

    def run(self) -> None:
        logger.info({"action": "telegram_polling_start"})
        self._app.run_polling()
