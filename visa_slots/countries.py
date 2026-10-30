"""All 29 Schengen states, as seen from Istanbul (researched 2026-10-30).

provider: who takes the appointment in Istanbul.
check:    "vfs" | "kosmos" -> checked automatically; "manual" -> only listed with the booking link and why.
"""
from .models import MANUAL, Result

VFS = "https://visa.vfsglobal.com/tur/en/{m}/login"

COUNTRIES = [
    # code, name, flag, provider, check, vfs mission, booking url, note
    dict(code="AT", name="Austria", flag="🇦🇹", provider="VFS Global", check="vfs", mission="aut"),
    dict(code="BE", name="Belgium", flag="🇧🇪", provider="VFS Global", check="vfs", mission="bel"),
    dict(code="BG", name="Bulgaria", flag="🇧🇬", provider="VFS Global", check="vfs", mission="bgr"),
    dict(code="HR", name="Croatia", flag="🇭🇷", provider="VFS Global", check="vfs", mission="hrv"),
    dict(code="CZ", name="Czechia", flag="🇨🇿", provider="VFS Global", check="vfs", mission="cze"),
    dict(code="DK", name="Denmark", flag="🇩🇰", provider="VFS Global", check="vfs", mission="dnk"),
    dict(code="EE", name="Estonia", flag="🇪🇪", provider="VFS Global", check="vfs", mission="est"),
    dict(code="FI", name="Finland", flag="🇫🇮", provider="VFS Global", check="vfs", mission="fin"),
    dict(code="FR", name="France", flag="🇫🇷", provider="VFS Global", check="vfs", mission="fra"),
    dict(code="DE", name="Germany", flag="🇩🇪", provider="iDATA", check="manual",
         url="https://de-tr-appointment.idata.com.tr/tr",
         note="Waiting list: you register at iDATA and they e-mail you a date in order. No open slots to watch."),
    dict(code="GR", name="Greece", flag="🇬🇷", provider="Kosmos Vize", check="kosmos",
         url="https://basvuru.kosmosvize.com.tr/appointmentform"),
    dict(code="HU", name="Hungary", flag="🇭🇺", provider="AS Visa", check="manual",
         url="https://www.as-visa.com/DynamicPage.aspx?ID=51",
         note="AS Visa site is behind a Cloudflare challenge that blocks automated checks."),
    dict(code="IS", name="Iceland", flag="🇮🇸", provider="VFS Global (via Denmark)", check="manual",
         url=VFS.format(m="dnk"), note="No Icelandic mission in Turkey; Denmark handles it, so watch Denmark."),
    dict(code="IT", name="Italy", flag="🇮🇹", provider="iDATA", check="manual",
         url="https://it-tr-appointment.idata.com.tr/tr",
         note="iDATA needs login + image captcha + e-mail code, and blocks datacenter IPs."),
    dict(code="LV", name="Latvia", flag="🇱🇻", provider="VFS Global", check="vfs", mission="lva"),
    dict(code="LI", name="Liechtenstein", flag="🇱🇮", provider="VFS Global (via Switzerland)", check="manual",
         url=VFS.format(m="che"), note="Switzerland issues the visa, so watch Switzerland."),
    dict(code="LT", name="Lithuania", flag="🇱🇹", provider="VFS Global", check="vfs", mission="ltu"),
    dict(code="LU", name="Luxembourg", flag="🇱🇺", provider="VFS Global", check="vfs", mission="lux"),
    dict(code="MT", name="Malta", flag="🇲🇹", provider="VFS Global", check="vfs", mission="mlt"),
    dict(code="NL", name="Netherlands", flag="🇳🇱", provider="VFS Global", check="vfs", mission="nld"),
    dict(code="NO", name="Norway", flag="🇳🇴", provider="VFS Global", check="vfs", mission="nor"),
    dict(code="PL", name="Poland", flag="🇵🇱", provider="VFS Global", check="vfs", mission="pol"),
    dict(code="PT", name="Portugal", flag="🇵🇹", provider="AS Visa", check="manual",
         url="https://www.as-visa.com/",
         note="AS Visa site is behind a Cloudflare challenge that blocks automated checks."),
    dict(code="RO", name="Romania", flag="🇷🇴", provider="Consulate (e-Viza)", check="manual",
         url="https://evisa.mae.ro/",
         note="You file the application online first; the consulate then offers a date. No slots to watch."),
    dict(code="SK", name="Slovakia", flag="🇸🇰", provider="BLS International", check="manual",
         url="https://software.blsslovakiavisa.com/appointments/login",
         note="BLS needs an account and an hCaptcha for every look at the calendar."),
    dict(code="SI", name="Slovenia", flag="🇸🇮", provider="VFS Global", check="vfs", mission="svn"),
    dict(code="ES", name="Spain", flag="🇪🇸", provider="BLS International", check="manual",
         url="https://turkey.blsspainglobal.com/Global/account/login",
         note="BLS needs an account, an image captcha and e-mail verification."),
    dict(code="SE", name="Sweden", flag="🇸🇪", provider="VFS Global", check="vfs", mission="swe"),
    dict(code="CH", name="Switzerland", flag="🇨🇭", provider="VFS Global", check="vfs", mission="che"),
]

for c in COUNTRIES:
    if c["check"] == "vfs":
        c.setdefault("url", VFS.format(m=c["mission"]))

BY_MISSION = {c["mission"]: c for c in COUNTRIES if c.get("mission")}


def manual_results() -> list[Result]:
    return [Result(key=f"{c['code'].lower()}/manual", country=c["code"], provider=c["provider"], status=MANUAL,
                   detail=c.get("note", ""), booking_url=c["url"])
            for c in COUNTRIES if c["check"] == "manual"]
