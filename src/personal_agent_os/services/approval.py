from personal_agent_os.models.schemas import IntentType

SAFE_INTENTS = {
    IntentType.save_note,
    IntentType.summarize,
    IntentType.extract_actions,
    IntentType.research_brief,
    IntentType.save_link,
    IntentType.transcribe_voice,
}


def requires_approval(intent: str) -> bool:
    try:
        return IntentType(intent) not in SAFE_INTENTS
    except ValueError:
        return True
