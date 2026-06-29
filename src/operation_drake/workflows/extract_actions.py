from operation_drake.agents.synthesis import SynthesisAgent
from operation_drake.services.artifact_service import ArtifactService
from operation_drake.workflows.capture_note import WorkflowResult


class ExtractActionsWorkflow:
    def __init__(self, synthesis_agent: SynthesisAgent, artifact_service: ArtifactService):
        self.agent = synthesis_agent
        self.artifact_service = artifact_service

    def run(self, content: str, task_id: str) -> WorkflowResult:
        try:
            result = self.agent.run_synthesis(content, task_type="extract_actions")
            actions = (
                "\n".join(f"- [ ] {a}" for a in result.action_items) or "_No action items found_"
            )
            md = f"""# Action Items: {result.title}

{actions}

## Context
{result.summary}
"""
            path = self.artifact_service.save(
                title=f"Actions - {result.title}",
                content=md,
                task_id=task_id,
                artifact_type="action_list",
            )
            return WorkflowResult(
                success=True,
                artifact_path=path,
                summary=f"{len(result.action_items)} action items extracted",
            )
        except Exception as e:
            return WorkflowResult(success=False, error=str(e))
