"""Main loop: run every provider on its own interval, publish state, send alerts.

python -m visa_slots.run --minutes 340      # loop (GitHub Actions)
python -m visa_slots.run --once             # single round (local test)
"""
import argparse
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

from . import notify, publish, state as state_mod
from .countries import COUNTRIES, manual_results
from .models import ERROR, Result, now_iso
from .providers import PROVIDERS

log = logging.getLogger("visa_slots")
HEARTBEAT = 120  # seconds between publishes when nothing changed
FLAG = {c["code"]: c["flag"] for c in COUNTRIES}
NAME = {c["code"]: c["name"] for c in COUNTRIES}


def run_provider(p) -> list[Result]:
    try:
        return p.check()
    except Exception as e:  # one broken provider must not stop the others
        log.exception("%s failed", p.NAME)
        return [Result(key=k, country=c, provider=p.NAME, status=ERROR, detail=f"{type(e).__name__}: {e}"[:300])
                for k, c in p.targets()]


def alert_text(a: dict) -> str:
    r = a["result"]
    who = f"{FLAG.get(r['country'], '')} <b>{notify.esc(NAME.get(r['country'], r['country']))}</b>"
    where = " · ".join(x for x in (r.get("center"), r.get("category")) if x)
    where = f"\n{notify.esc(where)}" if where else ""
    link = f"\n{r['booking_url']}" if r.get("booking_url") else ""
    date = f"\nEarliest: <b>{r['earliest']}</b>" if r.get("earliest") else ""
    if a["kind"] == "opened":
        return f"🟢 VISA SLOT OPEN: {who}{where}{date}{link}\n\nBook now, slots go in minutes."
    if a["kind"] == "earlier":
        return f"🟢 VISA earlier slot: {who}{where}{date}{link}"
    if a["kind"] == "closed":
        return f"⚪️ VISA closed again: {who}{where} (was open {a['minutes']} min)"
    if a["kind"] == "broken":
        return f"⚠️ VISA checker broken for {who}{where} for 1h+: {notify.esc(r.get('detail', ''))[:200]}"
    return f"✅ VISA checker working again: {who}{where}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=340)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--only", help="comma-separated provider names")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    providers = [p for p in PROVIDERS if not args.only or p.NAME in args.only.split(",")]
    st = publish.load()
    st["run_url"] = os.environ.get("RUN_URL", "")
    st["started_at"] = now_iso()
    st["countries"] = [{k: c.get(k, "") for k in ("code", "name", "flag", "provider", "check", "url", "note")} for c in COUNTRIES]
    known = {k for p in providers for k, _ in p.targets()} | {r.key for r in manual_results()}
    st["targets"] = {k: v for k, v in st.get("targets", {}).items() if k in known}
    st, _ = state_mod.apply(st, manual_results(), now_iso())
    due = {p.NAME: 0.0 for p in providers}
    deadline = time.time() + args.minutes * 60
    last_publish = 0.0

    with ThreadPoolExecutor(max_workers=8) as pool:
        while True:
            now = time.time()
            ready = [p for p in providers if due[p.NAME] <= now]
            results: list[Result] = []
            for p, res in zip(ready, pool.map(run_provider, ready)):
                due[p.NAME] = time.time() + p.INTERVAL
                results += res
                log.info("%s: %s", p.NAME, ", ".join(f"{x.key}={x.status}" for x in res))
            changed = False
            if results:
                before = {k: (v.get("status"), v.get("earliest")) for k, v in st.get("targets", {}).items()}
                st, alerts = state_mod.apply(st, results, now_iso())
                after = {k: (v.get("status"), v.get("earliest")) for k, v in st["targets"].items()}
                changed = before != after
                for a in alerts:
                    notify.send(alert_text(a), silent=a["silent"])
            if changed or args.once or time.time() - last_publish >= HEARTBEAT:
                try:
                    publish.save(st)
                    last_publish = time.time()
                except Exception:
                    log.exception("publish failed")
            if args.once or time.time() >= deadline:
                break
            time.sleep(max(1.0, min(due.values()) - time.time()))


if __name__ == "__main__":
    main()
