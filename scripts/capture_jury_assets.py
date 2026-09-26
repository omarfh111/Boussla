"""Automated capture of all 8 jury screenshots and animated demo video via Edge CDP."""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from PIL import Image
import websockets

from boussla.config import FIXTURE_ROOT
from boussla.contracts import Audience
from boussla.services import build_service

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUTPUT_DIR = Path("docs/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CASE_ID = "CASE-BRICKS-001"


async def capture_tab(ws, output_path: Path, js_before: list[str] = None, wait_before: float = 2.0):
    if js_before:
        for js in js_before:
            await ws.send(json.dumps({
                "id": 99,
                "method": "Runtime.evaluate",
                "params": {"expression": js}
            }))
            await asyncio.sleep(wait_before)

    await ws.send(json.dumps({
        "id": 100,
        "method": "Page.captureScreenshot",
        "params": {"format": "png"}
    }))

    while True:
        raw = await ws.recv()
        data = json.loads(raw)
        if data.get("id") == 100:
            img = base64.b64decode(data["result"]["data"])
            output_path.write_bytes(img)
            print(f"Captured {output_path.name} ({len(img):,} bytes)")
            break


async def run_journey_and_capture():
    async with httpx.AsyncClient() as client:
        r = await client.put("http://127.0.0.1:9222/json/new?http://localhost:8501/?role=Entreprise")
        tab = r.json()
        target_id = tab["id"]
        ws_url = tab["webSocketDebuggerUrl"]

    try:
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            await asyncio.sleep(4)

            # 1. Company Operations & Context
            print("Capturing 01_company_operations_context.png...")
            await capture_tab(ws, OUTPUT_DIR / "01_company_operations_context.png")

            # 2. Officer Review Queue (index 40)
            print("Capturing 02_officer_review_queue_index40.png...")
            await ws.send(json.dumps({
                "id": 2,
                "method": "Page.navigate",
                "params": {"url": "http://localhost:8501/?role=Agent"}
            }))
            await asyncio.sleep(4)
            await capture_tab(ws, OUTPUT_DIR / "02_officer_review_queue_index40.png")

            # 3. Officer Dossier showing discrepancy 2000 vs 1000
            print("Capturing 03_officer_dossier_discrepancy.png...")
            await capture_tab(
                ws,
                OUTPUT_DIR / "03_officer_dossier_discrepancy.png",
                js_before=["document.querySelectorAll('button[data-baseweb=\"tab\"]')[1].click();"],
                wait_before=2.5
            )

            # 4. Clarification Request Preparation
            print("Capturing 04_clarification_request.png...")
            await capture_tab(
                ws,
                OUTPUT_DIR / "04_clarification_request.png",
                js_before=[
                    "Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Préparer une demande')).click();",
                    "window.scrollBy(0, 400);"
                ],
                wait_before=2.0
            )

            # Publish clarification in demo box
            await ws.send(json.dumps({
                "id": 5,
                "method": "Runtime.evaluate",
                "params": {"expression": "Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Publier dans la boîte')).click();"}
            }))
            await asyncio.sleep(2.0)

            # 5. Company response and evidence
            print("Capturing 05_company_response_evidence.png...")
            await ws.send(json.dumps({
                "id": 6,
                "method": "Page.navigate",
                "params": {"url": "http://localhost:8501/?role=Entreprise"}
            }))
            await asyncio.sleep(4)
            await capture_tab(
                ws,
                OUTPUT_DIR / "05_company_response_evidence.png",
                js_before=[
                    "document.querySelectorAll('button[data-baseweb=\"tab\"]')[1].click();",
                    "window.scrollBy(0, 300);"
                ],
                wait_before=2.0
            )

            # Respond with allocation from Company via service
            svc = build_service()
            actor_co = svc.registry.actors["DEMO-COMPANY-BAT"]
            actor_off = svc.registry.actors["DEMO-OFFICER"]
            c = svc.get_case(actor_off, CASE_ID)
            v = c.case_version
            req_id = c.requests[-1].request.request_id

            alloc_pdf = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()
            doc_view = svc.upload_document(actor_co, CASE_ID, alloc_pdf, "affectation_P2.pdf", "application/pdf", v, "up-p2")
            v_after_doc = doc_view.case_version

            curr_alloc = c.allocations[0]
            resp_payload = {
                "answers": {q.question_id: "Affectation validée sur le second chantier." for q in c.requests[-1].questions},
                "document_ids": [doc_view.document.document_id],
                "allocation": {
                    "transaction_id": curr_alloc.transaction_id,
                    "line_id": curr_alloc.line_id,
                    "splits": {"P1": "1000", "P2": "1000"}
                }
            }
            svc.submit_response(actor_co, CASE_ID, req_id, resp_payload, v_after_doc, "resp-p2")

            # 6. Before / after revision showing 40 -> 0
            print("Capturing 06_before_after_revision_40_to_0.png...")
            await ws.send(json.dumps({
                "id": 7,
                "method": "Page.navigate",
                "params": {"url": "http://localhost:8501/?role=Agent"}
            }))
            await asyncio.sleep(4)
            # Click tab Dossier, then click "Accepter dans ce dossier"
            await capture_tab(
                ws,
                OUTPUT_DIR / "06_before_after_revision_40_to_0.png",
                js_before=[
                    "document.querySelectorAll('button[data-baseweb=\"tab\"]')[1].click();",
                    "setTimeout(() => { const b = Array.from(document.querySelectorAll('button')).find(x => x.innerText.includes('Accepter dans ce dossier')); if (b) b.click(); }, 1000);",
                    "window.scrollBy(0, 600);"
                ],
                wait_before=3.5
            )

            # 7. History showing case versions
            print("Capturing 07_history_case_versions.png...")
            await capture_tab(
                ws,
                OUTPUT_DIR / "07_history_case_versions.png",
                js_before=["window.scrollTo(0, document.body.scrollHeight);"],
                wait_before=1.5
            )

            # 8. Diagnostics real integration statuses
            print("Capturing 08_diagnostics_real_status.png...")
            await capture_tab(
                ws,
                OUTPUT_DIR / "08_diagnostics_real_status.png",
                js_before=[
                    "window.scrollTo(0, 0);",
                    "document.querySelectorAll('button[data-baseweb=\"tab\"]')[2].click();"
                ],
                wait_before=2.0
            )

    finally:
        async with httpx.AsyncClient() as client:
            await client.get(f"http://127.0.0.1:9222/json/close/{target_id}")


def main():
    print("=== Starting Edge Headless with CDP ===")
    edge_proc = subprocess.Popen([
        EDGE_PATH,
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "--window-size=1440,1050",
        "about:blank"
    ])
    time.sleep(2)

    try:
        asyncio.run(run_journey_and_capture())

        print("=== Compiling animated demonstration video walkthrough (WebP) ===")
        png_names = [
            "01_company_operations_context.png",
            "02_officer_review_queue_index40.png",
            "03_officer_dossier_discrepancy.png",
            "04_clarification_request.png",
            "05_company_response_evidence.png",
            "06_before_after_revision_40_to_0.png",
            "07_history_case_versions.png",
            "08_diagnostics_real_status.png",
        ]
        images = []
        for name in png_names:
            p = OUTPUT_DIR / name
            if p.exists():
                images.append(Image.open(p).convert("RGB"))

        if images:
            resized = [img.resize((1200, int(1200 * img.height / img.width)), Image.Resampling.LANCZOS) for img in images]
            anim_path = OUTPUT_DIR / "boussla_demo_walkthrough.webp"
            resized[0].save(
                anim_path,
                format="WEBP",
                save_all=True,
                append_images=resized[1:],
                duration=3500,
                loop=0,
                quality=90
            )
            print(f"Saved animated walkthrough: {anim_path} ({anim_path.stat().st_size:,} bytes)")

        print("=== ALL JURY ASSETS PRODUCED SUCCESSFULLY! ===")

    finally:
        edge_proc.terminate()


if __name__ == "__main__":
    main()
