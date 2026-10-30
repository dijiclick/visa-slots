"""Probe: can a real Chrome (Xvfb, not headless) on a GitHub runner load the VFS login page and get a Turnstile token?"""
import asyncio, json, re, sys
from patchright.async_api import async_playwright

MISSION = sys.argv[1] if len(sys.argv) > 1 else "nld"

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/tmp/prof", channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        js_urls = []
        page.on("response", lambda r: js_urls.append(r.url) if r.url.endswith(".js") else None)
        await page.goto(f"https://visa.vfsglobal.com/tur/en/{MISSION}/login", wait_until="domcontentloaded", timeout=90000)
        token = ""
        for i in range(60):
            await asyncio.sleep(2)
            title = await page.title()
            try:
                token = await page.evaluate("() => (document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
            except Exception:
                token = ""
            print(i, repr(title), "token" if token else "-", flush=True)
            if token:
                break
        await page.screenshot(path="shot.png", full_page=True)
        html = await page.content()
        print("has email field:", "formcontrolname=\"username\"" in html or 'type="email"' in html)
        print("token len:", len(token))
        keys = set()
        for u in set(js_urls):
            if "vfsglobal" not in u: continue
            try:
                body = await page.evaluate("u => fetch(u).then(r=>r.text())", u)
            except Exception:
                continue
            for m in re.findall(r"-----BEGIN PUBLIC KEY-----[A-Za-z0-9+/=\\n\s]+-----END PUBLIC KEY-----", body):
                keys.add(m)
            for m in re.findall(r"MII[A-Za-z0-9+/=]{200,}", body):
                keys.add(m)
        print("public keys:", json.dumps(list(keys))[:3000])
        await ctx.close()

asyncio.run(main())
