"""Command-line interface.

    sip db upgrade                 apply migrations (app DB) and create the vault schema
    sip serve [--host --port]      run the API
    sip run --scenario northstar   run an investigation end-to-end in the terminal (scripted reviewer)
    sip eval run --scenario northstar [--reasoner offline|llm] [--output DIR]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sip.config import REPO_ROOT, ReasonerMode, get_settings


def _db_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    from sip.privacy.vault import SqlVault

    settings = get_settings()
    settings.sip_var_dir.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(REPO_ROOT / "alembic.ini")) if (REPO_ROOT / "alembic.ini").exists() else Config()
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.attributes["database_url"] = settings.database_url
    command.upgrade(cfg, "head")

    async def vault() -> None:
        v = SqlVault.from_url(settings.vault_database_url)
        await v.create_schema()
        await v.engine.dispose()

    asyncio.run(vault())
    print("Database migrated; vault schema ready.")


def _serve(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run("sip.api.main:app", host=host, port=port, proxy_headers=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sip", description="Strategic Investigation Platform")
    sub = parser.add_subparsers(dest="cmd", required=True)
    db = sub.add_parser("db").add_subparsers(dest="db_cmd", required=True)
    db.add_parser("upgrade")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    run = sub.add_parser("run", help="Run a scenario end-to-end in the terminal")
    run.add_argument("--scenario", default="northstar")
    run.add_argument("--reasoner", choices=[m.value for m in ReasonerMode], default=None)
    run.add_argument("--json", type=Path, default=None, help="write final state summary as JSON")
    ev = sub.add_parser("eval").add_subparsers(dest="eval_cmd", required=True)
    er = ev.add_parser("run")
    er.add_argument("--scenario", action="append", help="scenario id (repeatable); default all")
    er.add_argument("--reasoner", choices=[m.value for m in ReasonerMode], default=None)
    er.add_argument("--output", type=Path, default=REPO_ROOT / "evals" / "reports" / "latest")
    er.add_argument("--langsmith", action="store_true", help="also log results to a LangSmith experiment")
    args = parser.parse_args(argv)

    if args.cmd == "db":
        _db_upgrade()
    elif args.cmd == "serve":
        _serve(args.host, args.port)
    elif args.cmd == "run":
        from sip.services.terminal import run_scenario

        asyncio.run(run_scenario(args.scenario, args.reasoner, args.json))
    elif args.cmd == "eval":
        sys.path.insert(0, str(REPO_ROOT))
        from evals.runner import main as eval_main

        code = asyncio.run(eval_main(args.scenario, args.reasoner, args.output, args.langsmith))
        raise SystemExit(code)


if __name__ == "__main__":
    main()
