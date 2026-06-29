#!/usr/bin/env python3
"""Single backend entry point: API server (default) or CLI pipeline."""
import argparse
import sys

from app.core.config import get_settings


def serve(host=None, port=None, reload=None) -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=settings.reload if reload is None else reload,
    )


def main() -> None:
    settings = get_settings()
    argv = sys.argv[1:]

    if not argv:
        serve()
        return

    if argv[0] == "serve":
        parser = argparse.ArgumentParser(description="Start the API server")
        parser.add_argument("--host", default=settings.host)
        parser.add_argument("--port", type=int, default=settings.port)
        parser.add_argument("--no-reload", action="store_true")
        args = parser.parse_args(argv[1:])
        serve(host=args.host, port=args.port, reload=not args.no_reload)
        return

    if argv[0] == "cli":
        from app.cli.commands import run_cli

        raise SystemExit(run_cli(argv[1:]))

    if argv[0] in ("-h", "--help"):
        print(__doc__)
        print("  python main.py          Start API server")
        print("  python main.py cli      Run CLI pipeline")
        return

    from app.cli.commands import run_cli

    raise SystemExit(run_cli(argv))


if __name__ == "__main__":
    main()
