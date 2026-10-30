"""One run: log in (SMS code relayed via the otp branch), look for an authenticator option,
then list every Istanbul centre + category for every VFS mission and try one slot check each."""
import asyncio, json, os, sys, time
sys.path.insert(0, ".")
from patchright.async_api import async_playwright
from visa_slots.providers.vfs_session import VfsSession, jwt_exp
from probe.vfs_register import wait_otp

MISSIONS = os.environ.get("MISSIONS", "nld,fra,aut,bel,bgr,cze,dnk,est,fin,hrv,ltu,lux,lva,mlt,nor,pol,svn,swe,che").split(",")


async def main():
    out = {}
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/tmp/profd", channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0]
        s = VfsSession(page, os.environ["VFS_EMAIL"], os.environ["VFS_PASSWORD"], lambda since: wait_otp(since, 10))
        try:
            print("OTP_WAITING login", flush=True)
            await s.login(MISSIONS[0])
        finally:
            await page.screenshot(path="shot_d_login.png", full_page=True)
        print("LOGIN_OK token exp in min:", round((jwt_exp(s.token) - time.time()) / 60), "seen clientsource:", bool(s.seen_clientsource), flush=True)
        print("LOGIN_BODY", json.dumps({k: v for k, v in s.login_body.items() if k not in ("accessToken", "contactNumber", "loginUser")})[:1500], flush=True)
        await asyncio.sleep(5)
        print("DASH", page.url, (await page.evaluate("() => document.body.innerText"))[:1500], flush=True)
        links = await page.evaluate("() => [...document.querySelectorAll('a,button')].map(a => (a.innerText||'').trim() + ' -> ' + (a.href||'')).filter(x => x.length > 4).slice(0, 80)")
        print("LINKS", links, flush=True)
        await page.screenshot(path="shot_d_dash.png", full_page=True)
        # profile / security settings: look for an authenticator option
        for path in ("my-profile", "profile", "account-settings", "manage-account", "change-password"):
            await page.goto(f"https://visa.vfsglobal.com/tur/en/{MISSIONS[0]}/{path}", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            t = await page.evaluate("() => document.body.innerText")
            print("PAGE", path, page.url, t[:600].replace("\n", " | "), "AUTHENTICATOR" if "uthenticat" in t else "", flush=True)
        await page.goto(f"https://visa.vfsglobal.com/tur/en/{MISSIONS[0]}/dashboard", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        for m in MISSIONS:
            centers = [c for c in await s.centers(m) if "stanbul" in (c.get("city") or "") + (c.get("centerName") or "") or "Altunizade" in (c.get("city") or "") or "Beyoglu" in (c.get("city") or "") or "Harbiye" in (c.get("city") or "")]
            out[m] = []
            for c in centers:
                vac = c["isoCode"]
                st, cats = await s.api("GET", f"/master/visacategory/{m}/tur/{vac}/en-US", m)
                print("CATS", m, vac, st, json.dumps(cats, ensure_ascii=False)[:700], flush=True)
                entry = {"vac": vac, "center": c["centerName"], "categories": []}
                for cat in (cats if isinstance(cats, list) else []):
                    code = cat.get("code")
                    sst, subs = await s.api("GET", f"/master/subvisacategory/{m}/tur/{vac}/{code}/en-US", m)
                    print("SUBS", m, vac, code, sst, json.dumps(subs, ensure_ascii=False)[:500], flush=True)
                    entry["categories"].append({"code": code, "name": cat.get("name"), "subs": subs if isinstance(subs, list) else []})
                    await asyncio.sleep(1)
                out[m].append(entry)
                # one slot check per centre: first sub-category of the first short-stay-looking category
                pick = None
                for cat in entry["categories"]:
                    for sub in cat["subs"]:
                        if any(w in (sub.get("name", "") + cat.get("name", "")).lower() for w in ("touris", "short", "visit", "turizm")):
                            pick = sub.get("code"); break
                    if pick: break
                if pick:
                    st, res = await s.slot(m, vac, pick)
                    print("SLOT", m, vac, pick, st, json.dumps(res, ensure_ascii=False)[:400], flush=True)
                    entry["slot_probe"] = {"code": pick, "status": st, "res": res}
                await asyncio.sleep(2)
        json.dump(out, open("vfs_discovery.json", "w"), indent=1, ensure_ascii=False)
        await ctx.close()

asyncio.run(main())
