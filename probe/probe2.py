"""Probe 2: Kosmos (Greece) public API via curl_cffi; AS Visa (Hungary/Portugal) via real Chrome."""
import asyncio
from curl_cffi import requests

K = "https://api.kosmosvize.com.tr/api/"
for path in ("Dealers/GetDealers", "AdminDatas/GetDatasById?id=2329", "AdminDatas/GetToday", "AdminDatas/getDatas?dataType=AppointmentType"):
    try:
        r = requests.get(K + path, impersonate="chrome", timeout=25, headers={"Origin": "https://basvuru.kosmosvize.com.tr", "Referer": "https://basvuru.kosmosvize.com.tr/"})
        print("KOSMOS", r.status_code, path, r.text[:300].replace("\n", " "), flush=True)
    except Exception as e:
        print("KOSMOS ERR", path, e, flush=True)

from patchright.async_api import async_playwright

async def asvisa():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/tmp/prof2", channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0]
        page.on("response", lambda r: print("ASV", r.status, r.request.method, r.url[:150], flush=True) if r.request.resource_type in ("document", "xhr", "fetch") else None)
        for url in ("https://www.as-visa.com/DynamicPage.aspx?ID=51", "https://appointment.as-visa.com/"):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print("ASV goto err", e)
            for i in range(10):
                await asyncio.sleep(3)
                t = await page.title()
                if "moment" not in t.lower() and "dakika" not in t.lower():
                    break
                for f in page.frames:
                    if "challenges.cloudflare.com" in f.url:
                        box = await (await f.frame_element()).bounding_box()
                        if box:
                            await page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
            print("ASV title:", url, repr(await page.title()), flush=True)
            await page.screenshot(path=f"shot_asv{1 if 'www' in url else 2}.png", full_page=True)
            links = await page.evaluate("() => [...document.querySelectorAll('a')].map(a => a.href).filter(h => /randevu|appointment|macar|portek|hungar|portug/i.test(h)).slice(0, 40)")
            print("ASV links:", links, flush=True)
            html = await page.content()
            open(f"asv{1 if 'www' in url else 2}.html", "w").write(html)
        await ctx.close()

asyncio.run(asvisa())
