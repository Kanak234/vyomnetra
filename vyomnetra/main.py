"""VYOMNETRA Main CLI Entry Point.

Supports starting GUI workbench, REST API server, or batch conjunction screening.
"""

import sys
import argparse
from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.main")


def main():
    """Main CLI entrypoint for VYOMNETRA."""
    parser = argparse.ArgumentParser(
        description=f"{settings.app_name} v{settings.app_version} — Space Situational Awareness Platform"
    )
    parser.add_argument("--gui", action="store_true", help="Launch PySide6 Desktop GUI Workbench (Default)")
    parser.add_argument("--api", action="store_true", help="Launch FastAPI REST API Web Service")
    parser.add_argument("--screen", action="store_true", help="Execute 24-hour batch conjunction screening")
    parser.add_argument("--version", action="version", version=f"{settings.app_name} v{settings.app_version}")

    args = parser.parse_args()

    logger.info(f"Starting {settings.app_name} v{settings.app_version}...")
    logger.info(f"Database path: {settings.get_db_path()}")

    if args.api:
        import uvicorn
        logger.info("Launching REST API server on http://0.0.0.0:8000...")
        uvicorn.run("vyomnetra.api.app:app", host="0.0.0.0", port=8000, reload=False)
    elif args.screen:
        from scripts.run_screening import main as run_screen
        run_screen()
    else:
        from vyomnetra.ui.app import launch_app
        sys.exit(launch_app())


if __name__ == "__main__":
    main()
