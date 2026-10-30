"""Probe: real Chrome (Xvfb) on a GitHub runner: click Turnstile, then submit a dummy login and record the API reply."""
import asyncio, sys
from patchright.async_api import async_playwright

MISSION = sys.argv[1] if len(sys.argv) > 1 else "nld"

async def token(page):
    try:
        return await page.evaluate("() => (document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
    except Exception:
        return ""

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/tmp/prof", channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        def on_resp(r):
            if "lift-api" in r.url:
                async def show():
                    try: body = (await r.text())[:300]
                    except Exception: body = "?"
                    print("API", r.status, r.request.method, r.url, body, flush=True)
                asyncio.ensure_future(show())
        page.on("response", on_resp)
        def on_req(r):
            if "lift-api" in r.url and r.method == "POST":
                print("REQ", r.url, {k: v[:60] for k, v in r.headers.items() if k in ("route", "clientsource", "authorize", "cfmlift")}, (r.post_data or "")[:200], flush=True)
        page.on("request", on_req)
        await page.goto(f"https://visa.vfsglobal.com/tur/en/{MISSION}/login", wait_until="domcontentloaded", timeout=90000)
        await asyncio.sleep(8)
        try:
            await page.get_by_role("button", name="Accept Only Necessary").click(timeout=5000)
        except Exception as e:
            print("no cookie button", e)
        await page.fill("#email", "probe.visaslots@example.com")
        await page.fill("#password", "NotARealPassw0rd!")
        t = ""
        for attempt in range(6):
            t = await token(page)
            if t: break
            box = None
            for f in page.frames:
                if "challenges.cloudflare.com" in f.url:
                    el = await f.frame_element()
                    box = await el.bounding_box()
            print("attempt", attempt, "iframe box", box, flush=True)
            if box:
                await page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
            await asyncio.sleep(6)
        t = await token(page)
        print("token len:", len(t), flush=True)
        await page.screenshot(path="shot1.png")
        if t:
            await page.get_by_role("button", name="Sign In").click()
            await asyncio.sleep(10)
        await page.screenshot(path="shot.png")
        await ctx.close()

asyncio.run(main())
