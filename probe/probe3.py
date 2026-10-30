"""Probe 3: AS Visa appointment page structure; Kosmos via real Chrome."""
import asyncio, json
from patchright.async_api import async_playwright

async def pass_cf(page):
    for i in range(12):
        await asyncio.sleep(3)
        t = (await page.title()).lower()
        if "moment" not in t and "dakika" not in t and "attention" not in t:
            return True
        for f in page.frames:
            if "challenges.cloudflare.com" in f.url:
                box = await (await f.frame_element()).bounding_box()
                if box:
                    await page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
    return False

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/tmp/prof3", channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0]
        def on_resp(r):
            if r.request.resource_type in ("document", "xhr", "fetch") and "cdn-cgi" not in r.url and "google" not in r.url:
                async def show():
                    try: body = (await r.text())[:400].replace("\n", " ")
                    except Exception: body = "?"
                    print("RESP", r.status, r.request.method, r.url[:160], (r.request.post_data or "")[:200], "=>", body if r.request.resource_type != "document" else "", flush=True)
                asyncio.ensure_future(show())
        page.on("response", on_resp)

        await page.goto("https://www.as-visa.com/appointment", wait_until="domcontentloaded", timeout=60000)
        print("asv cf:", await pass_cf(page), await page.title(), page.url, flush=True)
        await asyncio.sleep(5)
        open("asv_appt.html", "w").write(await page.content())
        await page.screenshot(path="shot_appt.png", full_page=True)
        for path in ("macaristan", "portekiz"):
            await page.goto(f"https://www.as-visa.com/{path}", wait_until="domcontentloaded", timeout=60000)
            await pass_cf(page)
            await asyncio.sleep(3)
            open(f"asv_{path}.html", "w").write(await page.content())

        await page.goto("https://basvuru.kosmosvize.com.tr/appointmentform", wait_until="domcontentloaded", timeout=60000)
        print("kosmos cf:", await pass_cf(page), await page.title(), flush=True)
        await asyncio.sleep(8)
        await page.screenshot(path="shot_kosmos.png", full_page=True)
        for path in ("AdminDatas/GetDatasById?id=2329", "Dealers/GetDealers"):
            try:
                res = await page.evaluate("u => fetch(u).then(async r => r.status + ' ' + (await r.text()).slice(0, 300))", "https://api.kosmosvize.com.tr/api/" + path)
            except Exception as e:
                res = f"ERR {e}"
            print("KOSMOS-in-page", path, res, flush=True)
        await ctx.close()

asyncio.run(main())
