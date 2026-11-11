
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.memory.database import SQLiteDatabase
from app.memory.manager import MemoryManager
from app.memory.meta_maintenance import MetaMemoryMaintenanceManager
from app.memory.meta_manager import MetaMemoryManager
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryType,
)
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.repositories.meta_memory import (
    MetaMemoryRepository,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
)


def test_complete_memory_lifecycle_integration(tmp_path):
    """Tests episodic and meta-memory together using one SQLite database."""

    database = SQLiteDatabase(tmp_path / "memory_lifecycle.db")

    episodic_repository = EpisodicMemoryRepository(database)
    meta_repository = MetaMemoryRepository(database)

    memory_manager = MemoryManager(episodic_repository)
    meta_manager = MetaMemoryManager(meta_repository)

    memory_manager.initialize()
    meta_manager.initialize()

    maintenance = MetaMemoryMaintenanceManager(meta_manager)

    old = datetime.now(timezone.utc) - timedelta(days=120)

    # 1. Store an old episodic memory eligible for archival.
    episodic_record = EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="Successfully analyzed project files.",
        created_at=old,
        completed_at=old,
        sensitivity=MemorySensitivity.INTERNAL,
        source=MemorySource.COORDINATOR,
        last_used_at=old,
        usage_tracked=True,
        use_count=0,
    )

    memory_manager.remember_task(episodic_record)

    # 2. Store metadata associated with the episodic memory.
    meta_record = MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=str(episodic_record.task_id),
    )

    meta_manager.remember(
        meta_record,
        requesting_agent="CoordinatorAgent",
    )

    # 3. Verify the metadata association.
    associated_meta = meta_manager.get_for_memory(
        MetaMemoryType.EPISODIC,
        str(episodic_record.task_id),
        requesting_agent="CoordinatorAgent",
    )

    assert associated_meta is not None
    assert associated_meta.meta_id == meta_record.meta_id

    # 4. Record meta-memory usage independently.
    assert meta_manager.record_usage(
        MetaMemoryType.EPISODIC,
        str(episodic_record.task_id),
        requesting_agent="CoordinatorAgent",
    )

    updated_meta = meta_manager.get(
        meta_record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert updated_meta is not None
    assert updated_meta.usage_count == 1
    assert updated_meta.last_retrieved_at is not None

    # 5. Run meta-memory maintenance and verify persistence.
    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
        batch_size=10,
    )

    assert report.total_examined == 1
    assert report.assessed == 1
    assert report.failed == 0

    assessed_meta = meta_manager.get(
        meta_record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert assessed_meta is not None
    assert assessed_meta.last_assessed_at is not None
    assert assessed_meta.assessment_confidence is not None

    # 6. Verify episodic retention eligibility.
    assessments = memory_manager.assess_retention(
        requesting_agent="CoordinatorAgent",
    )

    assert len(assessments) == 1
    assert assessments[0][0].task_id == episodic_record.task_id
    assert assessments[0][1].eligible

    # 7. Archive the episodic memory.
    assert memory_manager.archive_task(
        episodic_record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    archived = memory_manager.get_archived_tasks(
        requesting_agent="CoordinatorAgent",
    )

    assert len(archived) == 1
    assert archived[0].lifecycle_status == MemoryLifecycleStatus.ARCHIVED
    assert archived[0].summary == episodic_record.summary

    # 8. Restore it and verify its original content.
    assert memory_manager.restore_task(
        episodic_record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    restored = memory_manager.get_task(
        episodic_record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert restored is not None
    assert restored.lifecycle_status == MemoryLifecycleStatus.ACTIVE
    assert restored.summary == episodic_record.summary
    assert restored.use_count == episodic_record.use_count

    # 9. Verify database integrity after the complete lifecycle.
    assert database.check_integrity()
    assert database.check_foreign_key_integrity()
