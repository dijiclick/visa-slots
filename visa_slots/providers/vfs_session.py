"""A logged-in VFS Global session driven through a real Chrome (Xvfb on GitHub Actions).

Login goes through the website (Turnstile + SMS/TOTP code); after that the lift-api calls are made
with fetch() from inside the page, so they carry the browser's cookies and fingerprint.
"""
import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

log = logging.getLogger(__name__)
LIFT = "https://lift-api.vfsglobal.com"
SITE = "https://visa.vfsglobal.com"
PUBKEY = serialization.load_pem_public_key((Path(__file__).parent / "vfs_clientsource.pem").read_bytes())


def clientsource() -> str:
    ct = PUBKEY.encrypt(str(int(time.time() * 1000)).encode(),
                        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return base64.b64encode(ct).decode()


def jwt_exp(token: str) -> float:
    try:
        payload = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("exp", 0)
    except Exception:
        return 0


class LoginNeedsCode(Exception):
    pass


class VfsSession:
    def __init__(self, page, email: str, password: str, get_code):
        """get_code(since_ts) -> awaitable str: returns the SMS/TOTP code (or "" on timeout)."""
        self.page, self.email, self.password, self.get_code = page, email, password, get_code
        self.token = ""
        self.mission = ""
        self.login_body: dict = {}
        self.seen_clientsource = ""
        page.on("request", self._on_request)
        page.on("response", self._on_response)

    def _on_request(self, r):
        cs = r.headers.get("clientsource")
        if cs and "lift-api" in r.url:
            self.seen_clientsource = cs

    def _on_response(self, r):
        if r.url.startswith(LIFT + "/user/login") and r.request.method == "POST":
            async def grab():
                try:
                    body = json.loads(await r.text())
                except Exception:
                    return
                self.login_body = body
                if body.get("accessToken"):
                    self.token = body["accessToken"]
            asyncio.ensure_future(grab())

    async def _turnstile(self) -> str:
        page = self.page
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

    def valid(self) -> bool:
        exp = jwt_exp(self.token)
        return bool(self.token) and (not exp or exp - time.time() > 300)

    async def login(self, mission: str) -> None:
        page = self.page
        self.token, self.login_body = "", {}
        await page.goto(f"{SITE}/tur/en/{mission}/login", wait_until="domcontentloaded", timeout=90000)
        await asyncio.sleep(6)
        try:
            await page.get_by_role("button", name="Accept Only Necessary").click(timeout=4000)
        except Exception:
            pass
        await page.fill("#email", self.email)
        await page.fill("#password", self.password)
        if not await self._turnstile():
            raise RuntimeError("turnstile not solved")
        t0 = time.time()
        await page.get_by_role("button", name="Sign In").click()
        for _ in range(30):
            await asyncio.sleep(1)
            if self.token or self.login_body:
                break
        if not self.token and self.login_body.get("enableOTPAuthentication"):
            code = await self.get_code(t0)
            if not code:
                raise LoginNeedsCode("no login code arrived")
            await page.locator("input[formcontrolname=otp]:visible, input[type=password]:visible").first.fill(code)
            await self._turnstile()
            self.login_body = {}
            await page.locator("button:visible", has_text="Sign In").first.click()
            for _ in range(30):
                await asyncio.sleep(1)
                if self.token or self.login_body:
                    break
        if not self.token:
            err = self.login_body.get("error") or self.login_body
            raise RuntimeError(f"login failed: {json.dumps(err)[:300]}")
        self.mission = mission
        log.info("vfs logged in (%s), token valid until %s", mission, time.strftime("%H:%M", time.gmtime(jwt_exp(self.token))))

    async def api(self, method: str, path: str, mission: str, body: dict | None = None, auth: bool = True):
        headers = {"route": f"tur/en/{mission}", "clientsource": clientsource(), "accept": "application/json, text/plain, */*"}
        if auth:
            headers["authorize"] = self.token
        if body is not None:
            headers["content-type"] = "application/json;charset=UTF-8"
        res = await self.page.evaluate(
            """async ([url, method, headers, body]) => {
                const r = await fetch(url, {method, headers, body: body ? JSON.stringify(body) : undefined, credentials: 'include'});
                return [r.status, await r.text()];
            }""",
            [LIFT + path, method, headers, body],
        )
        status, text = res
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, text

    async def centers(self, mission: str) -> list[dict]:
        st, data = await self.api("GET", f"/master/center/{mission}/tur/en-US", mission, auth=False)
        return data if isinstance(data, list) else []

    async def categories(self, mission: str, vac: str) -> list[dict]:
        st, data = await self.api("GET", f"/master/visacategory/{mission}/tur/{vac}/en-US", mission)
        return data if isinstance(data, list) else []

    async def subcategories(self, mission: str, vac: str, cat: str) -> list[dict]:
        st, data = await self.api("GET", f"/master/subvisacategory/{mission}/tur/{vac}/{cat}/en-US", mission)
        return data if isinstance(data, list) else []

    async def slot(self, mission: str, vac: str, category: str):
        return await self.api("POST", "/appointment/CheckIsSlotAvailable", mission, {
            "countryCode": "tur", "missionCode": mission, "vacCode": vac, "visaCategoryCode": category,
            "roleName": "Individual", "loginUser": self.email, "payCode": "",
        })
