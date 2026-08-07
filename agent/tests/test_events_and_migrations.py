def test_log_event_requires_existing_project(fresh_modules):
    """events.project_name FK-references projects.name — logging for a
    project that was never upserted must fail loudly, not silently."""
    import sqlite3

    import pytest

    _, _, _, registry = fresh_modules
    with pytest.raises(sqlite3.IntegrityError):
        registry.log_event("ghost", "deploy", "should not work", success=True)


def test_events_ordered_newest_first(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("a", "devps")

    registry.log_event("a", "deploy", "attempt 1", success=False)
    registry.log_event("a", "deploy", "attempt 2", success=True)

    events = registry.get_events("a")
    assert [e["detail"] for e in events] == ["attempt 2", "attempt 1"]
    assert events[0]["success"] == 1
    assert events[1]["success"] == 0


def test_last_event_surfaces_on_project(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("a", "devps")
    assert registry.get_project("a")["last_event"] is None

    registry.log_event("a", "restart", None, success=True)
    last = registry.get_project("a")["last_event"]
    assert last["kind"] == "restart"
    assert last["success"] == 1


def test_list_events_spans_projects(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("a", "devps")
    registry.upsert_project("b", "devps")
    registry.log_event("a", "deploy", None, success=True)
    registry.log_event("b", "adopt", None, success=True)

    feed = registry.list_events()
    assert {e["project_name"] for e in feed} == {"a", "b"}


def test_events_cascade_delete_with_project(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("a", "devps")
    registry.log_event("a", "deploy", None, success=True)

    registry.delete_project("a")

    assert registry.get_events("a") == []


def test_touch_migration_creates_and_stamps(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("legacy", "adopted")

    registry.touch_migration("legacy", "adopted", source_description="container legacy-web")

    migration = registry.get_migration("legacy")
    assert migration["source_description"] == "container legacy-web"
    assert migration["adopted_at"] is not None
    assert migration["cutover_at"] is None


def test_touch_migration_does_not_rewind_a_step(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("legacy", "adopted")

    registry.touch_migration("legacy", "adopted")
    first_stamp = registry.get_migration("legacy")["adopted_at"]

    registry.touch_migration("legacy", "adopted")  # called again — should not move
    assert registry.get_migration("legacy")["adopted_at"] == first_stamp


def test_touch_migration_progresses_through_steps(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("legacy", "adopted")

    registry.touch_migration("legacy", "adopted")
    registry.touch_migration("legacy", "paralleled")
    registry.touch_migration("legacy", "cutover")

    migration = registry.get_migration("legacy")
    assert migration["adopted_at"] is not None
    assert migration["paralleled_at"] is not None
    assert migration["cutover_at"] is not None
    assert migration["decommissioned_at"] is None


def test_list_migrations_only_includes_touched_projects(fresh_modules):
    _, _, _, registry = fresh_modules
    registry.upsert_project("a", "devps")  # never migrated — should not appear
    registry.upsert_project("legacy", "adopted")
    registry.touch_migration("legacy", "adopted")

    names = {m["project_name"] for m in registry.list_migrations()}
    assert names == {"legacy"}
