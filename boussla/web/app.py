"""Thin Starlette adapter. The service owns permissions, facts, and revisions."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from boussla.contracts import BousslaError, ErrorCode
from boussla.services import BousslaAppService, build_service

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"
ROLES = {"COMPANY": "DEMO-COMPANY-BAT", "OFFICER": "DEMO-OFFICER"}
SAFE_DETAILS = {"used", "available", "question_ids", "fields"}


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
    try:
        value = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Corps JSON invalide") from None
    if not isinstance(value, dict):
        raise HTTPException(400, "Objet JSON attendu")
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
    cases = (["CASE-BRICKS-001"] if a.role.value == "COMPANY" else list(a.assigned_case_ids))
    return result({"role": a.role.value, "case_ids": cases,
                   "banner_fr": "Simulation locale de rôles — pas une authentification de production."})


async def case(request: Request):
    return result(service(request).get_case(actor(request), request.path_params["case_id"]))


async def queue(request: Request):
    cursor = request.query_params.get("cursor")
    if cursor is not None and (not cursor.isdigit() or len(cursor) > 8):
        raise HTTPException(400, "Curseur invalide")
    return result(service(request).list_queue(actor(request), datetime.now(timezone.utc), 50, cursor))


async def history(request: Request):
    return result(service(request).get_history(actor(request), request.path_params["case_id"]))


async def upload(request: Request):
    a = actor(request)
    k = key(request)
    # Bound the request body before the PDF parser runs.
    if int(request.headers.get("content-length", "0") or "0") > 11 * 1024 * 1024:
        raise BousslaError(ErrorCode.LIMIT_EXCEEDED, "Fichier trop volumineux (10 Mo max.)")
    form = await request.form(max_files=1, max_fields=2)
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(400, "Fichier PDF requis")
    expected = form.get("expected_version")
    if not isinstance(expected, str) or not expected.isdigit():
        raise HTTPException(400, "expected_version requis")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise BousslaError(ErrorCode.LIMIT_EXCEEDED, "Fichier trop volumineux (10 Mo max.)")
    value = service(request).upload_document(a, request.path_params["case_id"], content,
                                             file.filename or "", file.content_type or "", int(expected), k)
    return result(value)


async def context(request: Request):
    a, k, data = actor(request), key(request), await body(request)
    return result(service(request).submit_context(a, request.path_params["case_id"],
                                                  data.get("context", {}), version(data), k))


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
                                                   data.get("response", {}), version(data), k))


async def decide(request: Request):
    a, k, data = actor(request), key(request), await body(request)
    cid, pid, v = request.path_params["case_id"], request.path_params["proposal_id"], version(data)
    if request.url.path.endswith("/accept"):
        value = service(request).accept_evidence(a, cid, pid, v, k)
    else:
        value = service(request).reject_evidence(a, cid, pid, v, str(data.get("reason", ""))[:500], k)
    return result(value)


async def spa(request: Request):
    path = request.path_params.get("path", "")
    if path.startswith("api/"):
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
        return result({"error": {"code": "BAD_REQUEST" if exc.status_code < 500 else "NOT_FOUND",
                                 "message": str(exc.detail), "details": {}}}, exc.status_code)
    if isinstance(exc, (ValidationError, ValueError, TypeError)):
        return result({"error": {"code": "BAD_REQUEST", "message": "Données invalides", "details": {}}}, 400)
    return result({"error": {"code": "INTERNAL_ERROR", "message": "Une erreur est survenue", "details": {}}}, 500)


def create_app(app_service: BousslaAppService | None = None) -> Starlette:
    routes = [
        Route("/api/health", health), Route("/api/demo/bootstrap", bootstrap),
        Route("/api/cases/{case_id}", case), Route("/api/officer/queue", queue),
        Route("/api/cases/{case_id}/history", history),
        Route("/api/cases/{case_id}/documents", upload, methods=["POST"]),
        Route("/api/cases/{case_id}/context", context, methods=["POST"]),
        Route("/api/cases/{case_id}/clarifications/prepare", prepare, methods=["POST"]),
        Route("/api/cases/{case_id}/clarifications/{draft_id}/publish", publish, methods=["POST"]),
        Route("/api/cases/{case_id}/responses/{request_id}", respond, methods=["POST"]),
        Route("/api/cases/{case_id}/proposals/{proposal_id}/accept", decide, methods=["POST"]),
        Route("/api/cases/{case_id}/proposals/{proposal_id}/reject", decide, methods=["POST"]),
        Route("/{path:path}", spa),
    ]
    application = Starlette(routes=routes, exception_handlers={BousslaError: on_error, HTTPException: on_error,
                          ValidationError: on_error, ValueError: on_error, TypeError: on_error, Exception: on_error})
    application.state.service = app_service or build_service()
    return application


app = create_app()
