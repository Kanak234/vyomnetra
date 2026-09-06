#!/usr/bin/env python3
"""CLI runner to launch the VYOMNETRA FastAPI REST web service."""

import sys
import uvicorn
from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.scripts.run_server")

def main():
    print(f"🚀 Starting {settings.app_name} v{settings.app_version} REST API Web Server on 0.0.0.0:8000...")
    uvicorn.run("vyomnetra.api.app:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
