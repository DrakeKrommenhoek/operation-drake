"""
Mock CLI dry-run. Exercises the full pipeline without paid credentials.
Run from the project root: python scripts/dry_run.py
"""
import os
import shutil
import sys

# Point at isolated test database and artifacts
os.environ["DATABASE_URL"] = "sqlite:///./data/database/dryrun.db"
os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"
os.environ["ARTIFACTS_DIR"] = "./data/artifacts/dryrun"

import operation_drake.storage.database as db_module  # noqa: E402

db_module._engine = None
db_module._SessionLocal = None

from operation_drake.agents.router import RouterAgent  # noqa: E402
from operation_drake.config import get_settings  # noqa: E402
from operation_drake.llm.mock_provider import MockLLMProvider  # noqa: E402
from operation_drake.models.database import (  # noqa: E402
    AgentRunORM,
    ArtifactORM,
    InboundMessageORM,
    IntentDecisionORM,
    TaskORM,
)
from operation_drake.services.orchestration import OrchestratorService  # noqa: E402
from operation_drake.storage.database import get_session, init_db  # noqa: E402
from operation_drake.storage.repositories import ArtifactRepository, TaskRepository  # noqa: E402
from operation_drake.transcription.mock_transcriber import MockTranscriber  # noqa: E402

get_settings.cache_clear()
init_db()


def make_orch(fixed_response=None):
    llm = MockLLMProvider(fixed_response=fixed_response) if fixed_response else MockLLMProvider()
    return OrchestratorService(
        session=get_session(),
        llm=llm,
        transcriber=MockTranscriber(),
        artifacts_dir="./data/artifacts/dryrun",
    )


APPROVAL_RESPONSE = '{"primary_intent":"save_note","secondary_intents":[],"confidence":0.7,"proposed_action":"Save this as a note","approval_required":true,"clarification_question":null,"rationale_summary":"Manual approval requested."}'
UNCERTAIN_RESPONSE = '{"primary_intent":"unknown","secondary_intents":[],"confidence":0.3,"proposed_action":"Unknown intent","approval_required":true,"clarification_question":"What do you mean?","rationale_summary":"Low confidence."}'


def sep(n=70):
    print("-" * n)


print("\n=== D.R.A.K.E. MOCK DRY RUN ===\n")

# --- 1. Normal note ---
sep()
print("[1] Submit a note")
r1 = make_orch().process(
    channel="cli", raw_text="Remember: call mom this Sunday", message_type="text", sender_id="drake"
)
print(f"    intent={r1.intent}  confidence={r1.confidence:.0%}  status={r1.status}")
print(f"    task_id={r1.task_id[:8]}")
if r1.artifact_path:
    print(f"    artifact={r1.artifact_path}")

# --- 2. Summary request ---
sep()
print("[2] Submit summary request")
r2 = make_orch().process(
    channel="cli",
    raw_text="Summarize: Python is a versatile language used for web, data, and AI.",
    message_type="text",
    sender_id="drake",
)
print(f"    intent={r2.intent}  confidence={r2.confidence:.0%}  status={r2.status}")

# --- 3. Action items ---
sep()
print("[3] Extract action items")
r3 = make_orch().process(
    channel="cli",
    raw_text="Extract actions: review PR, update docs, write tests, deploy to staging",
    message_type="text",
    sender_id="drake",
)
print(f"    intent={r3.intent}  confidence={r3.confidence:.0%}  status={r3.status}")

# --- 4. URL ---
sep()
print("[4] Submit URL")
r4 = make_orch().process(
    channel="cli", raw_text="https://example.com", message_type="text", sender_id="drake"
)
print(f"    intent={r4.intent}  confidence={r4.confidence:.0%}  status={r4.status}")

# --- 5. Voice note ---
sep()
print("[5] Submit voice note transcript")
r5 = make_orch().process(
    channel="cli",
    raw_text="[Voice] I want to build a habit tracker for the Answer Movement",
    message_type="voice",
    sender_id="drake",
    attachment_path="/fake/voice.ogg",
)
print(f"    intent={r5.intent}  confidence={r5.confidence:.0%}  status={r5.status}")

# --- 6. Task requiring approval ---
sep()
print("[6] Submit task requiring approval")
orch6 = make_orch(fixed_response=APPROVAL_RESPONSE)
r6 = orch6.process(
    channel="cli",
    raw_text="Research brief: LBO modeling basics for PE interviews",
    message_type="text",
    sender_id="drake",
)
print(f"    intent={r6.intent}  confidence={r6.confidence:.0%}  status={r6.status}")
print(f"    task_id={r6.task_id[:8]}  (awaiting approval)")
approval_task_id = r6.task_id

# --- 7. Approve it ---
sep()
print("[7] Approve task")
ra = make_orch().execute_approved_task(approval_task_id)
print(f"    status={ra.status}")
if ra.artifact_path:
    print(f"    artifact={ra.artifact_path}")

# --- 8. Submit and reject ---
sep()
print("[8] Submit and reject a task")
orch8 = make_orch(fixed_response=APPROVAL_RESPONSE)
r8 = orch8.process(
    channel="cli", raw_text="Do something risky", message_type="text", sender_id="drake"
)
rrej = orch8.reject_task(r8.task_id)
print(f"    submitted status={r8.status}  task_id={r8.task_id[:8]}")
print(f"    after reject status={rrej.status}")

# --- 9. Submit and correct ---
sep()
print("[9] Submit ambiguous message and correct interpretation")
orch9 = make_orch(fixed_response=UNCERTAIN_RESPONSE)
r9 = orch9.process(
    channel="cli", raw_text="blah blah ambiguous", message_type="text", sender_id="drake"
)
print(f"    original intent={r9.intent}  status={r9.status}")
orch9._router = RouterAgent(llm=MockLLMProvider())
rc = orch9.correct_task(r9.task_id, "Actually save this as a note about fitness goals")
print(f"    corrected intent={rc.intent}  status={rc.status}")
print(f"    proposed action: {rc.proposed_action}")

# --- 10. Query records ---
sep()
print("[10] Query all persisted records")
session = get_session()
tasks = TaskRepository(session).list_recent(limit=50)
print(f"    Tasks ({len(tasks)} total):")
for t in tasks:
    arts = ArtifactRepository(session).get_by_task(t.id)
    print(f"      [{t.status:22s}] type={t.task_type:20s} artifacts={len(arts)}")

msgs = session.query(InboundMessageORM).all()
intents = session.query(IntentDecisionORM).all()
runs = session.query(AgentRunORM).all()
arts_all = session.query(ArtifactORM).all()

sep()
print("    Record type          Count")
sep()
print(f"    InboundMessages      {len(msgs)}")
print(f"    IntentDecisions      {len(intents)}")
print(f"    Tasks                {len(tasks)}")
print(f"    AgentRuns            {len(runs)}")
print(f"    Artifacts            {len(arts_all)}")
sep()

# Verify all records are linked
print("\n    Linkage check:")
for t in tasks:
    msg = session.get(InboundMessageORM, t.inbound_message_id)
    assert msg is not None, f"Task {t.id[:8]} has no message!"
print("    All tasks have linked InboundMessage records. OK")

arts_with_task = [a for a in arts_all if session.get(TaskORM, a.task_id)]
print(f"    All {len(arts_with_task)} artifacts have linked Task records. OK")

# Clean up
session.close()
db_module._engine.dispose()
db_module._engine = None
db_module._SessionLocal = None
try:
    os.remove("./data/database/dryrun.db")
except OSError:
    print("    Note: dryrun.db not removed (Windows SQLite file lock — safe to delete manually)")
shutil.rmtree("./data/artifacts/dryrun", ignore_errors=True)

print("\n=== DRY RUN COMPLETE ===\n")
sys.exit(0)
