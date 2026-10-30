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
