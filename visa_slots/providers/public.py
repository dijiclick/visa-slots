"""Providers that read public trackers which already watch Istanbul. No account, no phone.

vizetakip.app      iDATA Italy, BLS Spain (+ others when they post)  -> list of recent finds
visacatcher.bot    free VFS countries for Istanbul                   -> live state per country
t.me/s/TurkiyeVFSBot  Visa Catcher's free alert channel              -> list of recent posts
"""
import html
import json
import re
from datetime import datetime, timedelta, timezone

from ..models import CLOSED, OPEN, Result
from .base import fold, get, is_istanbul

FRESH = timedelta(minutes=30)   # a find younger than this counts as "open now"


def _recent(at: datetime) -> bool:
    return datetime.now(timezone.utc) - at <= FRESH


class Vizetakip:
    NAME = "vizetakip"
    INTERVAL = 60
    URL = "https://vizetakip.app/"
    # Turkish country name on the site -> ISO-2
    COUNTRY = {"italya": "IT", "ispanya": "ES", "yunanistan": "GR", "macaristan": "HU", "portekiz": "PT",
               "fransa": "FR", "hollanda": "NL", "almanya": "DE", "avusturya": "AT", "belcika": "BE",
               "polonya": "PL", "cekya": "CZ", "danimarka": "DK", "finlandiya": "FI", "isvec": "SE",
               "isvicre": "CH", "norvec": "NO", "hirvatistan": "HR", "slovenya": "SI", "slovakya": "SK",
               "bulgaristan": "BG", "estonya": "EE", "letonya": "LV", "litvanya": "LT", "luksemburg": "LU",
               "malta": "MT", "romanya": "RO", "izlanda": "IS"}
    WATCH = ("IT", "ES", "GR", "HU", "PT")
    LINKS = {"IT": "https://it-tr-appointment.idata.com.tr/tr", "ES": "https://turkey.blsspainglobal.com/Global/account/login",
             "GR": "https://basvuru.kosmosvize.com.tr/appointmentform", "HU": "https://www.as-visa.com/appointment",
             "PT": "https://www.as-visa.com/appointment"}

    def targets(self):
        return [(f"{c.lower()}/vizetakip", c) for c in self.WATCH]

    @staticmethod
    def parse(page: str) -> list[dict]:
        out = []
        for card in re.findall(r'<article class="appt-card.*?</article>', page, re.S):
            country = re.search(r'class="appt-country"[^>]*>([^<]+)<', card)
            city = re.search(r'class="appt-city">([^<]*)<', card)
            typ = re.search(r'class="appt-type">([^<]*)<', card)
            times = re.findall(r'<time datetime="([^"]+)"', card)
            if not (country and city and len(times) >= 2):
                continue
            d, m, y = times[0].split("/")
            out.append({
                "country": html.unescape(country.group(1)).strip(),
                "city": html.unescape(city.group(1)).strip(),
                "type": html.unescape(typ.group(1)).strip() if typ else "",
                "slot_date": f"{y}-{m}-{d}",
                "found_at": datetime.fromisoformat(times[1].replace("Z", "+00:00")),
            })
        return out

    def check(self) -> list[Result]:
        finds = [f for f in self.parse(get(self.URL).text) if is_istanbul(f["city"])]
        results = []
        for code in self.WATCH:
            mine = [f for f in finds if self.COUNTRY.get(fold(f["country"])) == code and _recent(f["found_at"])]
            if mine:
                best = min(mine, key=lambda f: f["slot_date"])
                results.append(Result(key=f"{code.lower()}/vizetakip", country=code, provider="vizetakip.app",
                                      status=OPEN, center=best["city"].replace("İ̇S", "Is").title(), category=best["type"],
                                      earliest=best["slot_date"], detail=f"seen {best['found_at']:%H:%M} UTC by vizetakip.app",
                                      booking_url=self.LINKS[code]))
            else:
                results.append(Result(key=f"{code.lower()}/vizetakip", country=code, provider="vizetakip.app",
                                      status=CLOSED, center="Istanbul", detail="no find in the last 30 min",
                                      booking_url=self.LINKS[code]))
        return results


class VisaCatcher:
    NAME = "visacatcher"
    INTERVAL = 60
    URL = "https://visacatcher.bot/appointments/istanbul"

    def __init__(self):
        self.seen: set[str] = set()   # countries that came with real (non-paid) data at least once

    def targets(self):
        return [(f"{c.lower()}/visacatcher", c) for c in ("CH", "FI", "SI", "CZ")]

    @staticmethod
    def parse(page: str) -> list[dict]:
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', page, re.S)
        blob = "".join(json.loads('"' + c + '"') for c in chunks)
        i = blob.find('"initialData":')
        if i < 0:
            raise ValueError("initialData not found (page layout changed)")
        return json.JSONDecoder().raw_decode(blob, i + len('"initialData":'))[0]

    def check(self) -> list[Result]:
        rows = [r for r in self.parse(get(self.URL).text) if not r.get("isPaidOnly")]
        results = []
        for r in rows:
            code = r.get("countryAlpha2", "")
            if not code:
                continue
            waitlist = bool(r.get("isWaitlist"))
            status = OPEN if r.get("hasSlots") else CLOSED
            detail = "waitlist open" if waitlist and status == OPEN else (r.get("dateRangeText") or "")
            results.append(Result(key=f"{code.lower()}/visacatcher", country=code, provider="visacatcher.bot",
                                  status=status, center=r.get("cityName", ""),
                                  category=("Waitlist · " if waitlist else "") + (r.get("category") or {}).get("name", "")[:60],
                                  detail=f"{detail} (checked {r.get('lastCheckedSeconds')}s before)".strip(),
                                  booking_url=r.get("vfsLink", "")))
        return results


class TelegramChannel:
    NAME = "tg-turkiyevfsbot"
    INTERVAL = 60
    URL = "https://t.me/s/TurkiyeVFSBot"
    COUNTRY = {"NORWAY": "NO", "FINLAND": "FI", "SWITZERLAND": "CH", "SLOVENIA": "SI", "CZECH REPUBLIC": "CZ",
               "FRANCE": "FR", "NETHERLANDS": "NL", "AUSTRIA": "AT", "BELGIUM": "BE", "POLAND": "PL",
               "DENMARK": "DK", "SWEDEN": "SE", "CROATIA": "HR", "LATVIA": "LV", "LITHUANIA": "LT",
               "ESTONIA": "EE", "MALTA": "MT", "LUXEMBOURG": "LU", "BULGARIA": "BG", "CZECHIA": "CZ"}
    WATCH = ("NO", "FI", "CH", "SI")
    MISSION = {"NO": "nor", "FI": "fin", "CH": "che", "SI": "svn", "CZ": "cze"}

    def targets(self):
        return [(f"{c.lower()}/tg", c) for c in self.WATCH]

    @classmethod
    def parse(cls, page: str) -> list[dict]:
        out = []
        for m in re.findall(r'<div class="tgme_widget_message_wrap.*?</time>', page, re.S):
            t = re.search(r'<time[^>]*datetime="([^"]+)"', m)
            txt = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', m, re.S)
            if not (t and txt):
                continue
            body = re.sub(r"<[^>]+>", "", html.unescape(re.sub(r"<br\s*/?>", "\n", txt.group(1))))
            head = re.search(r"([A-Z][A-Z ]{3,})\n", body)
            code = cls.COUNTRY.get(head.group(1).strip()) if head else None
            at = datetime.fromisoformat(t.group(1))
            for place, cat in re.findall(r"🟢\s*([^:\n]+):\s*([^\n]+)", body):
                date = re.search(r"Earliest available slot:\s*(\d{2})\.(\d{2})", body)
                earliest = ""
                if date:
                    d, mo = int(date.group(1)), int(date.group(2))
                    y = at.year + (1 if mo < at.month else 0)
                    earliest = f"{y}-{mo:02d}-{d:02d}"
                out.append({"country": code, "place": place.strip(), "category": cat.strip(), "earliest": earliest, "at": at})
        return out

    def check(self) -> list[Result]:
        posts = [p for p in self.parse(get(self.URL).text) if p["country"] and is_istanbul(p["place"])]
        results = []
        for code in self.WATCH:
            url = f"https://visa.vfsglobal.com/tur/en/{self.MISSION[code]}/login"
            mine = [p for p in posts if p["country"] == code and _recent(p["at"])]
            if mine:
                p = max(mine, key=lambda p: p["at"])
                results.append(Result(key=f"{code.lower()}/tg", country=code, provider="t.me/TurkiyeVFSBot", status=OPEN,
                                      center=p["place"], category=p["category"], earliest=p["earliest"],
                                      detail=f"posted {p['at']:%H:%M} UTC", booking_url=url))
            else:
                results.append(Result(key=f"{code.lower()}/tg", country=code, provider="t.me/TurkiyeVFSBot", status=CLOSED,
                                      center="Istanbul", detail="no Istanbul post in the last 30 min", booking_url=url))
        return results
