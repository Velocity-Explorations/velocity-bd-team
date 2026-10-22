"""
Yukon — Profile loader
Loads profile.yaml + .env from configs/<profile_name>/
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv


@dataclass
class Portal:
    id: str
    name: str
    url: str
    cadence: str  # nightly | weekly
    type: str     # api | scrape
    auth: bool = False


@dataclass
class Profile:
    name: str
    discord_channel: str
    naics: List[str]
    keywords: List[str]           # broad keywords — used with NAICS-gated portals (SAM.gov)
    scrape_keywords: List[str]    # tight keywords — used for DoD scrape portals (NSTXL, DIU)
    bidnet_keywords: List[str]    # state/local IT keywords — used for BidNet CO/FL
    set_asides: List[str]
    portals: List[Portal]
    env: dict = field(default_factory=dict)
    slack_channel: str = ""
    google_drive_folder_id: str = ""
    google_drive_account: str = ""


def load_profile(profile_name: str, project_root: Optional[Path] = None) -> Profile:
    """Load a profile by name from configs/<profile_name>/"""
    if project_root is None:
        project_root = Path(__file__).parent.parent

    config_dir = project_root / "configs" / profile_name
    profile_path = config_dir / "profile.yaml"
    env_path = config_dir / ".env"

    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    # Load .env into environment
    if env_path.exists():
        load_dotenv(env_path, override=True)

    # Load profile.yaml
    with open(profile_path, "r") as f:
        data = yaml.safe_load(f)

    # Parse portals
    portals = []
    for p in data.get("portals", []):
        portals.append(Portal(
            id=p["id"],
            name=p["name"],
            url=p["url"],
            cadence=p.get("cadence", "weekly"),
            type=p.get("type", "scrape"),
            auth=p.get("auth", False),
        ))

    # Collect env vars relevant to this profile
    env = {k: v for k, v in os.environ.items() if v}

    broad_keywords = [str(k).lower() for k in data.get("keywords", [])]

    # scrape_keywords: tighter set for portals without NAICS gating
    # Falls back to broad keywords if not explicitly defined
    scrape_keywords = [str(k).lower() for k in data.get("scrape_keywords", broad_keywords)]

    return Profile(
        name=data.get("name", profile_name),
        discord_channel=str(data.get("discord_channel", "")),
        naics=[str(n) for n in data.get("naics", [])],
        keywords=broad_keywords,
        scrape_keywords=scrape_keywords,
        bidnet_keywords=[str(k).lower() for k in data.get("bidnet_keywords", scrape_keywords)],
        set_asides=[str(s).upper() for s in data.get("set_asides", [])],
        portals=portals,
        env=env,
        slack_channel=str(data.get("slack_channel", "")),
        google_drive_folder_id=str(data.get("google_drive_folder_id", "")),
        google_drive_account=str(data.get("google_drive_account", "")),
    )


def list_profiles(project_root: Optional[Path] = None) -> List[str]:
    """Return all available profile names (subdirs of configs/ with a profile.yaml)"""
    if project_root is None:
        project_root = Path(__file__).parent.parent

    configs_dir = project_root / "configs"
    profiles = []
    for d in configs_dir.iterdir():
        if d.is_dir() and d.name != "_template" and (d / "profile.yaml").exists():
            profiles.append(d.name)
    return sorted(profiles)
