"""Indian Space Research Organisation (ISRO) Asset Catalogue & Priority Metadata.

Curated database of Indian space assets across LEO, MEO, GEO, and deep space missions,
providing elevated security classification defaults and priority screening policies.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel


class ISROAsset(BaseModel):
    """Metadata model for an Indian space asset."""
    norad_id: int
    name: str
    constellation: str  # e.g., 'NavIC', 'Cartosat', 'GSAT', 'INSAT', 'RISAT', 'Scientific'
    orbit_regime: str   # 'LEO', 'MEO', 'GEO', 'HEO', 'DEEP_SPACE'
    classification: str # Default classification level: 'RESTRICTED', 'CONFIDENTIAL', 'SECRET'
    operator: str = "ISRO"
    priority: int = 1   # Priority tier (1 highest)
    launch_year: int
    mission_status: str # 'OPERATIONAL', 'RETIRED', 'RE-ENTRY_PENDING'


# Curated catalog of Indian Assets (NORAD IDs mapped to metadata)
ISRO_CATALOGUE: Dict[int, ISROAsset] = {
    # NavIC / IRNSS Constellation (MEO/GEO/IGSO)
    39199: ISROAsset(norad_id=39199, name="IRNSS-1A", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2013, mission_status="OPERATIONAL"),
    40004: ISROAsset(norad_id=40004, name="IRNSS-1B", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2014, mission_status="OPERATIONAL"),
    40269: ISROAsset(norad_id=40269, name="IRNSS-1C", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2014, mission_status="OPERATIONAL"),
    40505: ISROAsset(norad_id=40505, name="IRNSS-1D", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2015, mission_status="OPERATIONAL"),
    41241: ISROAsset(norad_id=41241, name="IRNSS-1E", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2016, mission_status="OPERATIONAL"),
    41384: ISROAsset(norad_id=41384, name="IRNSS-1F", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2016, mission_status="OPERATIONAL"),
    41469: ISROAsset(norad_id=41469, name="IRNSS-1G", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2016, mission_status="OPERATIONAL"),
    43286: ISROAsset(norad_id=43286, name="IRNSS-1I", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2018, mission_status="OPERATIONAL"),
    56759: ISROAsset(norad_id=56759, name="NVS-01", constellation="NavIC", orbit_regime="GEO", classification="CONFIDENTIAL", priority=1, launch_year=2023, mission_status="OPERATIONAL"),

    # GSAT & INSAT Series (GEO Communications & Meteorology)
    31752: ISROAsset(norad_id=31752, name="INSAT-4CR", constellation="INSAT", orbit_regime="GEO", classification="RESTRICTED", priority=2, launch_year=2007, mission_status="OPERATIONAL"),
    37834: ISROAsset(norad_id=37834, name="GSAT-12", constellation="GSAT", orbit_regime="GEO", classification="RESTRICTED", priority=2, launch_year=2011, mission_status="OPERATIONAL"),
    39241: ISROAsset(norad_id=39241, name="GSAT-7", constellation="GSAT", orbit_regime="GEO", classification="SECRET", priority=1, launch_year=2013, mission_status="OPERATIONAL"),
    39574: ISROAsset(norad_id=39574, name="INSAT-3D", constellation="INSAT", orbit_regime="GEO", classification="RESTRICTED", priority=2, launch_year=2013, mission_status="OPERATIONAL"),
    41748: ISROAsset(norad_id=41748, name="INSAT-3DR", constellation="INSAT", orbit_regime="GEO", classification="RESTRICTED", priority=2, launch_year=2016, mission_status="OPERATIONAL"),
    42747: ISROAsset(norad_id=42747, name="GSAT-19", constellation="GSAT", orbit_regime="GEO", classification="CONFIDENTIAL", priority=2, launch_year=2017, mission_status="OPERATIONAL"),
    43031: ISROAsset(norad_id=43031, name="GSAT-17", constellation="GSAT", orbit_regime="GEO", classification="CONFIDENTIAL", priority=2, launch_year=2017, mission_status="OPERATIONAL"),
    43716: ISROAsset(norad_id=43716, name="GSAT-29", constellation="GSAT", orbit_regime="GEO", classification="CONFIDENTIAL", priority=2, launch_year=2018, mission_status="OPERATIONAL"),
    43846: ISROAsset(norad_id=43846, name="GSAT-11", constellation="GSAT", orbit_regime="GEO", classification="CONFIDENTIAL", priority=2, launch_year=2018, mission_status="OPERATIONAL"),
    43865: ISROAsset(norad_id=43865, name="GSAT-7A", constellation="GSAT", orbit_regime="GEO", classification="SECRET", priority=1, launch_year=2018, mission_status="OPERATIONAL"),
    45026: ISROAsset(norad_id=45026, name="GSAT-30", constellation="GSAT", orbit_regime="GEO", classification="CONFIDENTIAL", priority=2, launch_year=2020, mission_status="OPERATIONAL"),
    52898: ISROAsset(norad_id=52898, name="GSAT-24", constellation="GSAT", orbit_regime="GEO", classification="CONFIDENTIAL", priority=2, launch_year=2022, mission_status="OPERATIONAL"),
    58994: ISROAsset(norad_id=58994, name="INSAT-3DS", constellation="INSAT", orbit_regime="GEO", classification="RESTRICTED", priority=2, launch_year=2024, mission_status="OPERATIONAL"),

    # Earth Observation (Cartosat, RISAT, Oceansat, ResourceSat) - LEO
    28649: ISROAsset(norad_id=28649, name="CARTOSAT-1", constellation="Cartosat", orbit_regime="LEO", classification="CONFIDENTIAL", priority=2, launch_year=2005, mission_status="OPERATIONAL"),
    30798: ISROAsset(norad_id=30798, name="CARTOSAT-2", constellation="Cartosat", orbit_regime="LEO", classification="CONFIDENTIAL", priority=2, launch_year=2007, mission_status="OPERATIONAL"),
    33053: ISROAsset(norad_id=33053, name="CARTOSAT-2A", constellation="Cartosat", orbit_regime="LEO", classification="CONFIDENTIAL", priority=2, launch_year=2008, mission_status="OPERATIONAL"),
    34807: ISROAsset(norad_id=34807, name="RISAT-2", constellation="RISAT", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2009, mission_status="RETIRED"),
    35931: ISROAsset(norad_id=35931, name="OCEANSAT-2", constellation="Oceansat", orbit_regime="LEO", classification="RESTRICTED", priority=3, launch_year=2009, mission_status="OPERATIONAL"),
    37387: ISROAsset(norad_id=37387, name="RESOURCESAT-2", constellation="ResourceSat", orbit_regime="LEO", classification="RESTRICTED", priority=3, launch_year=2011, mission_status="OPERATIONAL"),
    38248: ISROAsset(norad_id=38248, name="RISAT-1", constellation="RISAT", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2012, mission_status="RETIRED"),
    41599: ISROAsset(norad_id=41599, name="CARTOSAT-2C", constellation="Cartosat", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2016, mission_status="OPERATIONAL"),
    41783: ISROAsset(norad_id=41783, name="SCATSAT-1", constellation="Scientific", orbit_regime="LEO", classification="RESTRICTED", priority=3, launch_year=2016, mission_status="OPERATIONAL"),
    42767: ISROAsset(norad_id=42767, name="CARTOSAT-2E", constellation="Cartosat", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2017, mission_status="OPERATIONAL"),
    43116: ISROAsset(norad_id=43116, name="CARTOSAT-2F", constellation="Cartosat", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2018, mission_status="OPERATIONAL"),
    44804: ISROAsset(norad_id=44804, name="CARTOSAT-3", constellation="Cartosat", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2019, mission_status="OPERATIONAL"),
    44857: ISROAsset(norad_id=44857, name="RISAT-2B", constellation="RISAT", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2019, mission_status="OPERATIONAL"),
    44874: ISROAsset(norad_id=44874, name="RISAT-2BR1", constellation="RISAT", orbit_regime="LEO", classification="SECRET", priority=1, launch_year=2019, mission_status="OPERATIONAL"),
    54361: ISROAsset(norad_id=54361, name="OCEANSAT-3 (EOS-06)", constellation="Oceansat", orbit_regime="LEO", classification="RESTRICTED", priority=2, launch_year=2022, mission_status="OPERATIONAL"),

    # Scientific & Deep Space Missions
    40930: ISROAsset(norad_id=40930, name="ASTROSAT", constellation="Scientific", orbit_regime="LEO", classification="RESTRICTED", priority=2, launch_year=2015, mission_status="OPERATIONAL"),
    44441: ISROAsset(norad_id=44441, name="CHANDRAYAAN-2 ORBITER", constellation="Scientific", orbit_regime="DEEP_SPACE", classification="CONFIDENTIAL", priority=1, launch_year=2019, mission_status="OPERATIONAL"),
    57320: ISROAsset(norad_id=57320, name="CHANDRAYAAN-3 PROPULSION", constellation="Scientific", orbit_regime="DEEP_SPACE", classification="CONFIDENTIAL", priority=1, launch_year=2023, mission_status="OPERATIONAL"),
    57759: ISROAsset(norad_id=57759, name="ADITYA-L1", constellation="Scientific", orbit_regime="DEEP_SPACE", classification="CONFIDENTIAL", priority=1, launch_year=2023, mission_status="OPERATIONAL"),
    58694: ISROAsset(norad_id=58694, name="XPOSAT", constellation="Scientific", orbit_regime="LEO", classification="RESTRICTED", priority=2, launch_year=2024, mission_status="OPERATIONAL"),
}


def is_isro_asset(norad_id: int) -> bool:
    """Checks whether a given NORAD ID belongs to the ISRO Catalogue."""
    return norad_id in ISRO_CATALOGUE


def get_isro_asset(norad_id: int) -> Optional[ISROAsset]:
    """Retrieves ISRO Asset metadata for a NORAD ID, or None if not found."""
    return ISRO_CATALOGUE.get(norad_id)


def get_isro_catalogue() -> List[ISROAsset]:
    """Returns all curated ISRO assets."""
    return list(ISRO_CATALOGUE.values())


def get_isro_classification(norad_id: int, default: str = "UNCLASSIFIED") -> str:
    """Returns the security classification of an ISRO asset."""
    asset = get_isro_asset(norad_id)
    return asset.classification if asset else default


def enforce_isro_severity_floor(
    primary_norad: int,
    secondary_norad: int,
    computed_severity: str
) -> str:
    """Enforces an automatic HIGH minimum severity floor for conjunctions involving ISRO assets.
    
    If either primary or secondary satellite is an ISRO asset, the severity is bumped
    to 'HIGH' if it was originally 'LOW' or 'MEDIUM'.
    """
    if is_isro_asset(primary_norad) or is_isro_asset(secondary_norad):
        if computed_severity in ("LOW", "MEDIUM"):
            return "HIGH"
    return computed_severity
