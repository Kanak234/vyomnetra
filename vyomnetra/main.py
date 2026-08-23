"""VYOMNETRA Entry Point."""

import sys
from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger
from vyomnetra.ui.app import launch_app

logger = get_logger("vyomnetra.main")

def main():
    """Main CLI entrypoint for VYOMNETRA."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}...")
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info(f"Database path: {settings.get_db_path()}")
    sys.exit(launch_app())

if __name__ == "__main__":
    main()
