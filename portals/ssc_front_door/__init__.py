"""SSC Front Door portal adapter. The pipeline discovers it through PORTAL (see portals/registry.py)."""
from __future__ import annotations


def __getattr__(name: str):
    # Lazy, the same as the Vulcan SOF package, so importing a submodule never loads the rest.
    if name == "PORTAL":
        from portals.ssc_front_door.portal import PORTAL

        return PORTAL
    raise AttributeError(name)
