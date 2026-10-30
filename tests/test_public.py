from datetime import datetime, timezone
from pathlib import Path

from visa_slots.providers.base import is_istanbul
from visa_slots.providers.public import TelegramChannel, VisaCatcher, Vizetakip

FX = Path(__file__).parent / "fixtures"


def test_vizetakip_parse():
    finds = Vizetakip.parse((FX / "vt.html").read_text())
    assert len(finds) == 50
    ist = [f for f in finds if is_istanbul(f["city"])]
    assert ist and all(f["slot_date"][:4] == "2026" for f in ist)
    assert any(f["country"] == "İtalya" for f in ist)
    assert all(f["found_at"].tzinfo for f in finds)


def test_visacatcher_parse():
    rows = VisaCatcher.parse((FX / "vc.html").read_text())
    ch = next(r for r in rows if r["countryAlpha2"] == "CH")
    assert ch["hasSlots"] is True and ch["isWaitlist"] is True
    assert any(r.get("isPaidOnly") for r in rows)


def test_telegram_parse():
    posts = TelegramChannel.parse((FX / "tg.html").read_text())
    assert posts
    no = [p for p in posts if p["country"] == "NO"]
    assert no and no[-1]["earliest"] == "2026-11-02"


def test_is_istanbul():
    assert is_istanbul("İ̇Stanbul - Gayrettepe")
    assert is_istanbul("Istanbul Harbiye")
    assert is_istanbul("Beyoglu")
    assert not is_istanbul("Antalya")
