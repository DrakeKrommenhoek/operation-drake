import os
import tempfile

from operation_drake.agents.capture import CaptureAgent
from operation_drake.agents.synthesis import SynthesisAgent
from operation_drake.llm.mock_provider import MockLLMProvider
from operation_drake.services.approval import requires_approval
from operation_drake.services.artifact_service import ArtifactService
from operation_drake.transcription.mock_transcriber import MockTranscriber
from operation_drake.workflows.capture_note import CaptureNoteWorkflow
from operation_drake.workflows.extract_actions import ExtractActionsWorkflow
from operation_drake.workflows.process_voice_note import ProcessVoiceNoteWorkflow
from operation_drake.workflows.summarize import SummarizeWorkflow


def test_artifact_service_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = ArtifactService(artifacts_dir=tmpdir)
        path = svc.save(
            title="Test Note",
            content="# Test\nHello world",
            task_id="task-abc123",
            artifact_type="note",
        )
        assert os.path.exists(path)
        content = open(path, encoding="utf-8").read()
        assert "# Test" in content


def test_capture_note_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = CaptureAgent(llm=MockLLMProvider())
        svc = ArtifactService(artifacts_dir=tmpdir)
        wf = CaptureNoteWorkflow(capture_agent=agent, artifact_service=svc)
        result = wf.run(content="Remember to call mom on Sunday", task_id="task-001", project=None)
        assert result.success
        assert result.artifact_path
        assert os.path.exists(result.artifact_path)


def test_summarize_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = SynthesisAgent(llm=MockLLMProvider())
        svc = ArtifactService(artifacts_dir=tmpdir)
        wf = SummarizeWorkflow(synthesis_agent=agent, artifact_service=svc)
        result = wf.run(
            content="Python is a versatile programming language used in many fields.",
            task_id="task-002",
        )
        assert result.success
        assert result.artifact_path


def test_extract_actions_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = SynthesisAgent(llm=MockLLMProvider())
        svc = ArtifactService(artifacts_dir=tmpdir)
        wf = ExtractActionsWorkflow(synthesis_agent=agent, artifact_service=svc)
        result = wf.run(content="TODO: review the PR, update docs, write tests", task_id="task-003")
        assert result.success
        assert result.artifact_path
        # summary must contain the formatted action list, not just a count string
        assert "- [ ]" in result.summary or "No action items found" in result.summary


def test_voice_note_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = SynthesisAgent(llm=MockLLMProvider())
        svc = ArtifactService(artifacts_dir=tmpdir)
        transcriber = MockTranscriber()
        wf = ProcessVoiceNoteWorkflow(
            transcriber=transcriber, synthesis_agent=agent, artifact_service=svc
        )
        result = wf.run(audio_path="/fake/voice.ogg", task_id="task-004")
        assert result.success
        assert "transcribed" in result.summary.lower()


def test_approval_required_for_unknown_intent():
    assert requires_approval("unknown") is True
    assert requires_approval("send_email") is True


def test_no_approval_for_safe_intents():
    assert requires_approval("save_note") is False
    assert requires_approval("summarize") is False
    assert requires_approval("extract_actions") is False
    assert requires_approval("research_brief") is False
