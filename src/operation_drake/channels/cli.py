from operation_drake.channels.base import ChannelAdapter
from operation_drake.llm import get_llm_provider
from operation_drake.observability.logging import get_logger
from operation_drake.services.orchestration import OrchestratorService, ProcessResult
from operation_drake.storage.database import get_session
from operation_drake.transcription import get_transcription_provider

logger = get_logger(__name__)


_PLAIN_STATUSES = {
    "duplicate",
    "answered",
    "command_hint",
    "awaiting_capture_confirmation",
    "discarded",
}


def _format_response(result: ProcessResult) -> str:
    if result.status in _PLAIN_STATUSES:
        return result.result_summary
    lines = [
        f"Intent: {result.intent} (confidence: {result.confidence:.0%})",
        f"I think: {result.proposed_action}",
        f"Status: {result.status}",
    ]
    if result.clarification_question:
        lines.append(f"Question: {result.clarification_question}")
    if result.artifact_path:
        lines.append(f"Artifact saved: {result.artifact_path}")
    if result.result_summary:
        lines.append(f"Result: {result.result_summary}")
    return "\n".join(lines)


def _make_orchestrator(artifacts_dir: str) -> OrchestratorService:
    return OrchestratorService(
        session=get_session(),
        llm=get_llm_provider(),
        transcriber=get_transcription_provider(),
        artifacts_dir=artifacts_dir,
    )


class CLIAdapter(ChannelAdapter):
    channel_name = "cli"

    def __init__(self, artifacts_dir: str = "./data/artifacts"):
        self._artifacts_dir = artifacts_dir

    def send(self, text: str, reply_to: str | None = None) -> None:
        print(f"\n[Agent] {text}")

    def run_once(self, text: str) -> str:
        result = _make_orchestrator(self._artifacts_dir).process(
            channel="cli", raw_text=text, message_type="text", sender_id="local"
        )
        return _format_response(result)

    def approve(self, task_id: str) -> str:
        result = _make_orchestrator(self._artifacts_dir).execute_approved_task(task_id)
        return _format_response(result)

    def reject(self, task_id: str) -> str:
        result = _make_orchestrator(self._artifacts_dir).reject_task(task_id)
        return _format_response(result)

    def correct(self, task_id: str, correction: str) -> str:
        result = _make_orchestrator(self._artifacts_dir).correct_task(task_id, correction)
        return _format_response(result)

    def run_interactive(self) -> None:
        print("D.R.A.K.E. CLI — type your message, 'quit' to exit")
        while True:
            try:
                text = input("\nYou: ").strip()
                if text.lower() in ("quit", "exit", "q"):
                    break
                if not text:
                    continue
                response = self.run_once(text)
                self.send(response)
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye.")
                break
