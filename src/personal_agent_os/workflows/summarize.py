from personal_agent_os.agents.synthesis import SynthesisAgent
from personal_agent_os.services.artifact_service import ArtifactService
from personal_agent_os.workflows.capture_note import WorkflowResult


class SummarizeWorkflow:
    def __init__(self, synthesis_agent: SynthesisAgent, artifact_service: ArtifactService):
        self.agent = synthesis_agent
        self.artifact_service = artifact_service

    def run(self, content: str, task_id: str) -> WorkflowResult:
        try:
            result = self.agent.run_synthesis(content, task_type="summarize")
            points = "\n".join(f"- {p}" for p in result.key_points) or "_None_"
            actions = "\n".join(f"- {a}" for a in result.action_items) or "_None_"
            md = f"""# {result.title}

## Summary
{result.summary}

## Key Points
{points}

## Action Items
{actions}
"""
            path = self.artifact_service.save(title=result.title, content=md, task_id=task_id, artifact_type="summary")
            return WorkflowResult(success=True, artifact_path=path, summary=result.summary)
        except Exception as e:
            return WorkflowResult(success=False, error=str(e))
