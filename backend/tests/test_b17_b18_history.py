"""B17 + B18: quy tắc lịch sử, tái dựng, phân trang (không cần DB). Kiểm cả đầu ra của B12 (task_rules)."""
import importlib.util, sys
from pathlib import Path
import pytest

A = Path(__file__).resolve().parents[1] / "app"
def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, A / rel); m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m; spec.loader.exec_module(m); return m

H = load("history_rules_t", "core/history_rules.py")
R = load("task_rules_h", "core/task_rules.py")

SNAP = {"title": "A", "description": None, "status": "TODO", "due_date": None, "assignee_id": None, "parent_id": None}


def ev(seq, t, ts, before, after):
    return {"event_seq": seq, "event_type": t, "occurred_at": ts, "before_value": before, "after_value": after}


# ---- validate_event ----
def test_create_requires_full_snapshot():
    assert H.validate_event("CREATE", None, SNAP) == []
    assert H.validate_event("CREATE", None, {"title": "A"})
    assert H.validate_event("CREATE", {"x": 1}, SNAP)
    assert H.validate_event("CREATE", None, {**SNAP, "status": "DOING"})


def test_unknown_event_type_rejected():
    assert H.validate_event("DELETE_ALL", None, None)


def test_field_events():
    assert H.validate_event("STATUS_CHANGE", {"status": "TODO"}, {"status": "DONE"}) == []
    assert H.validate_event("STATUS_CHANGE", {"status": "TODO"}, {"status": "TODO"})
    assert H.validate_event("STATUS_CHANGE", {"status": "TODO"}, {"status": "X"})
    assert H.validate_event("DUE_CHANGE", {"due_date": None}, {"due_date": "2026-12-01"}) == []
    assert H.validate_event("DUE_CHANGE", {"due_date": None, "status": "TODO"}, {"due_date": "2026-12-01"})
    assert H.validate_event("ASSIGNEE_CHANGE", {"assignee_id": None}, {"assignee_id": 3}) == []


def test_archive_restore_events():
    assert H.validate_event("ARCHIVE", {"archived_at": None}, {"archived_at": "2026-11-10T00:00:00Z"}) == []
    assert H.validate_event("ARCHIVE", {"archived_at": "x"}, {"archived_at": "y"})
    assert H.validate_event("RESTORE", {"archived_at": "2026-11-10T00:00:00Z"}, {"archived_at": None}) == []
    assert H.validate_event("RESTORE", {"archived_at": None}, {"archived_at": None})


def test_detail_change():
    assert H.validate_event("DETAIL_CHANGE", {"title": "A", "description": None}, {"title": "B", "description": "d"}) == []
    assert H.validate_event("DETAIL_CHANGE", {"title": "A"}, {"description": "d"})
    assert H.validate_event("DETAIL_CHANGE", {"status": "A"}, {"status": "B"})


def test_events_produced_by_b12_rules_are_valid():
    ch = R.changed_fields(SNAP, {"status": "DONE", "title": "B", "description": "d",
                                 "due_date": "2026-12-01", "assignee_id": 2})
    for etype, before, after in R.build_events(SNAP, ch):
        assert H.validate_event(etype, before, after) == [], etype


# ---- replay ----
EVENTS = [
    ev(1, "CREATE", "2026-11-01T01:00:00Z", None, SNAP),
    ev(2, "STATUS_CHANGE", "2026-11-02T01:00:00Z", {"status": "TODO"}, {"status": "IN_PROGRESS"}),
    ev(3, "DUE_CHANGE", "2026-11-03T01:00:00Z", {"due_date": None}, {"due_date": "2026-11-20"}),
    ev(4, "ARCHIVE", "2026-11-04T01:00:00Z", {"archived_at": None}, {"archived_at": "2026-11-04T01:00:00Z"}),
    ev(5, "RESTORE", "2026-11-05T01:00:00Z", {"archived_at": "2026-11-04T01:00:00Z"}, {"archived_at": None}),
    ev(6, "STATUS_CHANGE", "2026-11-06T01:00:00Z", {"status": "IN_PROGRESS"}, {"status": "DONE"}),
]


def test_replay_at_points_in_time():
    s, w = H.replay(EVENTS, until="2026-11-02T00:00:00Z")
    assert w == [] and s["status"] == "TODO" and s["due_date"] is None and s["archived_at"] is None
    s, _ = H.replay(EVENTS, until="2026-11-04T12:00:00Z")
    assert s["status"] == "IN_PROGRESS" and s["due_date"] == "2026-11-20" and s["archived_at"] == "2026-11-04T01:00:00Z"
    s, _ = H.replay(EVENTS)
    assert s["status"] == "DONE" and s["archived_at"] is None


def test_replay_before_create_is_missing_not_guessed():
    s, w = H.replay(EVENTS, until="2026-10-01T00:00:00Z")
    assert s is None and w


def test_replay_without_create_warns():
    s, w = H.replay(EVENTS[1:])
    assert s is None and w


def test_replay_order_uses_seq_when_same_timestamp():
    same = "2026-11-02T01:00:00Z"
    evs = [ev(1, "CREATE", "2026-11-01T00:00:00Z", None, SNAP),
           ev(3, "STATUS_CHANGE", same, {"status": "IN_PROGRESS"}, {"status": "DONE"}),
           ev(2, "STATUS_CHANGE", same, {"status": "TODO"}, {"status": "IN_PROGRESS"})]
    s, _ = H.replay(evs)
    assert s["status"] == "DONE"
    assert [e["event_seq"] for e in H.sort_events(evs)] == [1, 2, 3]


def test_timestamps_with_and_without_microseconds_sort_correctly():
    evs = [ev(2, "STATUS_CHANGE", "2026-11-02T01:00:00.500000Z", {"status": "TODO"}, {"status": "DONE"}),
           ev(1, "CREATE", "2026-11-02T01:00:00Z", None, SNAP)]
    assert [e["event_seq"] for e in H.sort_events(evs)] == [1, 2]


# ---- page_slice ----
def test_page_slice():
    assert H.page_slice([1, 2, 3], 2) == ([1, 2], True)
    assert H.page_slice([1, 2], 2) == ([1, 2], False)
    assert H.page_slice([], 5) == ([], False)
