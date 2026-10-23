"""DIU's open solicitations, read from the state its page embeds. No browser and no login.

    html = fetch_page()                  # one request a run
    aois = open_solicitations(html)      # state.aois: the open solicitations

DIU's page draws its list in the browser from a private API, but the server writes the same list
into the page as window.__NUXT__: a JavaScript function whose parameters stand for repeated
values, a few assignments, then `return {...state...}`. nuxt_state() reads that literal syntax
(strings, numbers, objects, arrays, parameter references and the assignments made before
return) and never runs any of it. Docs: portals/diu/NOTES.md.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

SOLICITATIONS_URL = "https://www.diu.mil/work-with-us/open-solicitations"
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"
MARK = "window.__NUXT__="

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in

TOKEN = re.compile(r'\s*(?:("(?:[^"\\]|\\.)*")|(-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)|([A-Za-z_$][\w$]*)'
                   r'|([{}\[\]():;,.=!]))', re.S)
LITERALS = {"true": True, "false": False, "null": None, "undefined": None}


class DiuError(RuntimeError):
    """The page did not answer as expected. The pipeline records it and alerts."""


class _Ref:
    """A parameter named in the state, bound to its argument once the arguments are read."""

    def __init__(self, name: str) -> None:
        self.name = name


class _Reader:
    """Reads `(function(params){assignments; return value}(args))` without running it."""

    def __init__(self, source: str) -> None:
        self.tokens: list[tuple[str, str]] = []
        pos = 0
        while pos < len(source):
            m = TOKEN.match(source, pos)
            if not m:
                if not source[pos:].strip():
                    break
                raise DiuError(f"the page's state has unexpected syntax near character {pos}")
            pos = m.end()
            text, number, name, punct = m.groups()
            self.tokens.append(("s", text) if text else ("n", number) if number else ("i", name) if name else ("p", punct))
        self.at = 0

    def peek(self) -> tuple[str, str]:
        return self.tokens[self.at] if self.at < len(self.tokens) else ("", "")

    def take(self, kind: str | None = None, text: str | None = None) -> tuple[str, str]:
        token = self.peek()
        if (kind and token[0] != kind) or (text is not None and token[1] != text):
            raise DiuError(f"the page's state has unexpected syntax at token {self.at}")
        self.at += 1
        return token

    def _items(self, close: str) -> list[Any]:
        items: list[Any] = []
        while self.peek() != ("p", close):
            items.append(self.value())
            if self.peek() == ("p", ","):
                self.take()
        self.take("p", close)
        return items

    def value(self) -> Any:
        kind, text = self.take()
        if (kind, text) == ("p", "{"):
            obj: dict[str, Any] = {}
            while self.peek() != ("p", "}"):
                key_kind, key = self.take()
                obj_key = _string(key) if key_kind == "s" else key
                self.take("p", ":")
                obj[obj_key] = self.value()
                if self.peek() == ("p", ","):
                    self.take()
            self.take("p", "}")
            return obj
        if (kind, text) == ("p", "["):
            return self._items("]")
        if kind == "s":
            return _string(text)
        if kind == "n":
            return float(text) if any(c in text for c in ".eE") else int(text)
        if (kind, text) == ("p", "!"):
            return self.take("n")[1] == "0"          # !0 is true, !1 is false
        if (kind, text) == ("i", "void"):
            self.take("n")
            return None
        if kind == "i":
            return LITERALS[text] if text in LITERALS else _Ref(text)
        raise DiuError(f"the page's state has unexpected syntax at token {self.at - 1}")

    def program(self) -> Any:
        self.take("p", "(")
        self.take("i", "function")
        self.take("p", "(")
        params: list[str] = []
        while self.peek() != ("p", ")"):
            params.append(self.take("i")[1])
            if self.peek() == ("p", ","):
                self.take()
        self.take("p", ")")
        self.take("p", "{")
        assignments: list[tuple[list[Any], Any]] = []
        while self.peek() != ("i", "return"):
            path: list[Any] = [self.take("i")[1]]
            while self.peek() in (("p", "."), ("p", "[")):
                if self.take()[1] == ".":
                    path.append(self.take("i")[1])
                else:
                    key_kind, key = self.take()
                    path.append(_string(key) if key_kind == "s" else int(key))
                    self.take("p", "]")
            self.take("p", "=")
            assignments.append((path, self.value()))
            self.take("p", ";")
        self.take("i", "return")
        result = self.value()
        if self.peek() == ("p", ";"):
            self.take()
        self.take("p", "}")
        self.take("p", "(")
        args = self._items(")")
        env = dict(zip(params, args))
        for arg in args:
            _resolve(arg, env)
        for path, value in assignments:
            target = env[path[0]]
            for key in path[1:-1]:
                target = target[key]
            target[path[-1]] = _resolve(value, env)
        return _resolve(result, env)


def _string(token: str) -> str:
    try:
        return json.loads(token)
    except json.JSONDecodeError:   # JavaScript escapes JSON does not know
        return json.loads(token.replace("\\'", "'").replace("\\x", "\\u00"))


def _resolve(value: Any, env: dict[str, Any]) -> Any:
    """Bind parameter references in place. A reference returns the one shared object, unvisited."""
    if isinstance(value, _Ref):
        return env.get(value.name)
    if isinstance(value, dict):
        for key in list(value):
            value[key] = _resolve(value[key], env)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            value[i] = _resolve(item, env)
    return value


def nuxt_state(html: str) -> dict[str, Any]:
    """The page's embedded Nuxt state."""
    start = html.find(MARK)
    end = html.find("</script>", start)
    if start == -1 or end == -1:
        raise DiuError("the page carries no embedded state (window.__NUXT__)")
    source = html[start + len(MARK):end].strip().rstrip(";")
    result = _Reader(source).program()
    state = result.get("state") if isinstance(result, dict) else None
    if not isinstance(state, dict):
        raise DiuError("the page's embedded state has no state object")
    return state


def open_solicitations(html: str) -> list[dict[str, Any]]:
    aois = nuxt_state(html).get("aois")
    if not isinstance(aois, list):
        raise DiuError("the page's state has no solicitation list")
    return [aoi for aoi in aois if isinstance(aoi, dict)]


def fetch_page(opener: Opener | None = None) -> str:
    """The open-solicitations page, retried once."""
    opener = opener or urllib.request.urlopen
    problem = ""
    for _ in range(2):
        request = urllib.request.Request(SOLICITATIONS_URL, headers={"User-Agent": USER_AGENT})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                return reply.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
    raise DiuError(f"DIU did not answer ({problem})")
