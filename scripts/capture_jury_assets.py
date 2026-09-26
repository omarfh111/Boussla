"""Regenerate the 8 static jury screenshots in docs/screenshots/.

ASSET GENERATION, NOT A TEST. UI correctness is established by tests/ui
(Streamlit AppTest on the real service). Here the company's evidence upload and
response are made through build_service() because headless file upload is out
of scope; every other step is a real click in the running app.

Isolation: a fresh temporary runtime (SQLite, checkpoints, uploads, traces), its
own Streamlit server and a temporary browser profile. Provider keys are blanked
and Jev/LangSmith/LLM are disabled, so no external calls are made and the
developer's runtime/ and .env are never touched. Data is the synthetic
CASE-BRICKS-001 fixture only.

Each capture waits until its expected text is visible (not a fixed sleep), and
the run fails if any two screenshots are byte-identical.

Usage (repository root, Windows Edge by default):
    python scripts/capture_jury_assets.py [--browser PATH] [--port 8599] [--cdp-port 9333]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "screenshots"
CASE_ID = "CASE-BRICKS-001"
DEFAULT_BROWSER = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
WIDTH, HEIGHT = 1440, 1050
SHOTS = (
    "01_company_operations_context.png",
    "02_officer_review_queue_index40.png",
    "03_officer_dossier_discrepancy.png",
    "04_clarification_request.png",
    "05_company_response_evidence.png",
    "06_before_after_revision_40_to_0.png",
    "07_history_case_versions.png",
    "08_diagnostics_real_status.png",
)


def isolated_env(runtime: Path) -> dict[str, str]:
    """Clean demo runtime with every external provider disabled."""
    env = {k: v for k, v in os.environ.items() if k != "BOUSSLA_SERVICE"}
    env.update({
        "CASE_DB_PATH": str(runtime / "cases.sqlite"), "CHECKPOINT_DB_PATH": str(runtime / "checkpoints.sqlite"),
        "UPLOAD_DIR": str(runtime / "uploads"), "EVENT_LOG_PATH": str(runtime / "events.jsonl"),
        "OPENAI_API_KEY": "", "TYPESAFE_API_KEY": "", "LANGSMITH_API_KEY": "",
        "LLM_PROVIDER": "manual", "JEV_ENABLED": "false", "LANGSMITH_TRACING": "false",
    })
    return env


class Page:
    """Minimal Chrome DevTools Protocol client for one tab."""

    def __init__(self, ws) -> None:
        self.ws, self.next_id = ws, 0

    async def call(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        await self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.next_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def js(self, expression: str):
        result = await self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return result.get("result", {}).get("value")

    async def wait_text(self, text: str, timeout: float = 30.0, present: bool = True) -> None:
        """Wait until `text` is (or is no longer) in the *visible* page text."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if bool(await self.js(f"document.body.innerText.includes({json.dumps(text)})")) is present:
                await self.wait_idle(deadline)
                return
            await asyncio.sleep(0.25)
        raise TimeoutError(f"text {'not found' if present else 'still visible'}: {text!r}")

    async def wait_idle(self, deadline: float) -> None:
        """Wait until Streamlit's run-status widget is gone, then let canvas grids paint."""
        while time.monotonic() < deadline:
            if not await self.js("!!document.querySelector('[data-testid=\"stStatusWidget\"]')"):
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(1.5)

    async def goto(self, url: str, expect: str) -> None:
        await self.call("Page.navigate", {"url": url})
        await self.wait_text(expect)

    async def click_tab(self, label: str, expect: str) -> None:
        ok = await self.js(f"""(() => {{
            const tab = [...document.querySelectorAll('[role="tab"]')]
                .find(t => t.innerText.trim().startsWith({json.dumps(label)}));
            if (!tab) return false; tab.click(); return true; }})()""")
        if not ok:
            raise RuntimeError(f"tab not found: {label}")
        await self.wait_text(expect)

    async def click_button(self, label: str, expect: str, present: bool = True) -> None:
        ok = await self.js(f"""(() => {{
            const b = [...document.querySelectorAll('button')]
                .find(x => x.innerText.includes({json.dumps(label)}) && x.offsetParent !== null);
            if (!b) return false; b.click(); return true; }})()""")
        if not ok:
            raise RuntimeError(f"visible button not found: {label}")
        await self.wait_text(expect, present=present)

    async def scroll_to(self, text: str) -> None:
        """Scroll the smallest *visible* element containing `text` to the top."""
        ok = await self.js(f"""(() => {{
            const hits = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,span,label,div')]
                .filter(e => e.offsetParent !== null && (e.innerText || '').includes({json.dumps(text)}));
            if (!hits.length) return false;
            hits.sort((a, b) => a.innerText.length - b.innerText.length);
            hits[0].scrollIntoView({{block: 'start'}}); return true; }})()""")
        if not ok:
            raise RuntimeError(f"section not found: {text}")
        await asyncio.sleep(0.6)

    async def scroll_top(self) -> None:
        await self.js("document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0; }); window.scrollTo(0, 0);")
        await asyncio.sleep(0.4)

    async def shot(self, name: str, from_text: str | None = None) -> None:
        """Viewport screenshot, or (from_text) a clip starting at that visible section,
        used when a section sits at the page bottom and cannot be scrolled to the top."""
        params: dict = {"format": "png"}
        if from_text:
            top = await self.js(f"""(() => {{
                const hits = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,span,label,div')]
                    .filter(e => e.offsetParent !== null && (e.innerText || '').includes({json.dumps(from_text)}));
                hits.sort((a, b) => a.innerText.length - b.innerText.length);
                return hits.length ? Math.max(0, hits[0].getBoundingClientRect().top - 16) : null; }})()""")
            if top is None:
                raise RuntimeError(f"section not found: {from_text}")
            params["clip"] = {"x": 0, "y": top, "width": WIDTH, "height": HEIGHT - top, "scale": 1}
        data = (await self.call("Page.captureScreenshot", params))["data"]
        import base64
        (OUTPUT_DIR / name).write_bytes(base64.b64decode(data))
        print(f"  captured {name}")


def respond_with_evidence_via_service() -> None:
    """Company evidence upload + reallocation response (service call, not a UI click)."""
    from boussla.config import FIXTURE_ROOT
    from boussla.services import build_service

    svc = build_service()
    company, officer = svc.registry.actors["DEMO-COMPANY-BAT"], svc.registry.actors["DEMO-OFFICER"]
    case = svc.get_case(officer, CASE_ID)
    request = case.requests[-1]
    pdf = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()
    doc = svc.upload_document(company, CASE_ID, pdf, "affectation_P2.pdf", "application/pdf",
                              case.case_version, "capture-upload")
    allocation = case.allocations[0]
    svc.submit_response(company, CASE_ID, request.request.request_id, {
        "answers": {q.question_id: "1 000 unités pour P1 et 1 000 unités pour P2, pièce d'affectation jointe."
                    for q in request.questions},
        "document_ids": [doc.document.document_id],
        "allocation": {"transaction_id": allocation.transaction_id, "line_id": allocation.line_id,
                       "splits": {"P1": "1000", "P2": "1000"}},
    }, doc.case_version, "capture-response")


async def journey(cdp_port: int, app: str) -> None:
    import httpx
    import websockets

    async with httpx.AsyncClient() as client:
        tab = (await client.put(f"http://127.0.0.1:{cdp_port}/json/new?about:blank")).json()
    async with websockets.connect(tab["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
        page = Page(ws)
        await page.call("Page.enable")
        await page.call("Emulation.setDeviceMetricsOverride",
                        {"width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1, "mobile": False})

        await page.goto(f"{app}/?role=Entreprise", "Facturé et réglé observé")
        await page.shot(SHOTS[0])

        await page.goto(f"{app}/?role=Agent", "pas probabilité de fraude")  # queue grid is a canvas
        await page.shot(SHOTS[1])

        await page.click_tab("Dossier", "Références de quantité")
        await page.scroll_to("Références de quantité")
        await page.shot(SHOTS[2])

        await page.click_button("Préparer une demande neutre", "Publier dans la boîte de démo")
        await page.scroll_to("Demande de précision")
        await page.shot(SHOTS[3])
        await page.click_button("Publier dans la boîte de démo", "Publier dans la boîte de démo", present=False)

        respond_with_evidence_via_service()

        await page.goto(f"{app}/?role=Entreprise", "Facturé et réglé observé")
        await page.click_tab("Contexte et réponses", "Réponses enregistrées")
        await page.scroll_to("Boîte de demandes")
        await page.shot(SHOTS[4])

        await page.goto(f"{app}/?role=Agent", "pas probabilité de fraude")
        await page.click_tab("Dossier", "Accepter dans ce dossier")
        await page.click_button("Accepter dans ce dossier", "Avant / après la décision")
        await page.scroll_to("Avant / après la décision")
        await page.shot(SHOTS[5])

        await page.scroll_to("Historique du dossier")
        await page.shot(SHOTS[6], from_text="Historique du dossier")

        await page.scroll_top()
        await page.click_tab("Diagnostics", "Comprendre les statuts")
        await page.shot(SHOTS[7])

    async with httpx.AsyncClient() as client:
        await client.get(f"http://127.0.0.1:{cdp_port}/json/close/{tab['id']}")


def port_free(port: int) -> bool:
    import socket
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def stop_tree(proc: subprocess.Popen) -> None:
    """Stop a process and its children (headless browsers spawn several)."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def stop_by_marker(marker: str) -> None:
    """Stop leftover processes whose command line contains our unique temp path
    (headless browsers re-parent their children, so the launcher tree is not enough)."""
    if os.name == "nt":
        script = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*" + marker.replace("'", "") +
                  "*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", marker], capture_output=True)


def wait_http(url: str, timeout: float = 60.0) -> None:
    import httpx
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise TimeoutError(url)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--browser", default=os.environ.get("BOUSSLA_CAPTURE_BROWSER", DEFAULT_BROWSER))
    parser.add_argument("--port", type=int, default=8599)
    parser.add_argument("--cdp-port", type=int, default=9333)
    args = parser.parse_args()

    busy = [p for p in (args.port, args.cdp_port) if not port_free(p)]
    if busy:
        print(f"ERROR: port(s) {busy} already in use; stop the other process or pass --port/--cdp-port",
              file=sys.stderr)
        return 2
    runtime = Path(tempfile.mkdtemp(prefix="boussla-capture-"))
    env = isolated_env(runtime)
    os.environ.clear()
    os.environ.update(env)  # the in-process service call uses the same isolated runtime
    sys.path.insert(0, str(ROOT))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = f"http://127.0.0.1:{args.port}"
    procs = []
    try:
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
             "--server.port", str(args.port), "--browser.gatherUsageStats", "false"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait_http(f"{app}/_stcore/health")
        procs.append(subprocess.Popen(
            [args.browser, "--headless=new", f"--remote-debugging-port={args.cdp_port}", "--disable-gpu",
             f"--user-data-dir={runtime / 'browser-profile'}", "--no-first-run", f"--window-size={WIDTH},{HEIGHT}",
             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait_http(f"http://127.0.0.1:{args.cdp_port}/json/version")
        print(f"Capturing from a clean runtime at {runtime}")
        asyncio.run(journey(args.cdp_port, app))
    finally:
        for proc in reversed(procs):
            stop_tree(proc)
        stop_by_marker(str(runtime / "browser-profile"))
        time.sleep(1)
        shutil.rmtree(runtime, ignore_errors=True)

    digests = {name: hashlib.sha256((OUTPUT_DIR / name).read_bytes()).hexdigest() for name in SHOTS}
    for name, digest in digests.items():
        print(f"  {digest[:16]}  {name}")
    if len(set(digests.values())) != len(SHOTS):
        print("ERROR: duplicate screenshots (identical bytes)", file=sys.stderr)
        return 1
    print(f"OK: {len(SHOTS)} distinct screenshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
