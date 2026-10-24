"""NASA Forecast portal adapter. The pipeline discovers it through PORTAL (see portals/registry.py)."""
from __future__ import annotations


def __getattr__(name: str):
    # Lazy, the same as the other portal packages, so importing a submodule never loads the rest.
    if name == "PORTAL":
        from portals.nasa_forecast.portal import PORTAL

        return PORTAL
    raise AttributeError(name)
