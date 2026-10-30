"""One-off reachability probe: what do visa sites return to a GitHub Actions runner?"""
import sys
from curl_cffi import requests

URLS = [
    "https://visa.vfsglobal.com/tur/en/nld/",
    "https://visa.vfsglobal.com/tur/en/fra/",
    "https://lift-api.vfsglobal.com/",
    "https://it-tr-appointment.idata.com.tr/tr",
    "https://de-tr-appointment.idata.com.tr/tr",
    "https://turkey.blsspainvisa.com/istanbul/english/",
    "https://service2.diplo.de/rktermin/extern/choose_realmList.do?locationCode=ista&request_locale=en",
]
for u in URLS:
    for imp in (None, "chrome"):
        try:
            r = requests.get(u, impersonate=imp, timeout=25) if imp else requests.get(u, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            title = r.text.split("<title>")[1].split("</title>")[0][:60] if "<title>" in r.text else r.text[:60]
            print(f"{imp or 'plain':6} {r.status_code} {len(r.text):7} {u}  | {title!r}")
        except Exception as e:
            print(f"{imp or 'plain':6} ERR {u} {e}")
sys.stdout.flush()
