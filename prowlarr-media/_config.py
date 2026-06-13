"""Configuration loading and Prowlarr indexer resolution for prowlarr-media.

Stdlib-only (Python 3.11+ for `tomllib`). Shared by grab.py and monitor.py.

Responsibilities:
  * Locate and parse config.toml (with a clear error if it's missing).
  * Apply environment-variable overrides for secrets.
  * Validate required sections.
  * Resolve a tracker spec ("all" | "ptp,btn" | "4,6") to concrete indexer IDs
    by discovering indexers from Prowlarr at runtime.
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# secret field  ->  environment variable that overrides it
_ENV_OVERRIDES = {
    ("prowlarr", "api_key"): "PROWLARR_API_KEY",
    ("clients.qbittorrent", "password"): "QBT_PASSWORD",
    ("clients.sabnzbd", "api_key"): "SAB_API_KEY",
    ("clients.sabnzbd", "password"): "SAB_PASSWORD",
    ("media_server", "token"): "MEDIA_SERVER_TOKEN",
}


class ConfigError(RuntimeError):
    """Raised for any user-fixable configuration problem."""


def _candidate_paths() -> list[Path]:
    here = Path(__file__).resolve().parent
    paths = []
    if os.environ.get("PROWLARR_MEDIA_CONFIG"):
        paths.append(Path(os.environ["PROWLARR_MEDIA_CONFIG"]).expanduser())
    paths.append(here / "config.toml")
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        paths.append(Path(xdg) / "prowlarr-media" / "config.toml")
    paths.append(Path.home() / ".config" / "prowlarr-media" / "config.toml")
    return paths


def _apply_env_overrides(cfg: dict) -> None:
    for (section, key), env in _ENV_OVERRIDES.items():
        val = os.environ.get(env)
        if not val:
            continue
        node = cfg
        for part in section.split("."):
            node = node.setdefault(part, {})
        node[key] = val


class Config:
    """Parsed configuration with convenience accessors."""

    def __init__(self, data: dict, path: Path | None):
        self.data = data
        self.path = path

    # -- section accessors -------------------------------------------------
    @property
    def prowlarr_url(self) -> str:
        return self.data["prowlarr"]["url"].rstrip("/")

    @property
    def prowlarr_key(self) -> str:
        return self.data["prowlarr"]["api_key"]

    def client(self, name: str) -> dict | None:
        c = self.data.get("clients", {}).get(name)
        if c and c.get("enabled"):
            return c
        return None

    @property
    def media_server(self) -> dict | None:
        ms = self.data.get("media_server")
        if ms and ms.get("enabled") and ms.get("type", "none") != "none":
            return ms
        return None

    def category(self, name: str) -> dict:
        cats = self.data.get("categories", {})
        if name not in cats:
            known = ", ".join(sorted(cats)) or "(none defined)"
            raise ConfigError(
                f"Category {name!r} is not defined in {self.path}. "
                f"Defined categories: {known}. Add a [categories.{name}] section."
            )
        return cats[name]

    @property
    def categories(self) -> list[str]:
        return sorted(self.data.get("categories", {}))

    @property
    def tracker_aliases(self) -> dict:
        return self.data.get("trackers", {})


def load() -> Config:
    """Find, parse, validate, and return the configuration."""
    chosen: Path | None = None
    for p in _candidate_paths():
        if p.is_file():
            chosen = p
            break
    if chosen is None:
        searched = "\n  ".join(str(p) for p in _candidate_paths())
        raise ConfigError(
            "No config.toml found. Copy the template and fill it in:\n"
            "    cp config.example.toml config.toml\n"
            f"Searched:\n  {searched}"
        )

    try:
        with chosen.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{chosen} is not valid TOML: {e}") from e

    _apply_env_overrides(data)

    # Minimal validation — fail early with an actionable message.
    pw = data.get("prowlarr", {})
    if not pw.get("url") or not pw.get("api_key"):
        raise ConfigError(
            f"{chosen}: [prowlarr] needs both `url` and `api_key` "
            "(or set PROWLARR_API_KEY)."
        )
    if "example" in pw.get("api_key", "") or "example" in pw.get("url", ""):
        raise ConfigError(
            f"{chosen} still has placeholder values — edit it with your real "
            "Prowlarr url and api_key."
        )

    return Config(data, chosen)


# ── Prowlarr indexer discovery ───────────────────────────────────────────

_indexer_cache: list[dict] | None = None


def list_indexers(cfg: Config) -> list[dict]:
    """Return Prowlarr indexers (cached for the process).

    Each dict has at least: id, name, enable, protocol.
    """
    global _indexer_cache
    if _indexer_cache is not None:
        return _indexer_cache
    req = urllib.request.Request(
        f"{cfg.prowlarr_url}/api/v1/indexer",
        headers={"X-Api-Key": cfg.prowlarr_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            _indexer_cache = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ConfigError(
            f"Prowlarr returned HTTP {e.code} listing indexers — check the "
            f"url and api_key in {cfg.path}."
        ) from e
    except urllib.error.URLError as e:
        raise ConfigError(
            f"Could not reach Prowlarr at {cfg.prowlarr_url}: {e.reason}"
        ) from e
    return _indexer_cache


def resolve_indexers(cfg: Config, spec: str) -> list[int]:
    """Resolve a tracker spec to a list of indexer IDs.

    spec forms (mixable, comma-separated):
      * "all"              -> every enabled indexer
      * "4,6"              -> raw IDs, used as-is
      * "ptp,btn"          -> names: config alias first, then case-insensitive
                              substring match against live indexer names
    """
    spec = spec.strip()
    if spec.lower() == "all":
        return [i["id"] for i in list_indexers(cfg) if i.get("enable", True)]

    aliases = cfg.tracker_aliases
    indexers = None  # lazy — only fetch when a name needs matching
    out: list[int] = []
    seen: set[int] = set()

    for token in (t.strip() for t in spec.split(",") if t.strip()):
        if token.isdigit():
            _add(out, seen, int(token))
            continue
        if token in aliases:
            _add(out, seen, int(aliases[token]))
            continue
        # name match against live indexers
        if indexers is None:
            indexers = list_indexers(cfg)
        matches = [
            i for i in indexers
            if token.lower() in i.get("name", "").lower()
            and i.get("enable", True)
        ]
        if not matches:
            available = ", ".join(sorted(i.get("name", "?") for i in indexers))
            raise ConfigError(
                f"No enabled indexer matches {token!r}. "
                f"Available: {available}. "
                f"Use --list-indexers to see IDs, or add an alias under [trackers]."
            )
        for m in matches:
            _add(out, seen, m["id"])

    if not out:
        raise ConfigError(f"Tracker spec {spec!r} resolved to no indexers.")
    return out


def _add(out: list[int], seen: set[int], i: int) -> None:
    if i not in seen:
        seen.add(i)
        out.append(i)


def die(msg: str) -> None:
    """Print a ConfigError-style message to stderr and exit non-zero."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)
