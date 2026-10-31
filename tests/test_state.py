from visa_slots.models import CLOSED, ERROR, OPEN, Result
from visa_slots.state import apply


def r(status, earliest=""):
    return Result(key="fra/IST/tourism", country="FR", provider="vfs", status=status, earliest=earliest)


def kinds(alerts):
    return [a["kind"] for a in alerts]


def test_open_alerts_once_then_closed_logs():
    s, a = apply({}, [r(CLOSED)], "2026-10-30T10:00:00+00:00")
    assert a == []
    s, a = apply(s, [r(OPEN, "2026-12-01")], "2026-10-30T10:01:00+00:00")
    assert kinds(a) == ["opened"]
    s, a = apply(s, [r(OPEN, "2026-12-01")], "2026-10-30T10:02:00+00:00")
    assert a == []
    s, a = apply(s, [r(OPEN, "2026-11-20")], "2026-10-30T10:03:00+00:00")
    assert kinds(a) == ["earlier"]
    s, a = apply(s, [r(CLOSED)], "2026-10-30T10:06:00+00:00")
    assert kinds(a) == ["closed"] and a[0]["minutes"] == 5
    assert [e["kind"] for e in s["events"]] == ["opened", "earlier", "closed"]


def test_first_ever_open_alerts():
    s, a = apply({}, [r(OPEN)], "2026-10-30T10:00:00+00:00")
    assert kinds(a) == ["opened"]


def test_error_keeps_last_answer_and_alerts_broken_once():
    s, _ = apply({}, [r(CLOSED)], "2026-10-30T10:00:00+00:00")
    s, a = apply(s, [r(ERROR)], "2026-10-30T10:01:00+00:00")
    assert a == [] and s["targets"]["fra/IST/tourism"]["status"] == CLOSED
    assert s["targets"]["fra/IST/tourism"]["stale"]
    s, a = apply(s, [r(ERROR)], "2026-10-30T11:02:00+00:00")
    assert kinds(a) == ["broken"]
    s, a = apply(s, [r(ERROR)], "2026-10-30T11:30:00+00:00")
    assert a == []
    s, a = apply(s, [r(CLOSED)], "2026-10-30T11:31:00+00:00")
    assert kinds(a) == ["recovered"]
    assert "error_since" not in s["targets"]["fra/IST/tourism"]


def test_error_while_open_does_not_close():
    s, _ = apply({}, [r(OPEN)], "2026-10-30T10:00:00+00:00")
    s, a = apply(s, [r(ERROR)], "2026-10-30T10:01:00+00:00")
    assert a == [] and s["targets"]["fra/IST/tourism"]["status"] == OPEN
    s, a = apply(s, [r(OPEN)], "2026-10-30T10:02:00+00:00")
    assert a == []


def test_closed_event_has_open_window():
    s, _ = apply({}, [r(OPEN, "2026-12-01")], "2026-10-30T10:00:00+00:00")
    s, _ = apply(s, [r(CLOSED)], "2026-10-30T10:07:00+00:00")
    e = s["events"][-1]
    assert e["kind"] == "closed" and e["opened_at"] == "2026-10-30T10:00:00+00:00"
    assert e["open_minutes"] == 7 and e["earliest"] == "2026-12-01"


def test_outage_logged_after_5_min_with_duration():
    s, _ = apply({}, [r(CLOSED)], "2026-10-30T10:00:00+00:00")
    s, _ = apply(s, [Result(key="fra/IST/tourism", country="FR", provider="vfs", status=ERROR, detail="HTTP 403")],
                 "2026-10-30T10:01:00+00:00")
    s, _ = apply(s, [r(ERROR)], "2026-10-30T10:03:00+00:00")
    assert [e["kind"] for e in s.get("events", [])] == []      # short blips stay out of the history
    s, _ = apply(s, [r(ERROR)], "2026-10-30T10:06:00+00:00")
    s, _ = apply(s, [r(ERROR)], "2026-10-30T10:08:00+00:00")
    assert [e["kind"] for e in s["events"]] == ["down"]
    assert s["events"][0]["at"] == "2026-10-30T10:01:00+00:00"
    s, _ = apply(s, [r(CLOSED)], "2026-10-30T10:21:00+00:00")
    assert [e["kind"] for e in s["events"]] == ["down", "up"] and s["events"][1]["down_minutes"] == 20
