# BOUSSLA React interface

Final portfolio UI contract assumptions and integration fields: [PORTFOLIO_INTEGRATION.md](PORTFOLIO_INTEGRATION.md).

The React application displays the existing `BousslaAppService` views. All case facts, checks, scores, permissions, and revisions remain in Python. The role switch is a **local simulation**, not production authentication.

## Local development

From the repository root, use the existing Python environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn boussla.web.app:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Vite proxies `/api` to Python port 8000. If that port is occupied or reserved, choose another port and update the proxy target in `vite.config.ts` for development.

## Same-origin demo

```powershell
cd frontend
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn boussla.web.app:app --host 127.0.0.1 --port 8000
```

The Starlette process serves both `frontend/dist` and `/api`. If `dist` is absent, `/` returns a clear development error. Streamlit remains available through `app.py`.

Use a fresh `CASE_DB_PATH` and `UPLOAD_DIR` under `runtime/` for each repeatable demonstration. Provider keys are optional; mode labels reflect the service's actual fallback. The reference panel can be empty when the current findings have no mapped public-reference query. A grounded note also requires a configured generator.

## Checks

```powershell
npm.cmd run typecheck
npm.cmd run test
npm.cmd run build
```

The real browser test uses installed Microsoft Edge and an already running same-origin Python server with a fresh demo database:

```powershell
$env:BOUSSLA_E2E_URL='http://127.0.0.1:8000'
npm.cmd run test:e2e
```

The browser test writes the synthetic release screenshots to `docs/screenshots/final_release/` when `BOUSSLA_E2E_SCREENSHOTS=1`. On Windows, the test/build may need permission to let Vite/esbuild read its config and to launch the browser.
