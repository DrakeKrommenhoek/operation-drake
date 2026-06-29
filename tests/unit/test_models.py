from operation_drake.models.schemas import (
    VALID_TRANSITIONS,
    InboundMessageCreate,
    IntentType,
    TaskStatus,
)


def test_task_status_values():
    assert TaskStatus.received == "received"
    assert TaskStatus.completed == "completed"
    assert TaskStatus.failed == "failed"


def test_valid_transitions_exist():
    assert TaskStatus.normalizing in VALID_TRANSITIONS[TaskStatus.received]
    assert TaskStatus.completed in VALID_TRANSITIONS[TaskStatus.running]
    assert VALID_TRANSITIONS[TaskStatus.completed] == []


def test_inbound_message_defaults():
    msg = InboundMessageCreate(
        channel="cli",
        external_message_id="test-1",
        sender_id="user",
        raw_text="hello world",
        message_type="text",
    )
    assert msg.raw_text == "hello world"
    assert msg.processing_status == TaskStatus.received


def test_intent_type_values():
    assert IntentType.save_note == "save_note"
    assert IntentType.summarize == "summarize"
    assert IntentType.unknown == "unknown"
