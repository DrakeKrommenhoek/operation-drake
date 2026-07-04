from dataclasses import dataclass

from operation_drake.agents.capture import CaptureAgent
from operation_drake.services.artifact_service import ArtifactService


@dataclass
class WorkflowResult:
    success: bool
    artifact_path: str = ""
    summary: str = ""
    error: str = ""
    token_count: int = 0


class CaptureNoteWorkflow:
    def __init__(self, capture_agent: CaptureAgent, artifact_service: ArtifactService):
        self.agent = capture_agent
        self.artifact_service = artifact_service

    def run(self, content: str, task_id: str, project: str | None = None) -> WorkflowResult:
        try:
            result = self.agent.run_capture(content, project=project)
            tags_str = ", ".join(result.tags) if result.tags else "none"
            actions_str = (
                "\n".join(f"- {a}" for a in result.action_items)
                if result.action_items
                else "_None identified_"
            )
            md = f"""# {result.title}

**Project:** {result.project or "General"}
**Tags:** {tags_str}

## Summary
{result.summary or content}

## Action Items
{actions_str}
"""
            path = self.artifact_service.save(
                title=result.title, content=md, task_id=task_id, artifact_type="note"
            )
            return WorkflowResult(
                success=True,
                artifact_path=path,
                summary=result.summary or result.title,
                token_count=result.input_tokens + result.output_tokens,
            )
        except Exception as e:
            return WorkflowResult(success=False, error=str(e))
