"""M02–M05: MET-01..MET-06 từ TaskHistory (hàm thuần, không cần DB) + bộ dữ liệu mẫu kiểm chứng.

LƯU Ý M05: SRS/SDD chỉ nêu KẾT QUẢ mong đợi của bộ mẫu (MET-01=3, MET-02=3, MET-03=2, MET-04=3, MET-05=2, MET-06=66.67)
chứ không kèm dữ liệu đầu vào. Bộ dữ liệu bên dưới do nhóm dựng lại sao cho đúng các kết quả đó và đúng định nghĩa SDD mục 5;
cần nhóm đối chiếu với bộ mẫu gốc (nếu có) trước khi nghiệm thu.
"""
import copy
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.core.metrics import MISSING_CREATE, NO_DUE_DATE_DONE, compute_metrics
from app.core.weekly_period import week_bounds

VN = "Asia/Ho_Chi_Minh"
WEEK = datetime(2026, 10, 19).date()                       # thứ Hai 19/10/2026
NOW = datetime(2026, 11, 30, tzinfo=timezone.utc)
START, END = week_bounds(WEEK, VN, NOW)                    # 2026-10-18T17:00Z .. 2026-10-25T17:00Z
seq = [0]


def L(text, tz=VN):
    """Giờ địa phương 'YYYY-MM-DD HH:MM' -> UTC."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def ev(task_id, etype, when, after, before=None):
    seq[0] += 1
    return {"task_id": task_id, "event_seq": seq[0], "event_type": etype, "before_value": before,
            "after_value": after, "occurred_at": when}


def snap(**kw):
    return {"title": "T", "description": None, "status": "TODO", "due_date": None, "assignee_id": None,
            "parent_id": None, **kw}


def create(tid, when, **kw):
    return ev(tid, "CREATE", when, snap(**kw))


def status(tid, when, to, frm="TODO"):
    return ev(tid, "STATUS_CHANGE", when, {"status": to}, {"status": frm})


def due(tid, when, to, frm=None):
    return ev(tid, "DUE_CHANGE", when, {"due_date": to}, {"due_date": frm})


def run(events, tz=VN, bounds=None):
    s, e = bounds or (START, END)
    return compute_metrics(events, s, e, tz)


def m(events, **kw):
    return run(events, **kw)["metrics"]


# ====================== M05: bộ dữ liệu mẫu (tuần 19–25/10/2026, giờ Việt Nam) ======================
def sample():
    before = L("2026-10-05 09:00")
    ev_ = [
        # T1: hạn 30/10, DONE 20/10, mở lại, DONE lại 21/10 -> MET-01 đếm 1 lần; đúng hạn (MET-05)
        create(1, before, due_date="2026-10-30"),
        status(1, L("2026-10-20 10:00"), "DONE", "TODO"),
        status(1, L("2026-10-20 15:00"), "IN_PROGRESS", "DONE"),
        status(1, L("2026-10-21 10:00"), "DONE", "IN_PROGRESS"),
        # T2: hạn 16/10 (tuần trước), DONE 20/10 -> MET-01, TRỄ hạn, có hạn
        create(2, before, due_date="2026-10-16"),
        status(2, L("2026-10-20 11:00"), "DONE", "TODO"),
        # T3: hạn 24/10, DONE đúng ngày 24/10 23:59 -> MET-01, đúng hạn, hạn nằm trong tuần (MET-04)
        create(3, before, due_date="2026-10-24"),
        status(3, L("2026-10-24 23:59"), "DONE", "TODO"),
        # T4: đang làm, hạn 22/10 -> mở (MET-02), quá hạn (MET-03), hạn trong tuần (MET-04)
        create(4, before, due_date="2026-10-22", status="IN_PROGRESS"),
        # T5: hạn Chủ nhật 25/10 -> hết ngày 25 là quá hạn lúc 00:00 thứ Hai (MET-03), hạn trong tuần (MET-04)
        create(5, before, due_date="2026-10-25"),
        # T6: hạn 23/10 đổi sang 27/10 giữa tuần -> mở nhưng chưa quá hạn, hạn không còn trong tuần
        create(6, before, due_date="2026-10-23"),
        due(6, L("2026-10-21 09:00"), "2026-10-27", "2026-10-23"),
        # T7: subtask của T6, DONE trong tuần, hạn trong tuần -> KHÔNG được đếm ở bất kỳ chỉ số nào
        create(7, before, due_date="2026-10-22", parent_id=6),
        status(7, L("2026-10-22 10:00"), "DONE", "TODO"),
        # T8: bị lưu trữ giữa tuần, hạn 22/10 -> không tính MET-02/03/04
        create(8, before, due_date="2026-10-22"),
        ev(8, "ARCHIVE", L("2026-10-21 12:00"), {"archived_at": "2026-10-21T05:00:00Z"}, {"archived_at": None}),
        # T9: tạo đúng thời điểm end_at -> chưa tồn tại trong tuần này
        create(9, END, due_date="2026-10-22"),
        # T10: DONE từ tuần trước, không có sự kiện trong tuần -> không tính MET-01, không còn mở
        create(10, before, due_date="2026-10-14"),
        status(10, L("2026-10-14 10:00"), "DONE", "TODO"),
    ]
    return [e for e in ev_ if e["occurred_at"] < END or e["task_id"] == 9]


def test_sample_dataset_matches_srs_expected_results():
    r = run(sample())
    assert r["metrics"] == {"MET-01": 3, "MET-02": 3, "MET-03": 2, "MET-04": 3, "MET-05": 2, "MET-06": 66.67}
    assert r["details"]["MET-01"] == [1, 2, 3]
    assert r["details"]["MET-02"] == [4, 5, 6]
    assert r["details"]["MET-03"] == [4, 5]
    assert r["details"]["MET-04"] == [3, 4, 5]
    assert r["details"]["MET-05"] == [1, 3]
    assert r["details"]["MET-06_denominator"] == [1, 2, 3]
    assert r["warnings"] == [] and r["complete"] is True


def test_sample_result_independent_of_input_order_and_does_not_mutate():
    events = sample()
    snapshot = copy.deepcopy(events)
    expected = run(events)
    for seed in range(5):
        shuffled = events[:]
        random.Random(seed).shuffle(shuffled)
        assert run(shuffled) == expected
    assert events == snapshot


# ====================== M02: MET-01 / MET-02 ======================
def test_met01_counts_distinct_tasks_done_multiple_times():
    evs = [create(1, L("2026-10-01 09:00")), status(1, L("2026-10-20 09:00"), "DONE"),
           status(1, L("2026-10-21 09:00"), "IN_PROGRESS", "DONE"), status(1, L("2026-10-22 09:00"), "DONE", "IN_PROGRESS")]
    assert m(evs)["MET-01"] == 1


def test_met01_reopen_in_same_week_still_counts_and_is_open():
    evs = [create(1, L("2026-10-01 09:00")), status(1, L("2026-10-20 09:00"), "DONE"),
           status(1, L("2026-10-21 09:00"), "IN_PROGRESS", "DONE")]
    r = m(evs)
    assert (r["MET-01"], r["MET-02"]) == (1, 1)


def test_met01_task_completed_last_week_not_counted_and_not_open():
    evs = [create(1, L("2026-10-01 09:00")), status(1, L("2026-10-14 09:00"), "DONE")]
    r = m(evs)
    assert (r["MET-01"], r["MET-02"]) == (0, 0)


def test_met01_reopened_then_done_again_this_week_counts():
    evs = [create(1, L("2026-10-01 09:00")), status(1, L("2026-10-14 09:00"), "DONE"),
           status(1, L("2026-10-19 09:00"), "IN_PROGRESS", "DONE"), status(1, L("2026-10-23 09:00"), "DONE", "IN_PROGRESS")]
    assert m(evs)["MET-01"] == 1


def test_empty_week_all_zero_and_met06_null():
    r = run([])
    assert r["metrics"] == {"MET-01": 0, "MET-02": 0, "MET-03": 0, "MET-04": 0, "MET-05": 0, "MET-06": None}
    assert [w["code"] for w in r["warnings"]] == [NO_DUE_DATE_DONE] and r["complete"] is True


def test_met02_excludes_archived_at_end_but_keeps_restored():
    arch = ev(1, "ARCHIVE", L("2026-10-20 09:00"), {"archived_at": "x"}, {"archived_at": None})
    rest = ev(1, "RESTORE", L("2026-10-22 09:00"), {"archived_at": None}, {"archived_at": "x"})
    base = create(1, L("2026-10-01 09:00"))
    assert m([base, arch])["MET-02"] == 0
    assert m([base, arch, rest])["MET-02"] == 1
    arch2 = ev(1, "ARCHIVE", L("2026-10-24 09:00"), {"archived_at": "y"}, {"archived_at": None})
    assert m([base, arch, rest, arch2])["MET-02"] == 0


def test_met02_never_counts_subtasks_and_uses_parent_at_the_time():
    base = [create(1, L("2026-10-01 09:00")), create(2, L("2026-10-01 09:00"), parent_id=1)]
    assert m(base)["MET-02"] == 1
    promoted = base + [ev(2, "PARENT_CHANGE", L("2026-10-20 09:00"), {"parent_id": None}, {"parent_id": 1})]
    assert m(promoted)["MET-02"] == 2


def test_done_as_subtask_then_promoted_not_in_met01_but_done_as_parent_then_demoted_is():
    sub_done = [create(1, L("2026-10-01 09:00"), parent_id=9), status(1, L("2026-10-20 09:00"), "DONE"),
                ev(1, "PARENT_CHANGE", L("2026-10-21 09:00"), {"parent_id": None}, {"parent_id": 9})]
    assert m(sub_done)["MET-01"] == 0
    par_done = [create(1, L("2026-10-01 09:00")), status(1, L("2026-10-20 09:00"), "DONE"),
                ev(1, "PARENT_CHANGE", L("2026-10-21 09:00"), {"parent_id": 9}, {"parent_id": None})]
    r = m(par_done)
    assert (r["MET-01"], r["MET-02"]) == (1, 0)


def test_task_created_in_week_counts_and_created_at_end_does_not():
    assert m([create(1, L("2026-10-22 09:00"))])["MET-02"] == 1
    assert m([create(1, END)])["MET-02"] == 0
    assert run([create(1, END)])["warnings"][0]["code"] == NO_DUE_DATE_DONE   # chỉ cảnh báo mẫu số, không phải thiếu dữ liệu


# ====================== ranh giới tuần ======================
@pytest.mark.parametrize("when,expected", [
    (START - timedelta(seconds=1), 0),     # ngay trước đầu tuần: thuộc tuần trước
    (START, 1),                            # đúng đầu tuần: thuộc tuần này
    (END - timedelta(seconds=1), 1),       # ngay trước cuối tuần
    (END, 0),                              # đúng cuối tuần: thuộc tuần sau
])
def test_met01_week_boundaries(when, expected):
    evs = [create(1, L("2026-10-01 09:00")), status(1, when, "DONE")]
    assert m(evs)["MET-01"] == expected


def test_status_change_at_end_is_excluded_from_end_state():
    evs = [create(1, L("2026-10-01 09:00")), status(1, END, "DONE")]
    r = m(evs)
    assert (r["MET-01"], r["MET-02"]) == (0, 1)               # chưa DONE tại end-, vẫn mở


def test_same_timestamp_events_ordered_by_event_seq():
    t = L("2026-10-22 10:00")
    evs = [create(1, L("2026-10-01 09:00")), status(1, t, "DONE"), status(1, t, "IN_PROGRESS", "DONE")]
    assert m(evs)["MET-02"] == 1
    evs2 = [create(1, L("2026-10-01 09:00")), status(1, t, "IN_PROGRESS"), status(1, t, "DONE", "IN_PROGRESS")]
    assert m(evs2)["MET-02"] == 0


# ====================== M03: MET-03 / MET-04 ======================
def test_overdue_is_after_end_of_due_day():
    base = create(1, L("2026-10-01 09:00"), due_date="2026-10-25")       # Chủ nhật cuối tuần
    assert m([base])["MET-03"] == 1                                      # qua hết ngày 25 -> quá hạn lúc 00:00 thứ Hai
    assert m([create(1, L("2026-10-01 09:00"), due_date="2026-10-26")])["MET-03"] == 0   # hạn thứ Hai tuần sau: chưa quá hạn
    assert m([create(1, L("2026-10-01 09:00"), due_date="2026-10-24")])["MET-03"] == 1


def test_overdue_needs_due_date_and_open_status():
    assert m([create(1, L("2026-10-01 09:00"))])["MET-03"] == 0           # hạn rỗng
    done = [create(1, L("2026-10-01 09:00"), due_date="2026-10-20"), status(1, L("2026-10-21 09:00"), "DONE")]
    assert m(done)["MET-03"] == 0                                         # đã DONE nên không thuộc MET-02


def test_met03_uses_due_date_at_end_after_changes():
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-10-20"), due(1, L("2026-10-22 09:00"), "2026-11-05", "2026-10-20")]
    r = m(evs)
    assert (r["MET-03"], r["MET-04"]) == (0, 0)
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-11-05"), due(1, L("2026-10-22 09:00"), "2026-10-21", "2026-11-05")]
    r = m(evs)
    assert (r["MET-03"], r["MET-04"]) == (1, 1)


@pytest.mark.parametrize("d,expected", [
    ("2026-10-18", 0),   # Chủ nhật tuần trước
    ("2026-10-19", 1),   # thứ Hai đầu tuần
    ("2026-10-25", 1),   # Chủ nhật cuối tuần
    ("2026-10-26", 0),   # thứ Hai tuần sau
])
def test_met04_due_window_boundaries(d, expected):
    assert m([create(1, L("2026-10-01 09:00"), due_date=d)])["MET-04"] == expected


def test_met04_counts_done_tasks_too_and_counts_task_once_after_due_changes():
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-10-20"), status(1, L("2026-10-20 09:00"), "DONE"),
           due(1, L("2026-10-21 09:00"), "2026-10-22", "2026-10-20"), due(1, L("2026-10-22 09:00"), "2026-10-23", "2026-10-22")]
    assert m(evs)["MET-04"] == 1


def test_met04_excludes_archived_subtasks_and_empty_due():
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-10-21"),
           ev(1, "ARCHIVE", L("2026-10-22 09:00"), {"archived_at": "x"}, {"archived_at": None}),
           create(2, L("2026-10-01 09:00"), due_date="2026-10-21", parent_id=1),
           create(3, L("2026-10-01 09:00"))]
    assert m(evs)["MET-04"] == 0


# ====================== M04: MET-05 / MET-06 ======================
def test_met05_boundary_end_of_due_day_in_project_timezone():
    base = create(1, L("2026-10-01 09:00"), due_date="2026-10-22")
    assert m([base, status(1, L("2026-10-22 23:59"), "DONE")])["MET-05"] == 1
    assert m([base, status(1, L("2026-10-23 00:00"), "DONE")])["MET-05"] == 0


def test_met05_uses_due_date_at_the_done_event_not_the_current_one():
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-10-20"), status(1, L("2026-10-22 09:00"), "DONE"),
           due(1, L("2026-10-23 09:00"), "2026-10-30", "2026-10-20")]      # dời hạn SAU khi đã trễ
    r = m(evs)
    assert (r["MET-05"], r["MET-06"]) == (0, 0.0)
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-10-30"), status(1, L("2026-10-22 09:00"), "DONE"),
           due(1, L("2026-10-23 09:00"), "2026-10-20", "2026-10-30")]      # rút hạn SAU khi đã xong đúng hạn
    assert m(evs)["MET-05"] == 1


def test_met05_one_on_time_done_event_is_enough_when_done_twice():
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-10-21"), status(1, L("2026-10-20 09:00"), "DONE"),
           status(1, L("2026-10-21 09:00"), "IN_PROGRESS", "DONE"), status(1, L("2026-10-23 09:00"), "DONE", "IN_PROGRESS")]
    r = m(evs)
    assert (r["MET-01"], r["MET-05"], r["MET-06"]) == (1, 1, 100.0)


def test_met06_null_when_met01_is_zero_no_division_by_zero():
    r = run([create(1, L("2026-10-01 09:00"), due_date="2026-10-21")])
    assert r["metrics"]["MET-01"] == 0 and r["metrics"]["MET-06"] is None
    assert any(w["code"] == NO_DUE_DATE_DONE for w in r["warnings"])


def test_met06_null_when_done_tasks_have_no_due_date():
    evs = [create(1, L("2026-10-01 09:00")), status(1, L("2026-10-20 09:00"), "DONE")]
    r = run(evs)
    assert (r["metrics"]["MET-01"], r["metrics"]["MET-05"], r["metrics"]["MET-06"]) == (1, 0, None)
    assert any(w["code"] == NO_DUE_DATE_DONE for w in r["warnings"])


def test_met06_denominator_excludes_done_without_due_and_rounds_to_2_decimals():
    evs = [create(1, L("2026-10-01 09:00"), due_date="2026-10-21"), status(1, L("2026-10-20 09:00"), "DONE"),
           create(2, L("2026-10-01 09:00"), due_date="2026-10-19"), status(2, L("2026-10-20 09:00"), "DONE"),
           create(3, L("2026-10-01 09:00"), due_date="2026-10-19"), status(3, L("2026-10-20 09:00"), "DONE"),
           create(4, L("2026-10-01 09:00")), status(4, L("2026-10-20 09:00"), "DONE")]
    r = m(evs)
    assert (r["MET-01"], r["MET-05"], r["MET-06"]) == (4, 1, 33.33)       # 1/3 (task không có hạn không vào mẫu số)


# ====================== múi giờ ======================
def test_timezone_changes_which_week_an_event_belongs_to():
    t = datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc)                # 03:00 thứ Hai 19/10 giờ VN, 20:00 CN 18/10 giờ UTC
    evs = [create(1, datetime(2026, 10, 1, tzinfo=timezone.utc)), status(1, t, "DONE")]
    assert m(evs, tz=VN)["MET-01"] == 1
    utc_bounds = week_bounds(WEEK, "UTC", NOW)
    assert m(evs, tz="UTC", bounds=utc_bounds)["MET-01"] == 0            # tuần UTC bắt đầu 19/10 00:00Z, sự kiện nằm trước đó


def test_timezone_changes_on_time_decision():
    base = create(1, datetime(2026, 10, 1, tzinfo=timezone.utc), due_date="2026-10-20")
    done = status(1, datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc), "DONE")   # 01:00 ngày 21 giờ VN (trễ), 18:00 ngày 20 giờ UTC (đúng hạn)
    assert m([base, done], tz=VN)["MET-05"] == 0
    utc_bounds = week_bounds(WEEK, "UTC", NOW)
    assert m([base, done], tz="UTC", bounds=utc_bounds)["MET-05"] == 1


def test_week_with_daylight_saving_uses_local_days():
    ny = "America/New_York"
    start, end = week_bounds(datetime(2026, 3, 2).date(), ny, NOW)       # tuần có đổi giờ hè (167 giờ)
    assert end - start == timedelta(hours=167)
    base = create(1, datetime(2026, 2, 1, tzinfo=timezone.utc), due_date="2026-03-08")   # Chủ nhật cuối tuần
    assert compute_metrics([base], start, end, ny)["metrics"]["MET-03"] == 1


# ====================== thiếu dữ liệu: cảnh báo, không suy diễn ======================
def test_missing_create_is_excluded_with_warning_and_marks_incomplete():
    evs = [status(5, L("2026-10-20 09:00"), "DONE"), create(1, L("2026-10-01 09:00"), due_date="2026-10-21")]
    r = run(evs)
    w = [x for x in r["warnings"] if x["code"] == MISSING_CREATE]
    assert len(w) == 1 and w[0]["task_id"] == 5
    assert "MET-01" in w[0]["affects"] and "MET-06" in w[0]["affects"]
    assert r["complete"] is False
    assert r["metrics"]["MET-01"] == 0                       # không đoán task 5 là Task cha đã DONE


def test_unrelated_future_orphan_event_does_not_warn():
    evs = [status(5, END + timedelta(days=1), "DONE")]
    assert [w["code"] for w in run([e for e in evs if e["occurred_at"] < END])["warnings"]] == [NO_DUE_DATE_DONE]


# ====================== kết nối hệ thống ======================
def test_service_reuses_week_bounds_and_has_no_public_endpoint():
    app = Path(__file__).resolve().parents[1] / "app"
    svc = (app / "services" / "metrics_service.py").read_text(encoding="utf-8")
    assert "from app.core.weekly_period import week_bounds" in svc and "TaskHistory.occurred_at < end_at" in svc
    for p in (app / "api").glob("*.py"):
        assert "metric" not in p.name
    assert "metrics" not in (app / "main.py").read_text(encoding="utf-8")
