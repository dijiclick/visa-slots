"""Register the checker's VFS account (run once on Actions). DUMP=1 only prints the form."""
import asyncio, json, os, sys
from patchright.async_api import async_playwright

MISSION = os.environ.get("MISSION", "nld")
DUMP = os.environ.get("DUMP") == "1"

async def turnstile(page):
    for _ in range(8):
        tok = await page.evaluate("() => (document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
        if tok:
            return tok
        for f in page.frames:
            if "challenges.cloudflare.com" in f.url:
                box = await (await f.frame_element()).bounding_box()
                if box:
                    await page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
        await asyncio.sleep(5)
    return ""

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/tmp/profr", channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0]
        def on_resp(r):
            if "lift-api" in r.url and r.request.method == "POST":
                async def show():
                    try: body = (await r.text())[:600]
                    except Exception: body = "?"
                    print("API", r.status, r.url, body, flush=True)
                asyncio.ensure_future(show())
        page.on("response", on_resp)
        await page.goto(f"https://visa.vfsglobal.com/tur/en/{MISSION}/register", wait_until="domcontentloaded", timeout=90000)
        await asyncio.sleep(8)
        try:
            await page.get_by_role("button", name="Accept Only Necessary").click(timeout=5000)
        except Exception:
            pass
        fields = await page.evaluate("""() => [...document.querySelectorAll('input,select,mat-select,textarea,mat-checkbox,button')].map(e => ({
            tag: e.tagName, id: e.id, type: e.type, name: e.getAttribute('name'), fc: e.getAttribute('formcontrolname'),
            ph: e.getAttribute('placeholder'), text: (e.innerText||'').slice(0,80)}))""")
        print("FIELDS", json.dumps(fields, ensure_ascii=False), flush=True)
        print("TEXT", (await page.evaluate("() => document.body.innerText"))[:3000], flush=True)
        await page.screenshot(path="shot_reg.png", full_page=True)
        if DUMP:
            await ctx.close(); return
        await ctx.close()

asyncio.run(main())
