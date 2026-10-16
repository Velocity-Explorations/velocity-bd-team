"""Vulcan SOF portal adapter. The pipeline discovers it through PORTAL (see portals/registry.py)."""
from __future__ import annotations


def __getattr__(name: str):
    # Lazy so that importing the package for its submodules never pulls in Playwright first.
    if name == "PORTAL":
        from portals.vulcan_sof.portal import PORTAL

        return PORTAL
    raise AttributeError(name)
