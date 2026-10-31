"""Turn a round of check results into the new published state plus the alerts to send."""
from datetime import datetime, timedelta

from .models import CLOSED, ERROR, OPEN, Result

BROKEN_AFTER = timedelta(minutes=60)   # a check failing this long gets one "broken" alert
DOWN_AFTER = timedelta(minutes=5)      # a check failing this long is logged in the history
MAX_EVENTS = 300


def _t(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def apply(state: dict, results: list[Result], now: str) -> tuple[dict, list[dict]]:
    """Returns (state, alerts). Alerts are {"kind", "text_args", "silent"} dicts for the notifier."""
    targets = dict(state.get("targets", {}))
    events = list(state.get("events", []))
    alerts: list[dict] = []

    for r in results:
        prev = targets.get(r.key, {})
        cur = r.to_dict()
        for k in ("last_open_at", "opened_at", "error_since", "broken_alerted", "down_logged", "last_ok_at"):
            if k in prev:
                cur[k] = prev[k]

        was_open = prev.get("status") == OPEN
        base = {"at": now, "key": r.key, "country": r.country, "provider": r.provider,
                "center": r.center, "category": r.category}
        if r.status == ERROR:
            cur.setdefault("error_since", now)
            # keep showing the last real answer until the check recovers
            if prev.get("status") in (OPEN, CLOSED):
                cur["status"] = prev["status"]
                cur["earliest"] = prev.get("earliest", "")
                cur["stale"] = True
            if not cur.get("down_logged") and _t(now) - _t(cur["error_since"]) >= DOWN_AFTER:
                cur["down_logged"] = True
                events.append({**base, "at": cur["error_since"], "kind": "down", "detail": r.detail[:200]})
            if not cur.get("broken_alerted") and _t(now) - _t(cur["error_since"]) >= BROKEN_AFTER:
                cur["broken_alerted"] = True
                alerts.append({"kind": "broken", "result": cur, "silent": True})
        else:
            if cur.get("broken_alerted"):
                alerts.append({"kind": "recovered", "result": cur, "silent": True})
            if cur.get("down_logged"):
                minutes = int((_t(now) - _t(cur["error_since"])).total_seconds() // 60)
                events.append({**base, "kind": "up", "since": cur["error_since"], "down_minutes": minutes})
            cur.pop("error_since", None)
            cur.pop("broken_alerted", None)
            cur.pop("down_logged", None)
            cur["last_ok_at"] = now

            if r.status == OPEN:
                cur["last_open_at"] = now
                if not was_open:
                    cur["opened_at"] = now
                    events.append({**base, "kind": "opened", "earliest": r.earliest})
                    alerts.append({"kind": "opened", "result": cur, "silent": False})
                elif r.earliest and prev.get("earliest") and r.earliest < prev["earliest"]:
                    events.append({**base, "kind": "earlier", "earliest": r.earliest})
                    alerts.append({"kind": "earlier", "result": cur, "silent": False})
            elif r.status == CLOSED and was_open:
                opened_at = prev.get("opened_at", now)
                minutes = int((_t(now) - _t(opened_at)).total_seconds() // 60)
                cur.pop("opened_at", None)
                events.append({**base, "kind": "closed", "opened_at": opened_at, "open_minutes": minutes,
                               "earliest": prev.get("earliest", "")})
                alerts.append({"kind": "closed", "result": cur, "minutes": minutes, "silent": True})
        targets[r.key] = cur

    new = dict(state)
    new["targets"] = targets
    new["events"] = events[-MAX_EVENTS:]
    new["updated_at"] = now
    return new, alerts
