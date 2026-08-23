"""Global configuration and environment management for VYOMNETRA."""

import os
import importlib.metadata
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel, Field

DEFAULT_DATA_DIR = Path(os.path.expanduser("~/.local/share/vyomnetra"))

def get_installed_stack_versions() -> Dict[str, str]:
    """Returns exact installed package versions for reproducibility assurance."""
    packages = [
        "sgp4", "skyfield", "astropy", "numpy", "scipy",
        "pandas", "pyside6", "pyqtgraph", "networkx",
        "rdflib", "requests", "pytest", "pydantic"
    ]
    versions = {}
    for pkg in packages:
        try:
            versions[pkg.lower()] = importlib.metadata.version(pkg)
        except Exception:
            versions[pkg.lower()] = "UNAVAILABLE"
    return versions


class GroundSite(BaseModel):
    """Ground station site coordinates."""
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    description: str = ""

# Pre-defined ground sites (Hazaribagh + ISRO sites)
DEFAULT_GROUND_SITES: Dict[str, GroundSite] = {
    "hazaribagh": GroundSite(
        name="Hazaribagh",
        latitude_deg=23.9968,
        longitude_deg=85.3647,
        elevation_m=610.0,
        description="Hazaribagh, Jharkhand, India"
    ),
    "istrac_bengaluru": GroundSite(
        name="ISTRAC Bengaluru",
        latitude_deg=13.0336,
        longitude_deg=77.5647,
        elevation_m=920.0,
        description="ISRO Telemetry, Tracking and Command Network"
    ),
    "sdsc_sriharikota": GroundSite(
        name="SDSC Sriharikota",
        latitude_deg=13.7199,
        longitude_deg=80.2304,
        elevation_m=6.0,
        description="Satish Dhawan Space Centre"
    ),
    "nrsc_hyderabad": GroundSite(
        name="NRSC Hyderabad",
        latitude_deg=17.4729,
        longitude_deg=78.4388,
        elevation_m=542.0,
        description="National Remote Sensing Centre"
    ),
}

class AppSettings(BaseModel):
    """Main application configuration schema."""
    app_name: str = "VYOMNETRA"
    app_version: str = "0.1.0"
    data_dir: Path = Field(default_factory=lambda: DEFAULT_DATA_DIR)
    db_filename: str = "vyomnetra.db"
    
    # CelesTrak / Space-Track Sources
    celestrak_gp_url: str = "https://celestrak.org/NORAD/elements/gp.php"
    celestrak_cache_ttl_hours: int = 6
    space_track_url: str = "https://www.space-track.org"
    space_track_user: str = Field(default_factory=lambda: os.getenv("SPACE_TRACK_USER", ""))
    space_track_password: str = Field(default_factory=lambda: os.getenv("SPACE_TRACK_PASSWORD", ""))
    
    # LLM Settings (Ollama)
    ollama_host: str = Field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen3-coder"))
    
    # Validation Tolerances
    vallado_pos_tolerance_km: float = 1e-6
    vallado_vel_tolerance_kms: float = 1e-9
    skyfield_cross_val_tolerance_m: float = 1.0
    
    # Ground sites
    sites: Dict[str, GroundSite] = DEFAULT_GROUND_SITES

    def get_db_path(self) -> Path:
        """Returns the full path to the SQLite database."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / self.db_filename

    def get_cache_dir(self) -> Path:
        """Returns the full path to the cache directory."""
        cache_path = self.data_dir / "cache"
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    def get_logs_dir(self) -> Path:
        """Returns the full path to the logs directory."""
        logs_path = self.data_dir / "logs"
        logs_path.mkdir(parents=True, exist_ok=True)
        return logs_path

# Global settings singleton
settings = AppSettings()
