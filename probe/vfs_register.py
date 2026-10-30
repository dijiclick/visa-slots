"""Register the checker's VFS account, then log in once and record the booking API calls.

The SMS code is relayed through the `otp` branch (otp.txt, AES-encrypted with VFS_PASSWORD).
"""
import asyncio, base64, json, os, subprocess, time
from patchright.async_api import async_playwright

MISSION = os.environ.get("MISSION", "nld")
REPO = os.environ.get("GITHUB_REPOSITORY", "dijiclick/visa-slots")
SKIP_REGISTER = os.environ.get("SKIP_REGISTER") == "1"


def read_otp(since: float) -> str:
    try:
        meta = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/contents/otp.txt?ref=otp"], capture_output=True, check=True).stdout)
        enc = base64.b64decode(meta["content"]).decode().strip()
        plain = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-a", "-A", "-pass", "env:VFS_PASSWORD"],
                               input=enc.encode(), capture_output=True, check=True).stdout.decode().strip()
        ts, code = plain.split(":")
        return code if float(ts) >= since else ""
    except Exception:
        return ""


async def wait_otp(since: float, minutes: float = 12) -> str:
    end = time.time() + minutes * 60
    while time.time() < end:
        code = read_otp(since)
        if code:
            return code
        await asyncio.sleep(3)
    return ""


async def turnstile(page):
    for _ in range(10):
        tok = await page.evaluate("() => [...document.querySelectorAll('[name=cf-turnstile-response]')].map(e => e.value).join('')")
        if tok:
            return tok
        for f in page.frames:
            if "challenges.cloudflare.com" in f.url:
                el = await f.frame_element()
                if await el.is_visible():
                    box = await el.bounding_box()
                    if box:
                        await page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
        await asyncio.sleep(4)
    return ""


async def text(page):
    return (await page.evaluate("() => document.body.innerText"))[:1200]


async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context("/tmp/profr", channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0]
        log = []
        def on_resp(r):
            if "lift-api" in r.url:
                async def show():
                    try: body = (await r.text())[:1500]
                    except Exception: body = "?"
                    hdrs = {k: v[:40] for k, v in r.request.headers.items() if k in ("route", "clientsource", "authorize")}
                    print("API", r.status, r.request.method, r.url, hdrs, (r.request.post_data or "")[:300].replace(os.environ["VFS_PASSWORD"], "***"), "=>", body, flush=True)
                    log.append({"url": r.url, "status": r.status, "req": (r.request.post_data or "")[:300], "body": body})
                asyncio.ensure_future(show())
        page.on("response", on_resp)

        if not SKIP_REGISTER:
            await page.goto(f"https://visa.vfsglobal.com/tur/en/{MISSION}/register", wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(8)
            try:
                await page.get_by_role("button", name="Accept Only Necessary").click(timeout=5000)
            except Exception:
                pass
            await page.fill("#inputEmail", os.environ["VFS_EMAIL"])
            await page.fill("#password", os.environ["VFS_PASSWORD"])
            await page.fill("#confirmPassword", os.environ["VFS_PASSWORD"])
            await page.click("mat-select[formcontrolname=dialcode]")
            await asyncio.sleep(1)
            await page.locator("mat-option", has_text="Turkey(90)").click()
            await page.fill("input[formcontrolname=contact]", os.environ["VFS_PHONE"])
            for fc in ("processPerDataAgreed", "intTransPerDataAgreed", "termAndConditionAgreed"):
                await page.click(f"mat-checkbox[formcontrolname={fc}] input")
            print("turnstile", len(await turnstile(page)), flush=True)
            sent_at = time.time()
            await page.click("#trigger")
            print("OTP_WAITING sms sent", flush=True)
            code = await wait_otp(sent_at)
            print("otp received:", bool(code), flush=True)
            if not code:
                await page.screenshot(path="shot_reg_nootp.png", full_page=True)
                return
            fields = await page.evaluate("() => [...document.querySelectorAll('input')].filter(e => e.offsetParent).map(e => e.id + '|' + e.getAttribute('formcontrolname') + '|' + e.type)")
            print("visible inputs", fields, flush=True)
            otp_input = page.locator("input[formcontrolname*=otp i]:visible, input[id*=otp i]:visible").first
            if not await otp_input.count():
                otp_input = page.locator("input[type=password]:visible").first
            await otp_input.fill(code)
            # the OTP form has its own Turnstile widget
            await asyncio.sleep(2)
            print("turnstile2", len(await turnstile(page)), flush=True)
            btn = page.locator("button:visible", has_text="Register").first
            for _ in range(10):
                if await btn.is_enabled():
                    break
                await asyncio.sleep(2)
            await page.screenshot(path="shot_reg_otp.png", full_page=True)
            await btn.click(timeout=10000)
            await asyncio.sleep(12)
            print("AFTER_REGISTER", page.url, await text(page), flush=True)
            await page.screenshot(path="shot_reg_done.png", full_page=True)

        # ---- log in once and see what the account can do
        await page.goto(f"https://visa.vfsglobal.com/tur/en/{MISSION}/login", wait_until="domcontentloaded", timeout=90000)
        await asyncio.sleep(8)
        try:
            await page.get_by_role("button", name="Accept Only Necessary").click(timeout=4000)
        except Exception:
            pass
        await page.fill("#email", os.environ["VFS_EMAIL"])
        await page.fill("#password", os.environ["VFS_PASSWORD"])
        print("turnstile-login", len(await turnstile(page)), flush=True)
        t0 = time.time()
        await page.get_by_role("button", name="Sign In").click()
        await asyncio.sleep(12)
        body = await text(page)
        print("AFTER_LOGIN", page.url, body, flush=True)
        await page.screenshot(path="shot_login.png", full_page=True)
        if "OTP" in body or "one time" in body.lower():
            print("OTP_WAITING login", flush=True)
            code = await wait_otp(t0)
            if code:
                await page.locator("input[formcontrolname*=otp i], input[id*=otp i], input[type=password]").first.fill(code)
                print("turnstile3", len(await turnstile(page)), flush=True)
                await page.get_by_role("button", name="Sign In").click()
                await asyncio.sleep(12)
                print("AFTER_LOGIN_OTP", page.url, await text(page), flush=True)
        await page.screenshot(path="shot_dash.png", full_page=True)
        # ---- start a booking to see categories and the slot check
        try:
            await page.get_by_role("button", name="Start New Booking").click(timeout=15000)
            await asyncio.sleep(8)
            print("BOOKING_PAGE", page.url, await text(page), flush=True)
            selects = page.locator("mat-select")
            n = await selects.count()
            print("selects", n, flush=True)
            for i in range(n):
                await selects.nth(i).click()
                await asyncio.sleep(2)
                opts = [await o.inner_text() for o in await page.locator("mat-option").all()]
                print("SELECT", i, opts, flush=True)
                await page.locator("mat-option").last.click()
                await asyncio.sleep(6)
            print("AFTER_SELECT", await text(page), flush=True)
            await page.screenshot(path="shot_booking.png", full_page=True)
        except Exception as e:
            print("booking flow error", e, flush=True)
            await page.screenshot(path="shot_booking_err.png", full_page=True)
        json.dump(log, open("api_log.json", "w"), indent=1)
        await ctx.close()

async def safe():
    try:
        await main()
    except Exception as e:
        print("FAILED", type(e).__name__, str(e)[:300], flush=True)
        raise

asyncio.run(safe())
