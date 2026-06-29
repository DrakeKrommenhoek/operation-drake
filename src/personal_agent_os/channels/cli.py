from personal_agent_os.channels.base import ChannelAdapter
from personal_agent_os.llm import get_llm_provider
from personal_agent_os.observability.logging import get_logger
from personal_agent_os.services.orchestration import OrchestratorService, ProcessResult
from personal_agent_os.storage.database import get_session
from personal_agent_os.transcription import get_transcription_provider

logger = get_logger(__name__)


def _format_response(result: ProcessResult) -> str:
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


class CLIAdapter(ChannelAdapter):
    channel_name = "cli"

    def __init__(self, artifacts_dir: str = "./data/artifacts"):
        self._artifacts_dir = artifacts_dir

    def send(self, text: str, reply_to: str | None = None) -> None:
        print(f"\n[Agent] {text}")

    def run_once(self, text: str) -> str:
        session = get_session()
        orchestrator = OrchestratorService(
            session=session,
            llm=get_llm_provider(),
            transcriber=get_transcription_provider(),
            artifacts_dir=self._artifacts_dir,
        )
        result = orchestrator.process(channel="cli", raw_text=text, message_type="text", sender_id="local")
        return _format_response(result)

    def run_interactive(self) -> None:
        print("Operation Drake CLI — type your message, 'quit' to exit")
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
