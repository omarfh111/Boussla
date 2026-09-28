"""Thin Starlette adapter. The service owns permissions, facts, and revisions."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Match, Route

from boussla.contracts import BousslaError, ErrorCode
from boussla.services import BousslaAppService, build_service

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"
# Local role simulation: each header value maps to ONE server-side actor (no actor IDs accepted).
ROLES = {"COMPANY": "DEMO-COMPANY-BAT", "OFFICER": "DEMO-OFFICER", "OPERATOR": "DEMO-OPERATOR"}
SAFE_DETAILS = {"used", "available", "question_ids", "fields"}
# Identity, scope and trust signals are server-side only; rejected anywhere in a JSON body.
# Server-computed outputs (index, triage, assisted analysis) can never be supplied either.
FORBIDDEN_INPUT_FIELDS = {"actor_id", "company_id", "assigned_case_ids", "role", "reference_expected",
                          "review_index", "score", "triage", "triage_priority", "investigator_brief"}
ADMIN_NOTICE_FR = "Administration de données synthétiques — démonstration locale."
MAX_JSON_BYTES = 1024 * 1024
HTTP_ERROR_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "LIMIT_EXCEEDED"}


def service(request: Request) -> BousslaAppService:
    return request.app.state.service


def actor(request: Request):
    role = request.headers.get("x-boussla-demo-role", "").upper()
    if role not in ROLES:
        raise BousslaError(ErrorCode.FORBIDDEN, "Rôle de démonstration inconnu")
    # The server roster is authoritative; the browser never supplies identity or scope.
    return service(request).registry.actors[ROLES[role]]


def clean(value):
    """Serialize Pydantic results while excluding internal file paths recursively."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in {"local_path", "_secrets"}}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def result(value, status_code=200):
    return JSONResponse(clean(value), status_code=status_code)


async def body(request: Request) -> dict:
    if int(request.headers.get("content-length", "0") or "0") > MAX_JSON_BYTES:
        raise HTTPException(413, "Corps JSON trop volumineux")
    raw = bytearray()
    async for chunk in request.stream():  # bounded even without an honest Content-Length
        raw.extend(chunk)
        if len(raw) > MAX_JSON_BYTES:
            raise HTTPException(413, "Corps JSON trop volumineux")
    try:
        value = json.loads(bytes(raw))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Corps JSON invalide") from None
    if not isinstance(value, dict):
        raise HTTPException(400, "Objet JSON attendu")
    if contains_forbidden_fields(value):
        raise BousslaError(ErrorCode.FORBIDDEN, "L'identité et le périmètre sont définis par le serveur")
    return value


def contains_forbidden_fields(value) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_INPUT_FIELDS or contains_forbidden_fields(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_fields(item) for item in value)
    return False


def object_field(data: dict, name: str) -> dict:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise HTTPException(400, f"{name} doit être un objet")
    return value


def version(data: dict) -> int:
    value = data.get("expected_version")
    if type(value) is not int or value < 1:
        raise HTTPException(400, "expected_version requis")
    return value


def key(request: Request) -> str:
    value = request.headers.get("idempotency-key", "")
    if not (1 <= len(value) <= 100) or not all(c.isascii() and (c.isalnum() or c in "-_") for c in value):
        raise HTTPException(400, "Idempotency-Key requis")
    return value


async def health(request: Request):
    return result({"status": "ok", "mode": "LOCAL_SYNTHETIC_DEMO"})


async def bootstrap(request: Request):
    a = actor(request)
    cases = ([m["case_id"] for m in service(request).store.list_cases() if m["company_id"] == a.company_id]
             if a.role.value == "COMPANY" else list(a.assigned_case_ids))
    operator = a.role.value == "DEMO_OPERATOR" and service(request).portfolio is not None
    return result({"role": a.role.value, "case_ids": cases,
                   "banner_fr": "Simulation locale de rôles — pas une authentification de production.",
                   "demo_admin": {k: operator for k in ("can_list", "can_seed", "can_reset", "can_add", "can_delete")}})


async def case(request: Request):
    return result(service(request).get_case(actor(request), request.path_params["case_id"]))


async def queue(request: Request):
    cursor = request.query_params.get("cursor")
    if cursor is not None and (not cursor.isdigit() or len(cursor) > 8):
        raise HTTPException(400, "Curseur invalide")
    return result(service(request).list_queue(actor(request), datetime.now(timezone.utc), 50, cursor))


async def history(request: Request):
    return result(service(request).get_history(actor(request), request.path_params["case_id"]))


async def network(request: Request):
    return result(service(request).get_network(actor(request)))


async def network_company(request: Request):
    return result(service(request).get_network(actor(request), company_id=request.path_params["company_id"]))


async def network_case(request: Request):
    return result(service(request).get_network(actor(request), case_id=request.path_params["case_id"]))


async def notifications(request: Request):
    return result(service(request).get_notifications(actor(request), request.path_params["case_id"]))


async def upload(request: Request):
    a = actor(request)
    k = key(request)
    # Bound the request body before the PDF parser runs.
    if int(request.headers.get("content-length", "0") or "0") > 11 * 1024 * 1024:
        raise BousslaError(ErrorCode.LIMIT_EXCEEDED, "Fichier trop volumineux (10 Mo max.)")
    form = await request.form(max_files=1, max_fields=3)
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Fichier PDF requis")
    expected = form.get("expected_version")
    if not isinstance(expected, str) or not expected.isdigit():
        raise HTTPException(400, "expected_version requis")
    response_id = form.get("response_id")
    if response_id is not None and (not isinstance(response_id, str) or not response_id.strip()):
        raise HTTPException(400, "response_id invalide")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise BousslaError(ErrorCode.LIMIT_EXCEEDED, "Fichier trop volumineux (10 Mo max.)")
    value = service(request).upload_document(a, request.path_params["case_id"], content,
                                             file.filename or "", file.content_type or "", int(expected), k,
                                             response_id=response_id)
    return result(value)


async def confirm_transcription(request: Request):
    a, k, data = actor(request), key(request), await body(request)
    return result(service(request).confirm_transcription(
        a, request.path_params["case_id"], request.path_params["proposal_id"],
        object_field(data, "fields"), version(data), k))


async def context(request: Request):
    a, k, data = actor(request), key(request), await body(request)
    return result(service(request).submit_context(a, request.path_params["case_id"],
                                                  object_field(data, "context"), version(data), k))


async def prepare(request: Request):
    a, data = actor(request), await body(request)
    return result(service(request).prepare_clarification(a, request.path_params["case_id"], version(data)))


async def publish(request: Request):
    a, k, data = actor(request), key(request), await body(request)
    return result(service(request).publish_clarification(a, request.path_params["case_id"],
                                                         request.path_params["draft_id"], version(data), k))


async def respond(request: Request):
    a, k, data = actor(request), key(request), await body(request)
    return result(service(request).submit_response(a, request.path_params["case_id"],
                                                   request.path_params["request_id"],
                                                   object_field(data, "response"), version(data), k))


async def decide(request: Request):
    a, k, data = actor(request), key(request), await body(request)
    cid, pid, v = request.path_params["case_id"], request.path_params["proposal_id"], version(data)
    if request.url.path.endswith("/accept"):
        value = service(request).accept_evidence(a, cid, pid, v, k)
    else:
        value = service(request).reject_evidence(a, cid, pid, v, str(data.get("reason", ""))[:500], k)
    return result(value)


async def admin_enterprises(request: Request):
    a = actor(request)
    if request.method == "GET":
        return result({"items": service(request).admin_list_enterprises(a), "notice_fr": ADMIN_NOTICE_FR})
    k, data = key(request), await body(request)
    return result(service(request).admin_add_enterprise(a, data, k))


async def admin_delete(request: Request):
    a, data = actor(request), await body(request)
    return result(service(request).admin_delete_enterprise(a, request.path_params["company_id"],
                                                           str(data.get("confirm", ""))))


async def admin_seed(request: Request):
    a = actor(request)
    return result(service(request).admin_seed_portfolio(a))


async def admin_reset(request: Request):
    a, data = actor(request), await body(request)
    return result(service(request).admin_reset_portfolio(a, str(data.get("confirm", ""))))


async def spa(request: Request):
    path = request.path_params.get("path", "")
    if path.startswith("api/"):
        # Never render the SPA for /api/*: a known API path with the wrong method is 405.
        if any(route.matches(request.scope)[0] is Match.PARTIAL for route in request.app.routes[:-1]):
            raise HTTPException(405)
        raise HTTPException(404)
    if not DIST.is_dir():
        return PlainTextResponse("Frontend absent. Exécutez npm run build dans frontend/.", status_code=503)
    asset = (DIST / path).resolve()
    if path and asset.is_relative_to(DIST.resolve()) and asset.is_file():
        return FileResponse(asset)
    if path and "." in Path(path).name:
        raise HTTPException(404)
    return FileResponse(DIST / "index.html")


async def on_error(request: Request, exc: Exception) -> Response:
    if isinstance(exc, BousslaError):
        status = 403 if exc.code in {ErrorCode.FORBIDDEN, ErrorCode.CROSS_COMPANY} else 404 if exc.code is ErrorCode.NOT_FOUND else 409 if exc.code in {ErrorCode.STALE_REVISION, ErrorCode.IDEMPOTENCY_CONFLICT, ErrorCode.INVALID_STATE} else 400
        return result({"error": {"code": exc.code.value, "message": exc.message,
                                 "details": {k: v for k, v in exc.details.items() if k in SAFE_DETAILS}}}, status)
    if isinstance(exc, HTTPException):
        code = HTTP_ERROR_CODES.get(exc.status_code, "BAD_REQUEST" if exc.status_code < 500 else "INTERNAL_ERROR")
        return result({"error": {"code": code, "message": str(exc.detail), "details": {}}}, exc.status_code)
    if isinstance(exc, (ValidationError, ValueError, TypeError)):
        return result({"error": {"code": "BAD_REQUEST", "message": "Données invalides", "details": {}}}, 400)
    return result({"error": {"code": "INTERNAL_ERROR", "message": "Une erreur est survenue", "details": {}}}, 500)


def create_app(app_service: BousslaAppService | None = None) -> Starlette:
    routes = [
        Route("/api/health", health), Route("/api/demo/bootstrap", bootstrap),
        Route("/api/cases/{case_id}", case), Route("/api/officer/queue", queue),
        Route("/api/cases/{case_id}/history", history),
        Route("/api/cases/{case_id}/notifications", notifications),
        Route("/api/network", network),
        Route("/api/network/company/{company_id}", network_company),
        Route("/api/network/case/{case_id}", network_case),
        Route("/api/cases/{case_id}/documents", upload, methods=["POST"]),
        Route("/api/cases/{case_id}/context", context, methods=["POST"]),
        Route("/api/cases/{case_id}/transcriptions/{proposal_id}/confirm", confirm_transcription, methods=["POST"]),
        Route("/api/cases/{case_id}/clarifications/prepare", prepare, methods=["POST"]),
        Route("/api/cases/{case_id}/clarifications/{draft_id}/publish", publish, methods=["POST"]),
        Route("/api/cases/{case_id}/responses/{request_id}", respond, methods=["POST"]),
        Route("/api/cases/{case_id}/proposals/{proposal_id}/accept", decide, methods=["POST"]),
        Route("/api/cases/{case_id}/proposals/{proposal_id}/reject", decide, methods=["POST"]),
        Route("/api/admin/enterprises", admin_enterprises, methods=["GET", "POST"]),
        Route("/api/admin/enterprises/{company_id}", admin_delete, methods=["DELETE"]),
        Route("/api/admin/portfolio/seed", admin_seed, methods=["POST"]),
        Route("/api/admin/portfolio/reset", admin_reset, methods=["POST"]),
        Route("/{path:path}", spa),
    ]
    @asynccontextmanager
    async def lifespan(app: Starlette):
        # Built when the server starts, never at import: importing this module must not
        # read .env, open provider clients or create runtime/ files.
        if app.state.service is None:
            app.state.service = build_service()
        yield

    application = Starlette(routes=routes, lifespan=lifespan,
                            exception_handlers={BousslaError: on_error, HTTPException: on_error,
                                                ValidationError: on_error, ValueError: on_error, TypeError: on_error,
                                                Exception: on_error})
    application.state.service = app_service
    return application


app = create_app()  # service built at startup (uvicorn boussla.web.app:app)
