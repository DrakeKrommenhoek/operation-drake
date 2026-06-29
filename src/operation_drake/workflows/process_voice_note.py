from operation_drake.agents.synthesis import SynthesisAgent
from operation_drake.services.artifact_service import ArtifactService
from operation_drake.transcription.base import TranscriptionProvider
from operation_drake.workflows.capture_note import WorkflowResult
from operation_drake.workflows.summarize import SummarizeWorkflow


class ProcessVoiceNoteWorkflow:
    def __init__(
        self,
        transcriber: TranscriptionProvider,
        synthesis_agent: SynthesisAgent,
        artifact_service: ArtifactService,
    ):
        self.transcriber = transcriber
        self._summarize = SummarizeWorkflow(
            synthesis_agent=synthesis_agent, artifact_service=artifact_service
        )

    def run(self, audio_path: str, task_id: str) -> WorkflowResult:
        try:
            transcript = self.transcriber.transcribe(audio_path)
            result = self._summarize.run(content=transcript, task_id=task_id)
            return WorkflowResult(
                success=result.success,
                artifact_path=result.artifact_path,
                summary=f"Voice note transcribed and summarized. {result.summary}",
                error=result.error,
            )
        except Exception as e:
            return WorkflowResult(success=False, error=str(e))
