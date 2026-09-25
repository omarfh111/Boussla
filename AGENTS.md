# BOUSSLA repository instructions

The locked build pack lives in `docs/build_lock/` (`PLAN_ROOT`). Before editing, read in this order:

1. `docs/build_lock/AGENTS.md` — shared rules for every coding assistant.
2. `docs/build_lock/01_FINAL_LOCK.md` — the V4 eight-hour scope.
3. `docs/build_lock/contracts/CONTRACTS.md` — shared interfaces; Python source of truth is `boussla/contracts.py` (lane A).
4. `docs/build_lock/GIT_WORKFLOW.md` — branch, atomic commit and push policy.
5. Your lane handoff in `docs/build_lock/handoffs/`.

Documentation and fixture paths in the handoffs are relative to `docs/build_lock/`; implementation paths (`boussla/`, `ui/`, `app.py`, `tests/`) are relative to the repository root.

Shared contract or dependency change requests go to `docs/build_lock/handoffs/CHANGE_REQUESTS.md` via lane A. Never push directly to `main`.
