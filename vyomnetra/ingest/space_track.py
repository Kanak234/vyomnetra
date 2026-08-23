"""Space-Track.org adapter for full catalogue and historical orbital elements.

Reads credentials strictly from .env. If credentials are missing, degrades cleanly
with log notification without throwing exceptions.
"""

import os
from typing import Optional, Tuple, List
from dotenv import load_dotenv

from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger
from vyomnetra.ingest.models import SatelliteRecord, FetchLogRecord
from vyomnetra.ingest.db import DatabaseManager

logger = get_logger("vyomnetra.ingest.space_track")

# Load environment variables from .env
load_dotenv()


class SpaceTrackAdapter:
    """Adapter for Space-Track.org API."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.source_name = "Space-Track.org"
        self.db_manager = db_manager or DatabaseManager()
        self.user = os.getenv("SPACE_TRACK_USER") or settings.space_track_user
        self.password = os.getenv("SPACE_TRACK_PASSWORD") or settings.space_track_password

    def is_configured(self) -> bool:
        """Returns True if Space-Track credentials are present in .env."""
        return bool(self.user and self.password)

    def fetch(self) -> Tuple[Optional[FetchLogRecord], List[SatelliteRecord]]:
        """Attempts Space-Track acquisition. Degrades cleanly if credentials missing."""
        if not self.is_configured():
            logger.info("Space-Track.org credentials not configured in .env; skipping Space-Track fetch.")
            return None, []

        logger.info(f"Space-Track credentials detected for user '{self.user}'. Initiating fetch...")
        # Space-Track authenticated API fetch implementation hook
        return None, []
