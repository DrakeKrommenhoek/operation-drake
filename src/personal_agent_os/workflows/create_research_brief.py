from personal_agent_os.agents.synthesis import SynthesisAgent
from personal_agent_os.services.artifact_service import ArtifactService
from personal_agent_os.workflows.capture_note import WorkflowResult


class CreateResearchBriefWorkflow:
    def __init__(self, synthesis_agent: SynthesisAgent, artifact_service: ArtifactService):
        self.agent = synthesis_agent
        self.artifact_service = artifact_service

    def run(self, content: str, task_id: str) -> WorkflowResult:
        try:
            result = self.agent.run_synthesis(content, task_type="research_brief")
            points = "\n".join(f"- {p}" for p in result.key_points) or "_None_"
            questions = "\n".join(f"- {q}" for q in result.questions) or "_None_"
            next_steps = "\n".join(f"- {s}" for s in result.next_steps) or "_None_"
            md = f"""# Research Brief: {result.title}

## Summary
{result.summary}

## Key Claims
{points}

## Open Questions
{questions}

## Suggested Next Steps
{next_steps}
"""
            path = self.artifact_service.save(
                title=f"Brief - {result.title}", content=md, task_id=task_id, artifact_type="research_brief"
            )
            return WorkflowResult(success=True, artifact_path=path, summary=result.summary)
        except Exception as e:
            return WorkflowResult(success=False, error=str(e))
