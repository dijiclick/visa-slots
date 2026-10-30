"""Watch VFS's own switch for showing the earliest date before login (off for every Turkey mission in Oct 2026).
If it flips on, no-login checks become possible: one silent heads-up alert via the 'opened' path."""
import base64
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from curl_cffi import requests

from ..models import CLOSED, ERROR, OPEN, Result

MISSIONS = "aut bel bgr che cze dnk est fin fra hrv ltu lux lva mlt nld nor pol svn swe".split()
FLAGS = ("enablepreloginearliestavailabledate", "isCenterWithSlotsEnabled")
PUBKEY = serialization.load_pem_public_key((Path(__file__).parent / "vfs_clientsource.pem").read_bytes())


def clientsource() -> str:
    ct = PUBKEY.encrypt(str(int(time.time() * 1000)).encode(),
                        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return base64.b64encode(ct).decode()


class VfsFlags:
    NAME = "vfs-flags"
    INTERVAL = 3600

    def targets(self):
        return [("vfs/prelogin-flag", "VFS")]

    def check(self) -> list[Result]:
        s = requests.Session(impersonate="chrome")
        on, failed = [], 0
        for m in MISSIONS:
            try:
                r = s.get(f"https://lift-api.vfsglobal.com/configuration/fields/{m}/tur", timeout=20, headers={
                    "origin": "https://visa.vfsglobal.com", "referer": "https://visa.vfsglobal.com/",
                    "route": f"tur/en/{m}", "clientsource": clientsource()})
                if r.ok and r.json().get(FLAGS[0]):
                    on.append(m)
                elif not r.ok:
                    failed += 1
            except Exception:
                failed += 1
            time.sleep(1)
        if failed == len(MISSIONS):
            return [Result(key="vfs/prelogin-flag", country="VFS", provider="VFS Global", status=ERROR, detail="config endpoint unreachable")]
        return [Result(key="vfs/prelogin-flag", country="VFS", provider="VFS Global", status=OPEN if on else CLOSED,
                       detail=("pre-login earliest date ON for: " + ", ".join(on)) if on else "pre-login date switch off for all Turkey missions")]
