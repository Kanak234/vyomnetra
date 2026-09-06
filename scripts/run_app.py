#!/usr/bin/env python3
"""CLI runner to launch the VYOMNETRA PySide6 desktop GUI application."""

import sys
from vyomnetra.ui.app import launch_app

def main():
    sys.exit(launch_app())

if __name__ == "__main__":
    main()
