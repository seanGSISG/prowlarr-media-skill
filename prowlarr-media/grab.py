#!/usr/bin/env python3
"""Atomic search + grab for the prowlarr-media skill.

Searches Prowlarr and hands the chosen release to the right download client in
a single process, so Prowlarr's one-shot `downloadUrl` token can't expire
between a search call and a grab call.

  torrent  -> qBittorrent
  usenet   -> SABnzbd / RDT-Client

All connection details come from config.toml (see config.example.toml).

Examples:
    grab.py --query "Some Movie 2024 2160p" --tracker all --dry-run
    grab.py --query "Some Show S01 1080p" --tracker btn --match bluray --category tv
    grab.py --query "Album Name FLAC" --indexers 4,6 --category music
    grab.py --list-indexers
    grab.py --show-config
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request

import _config
from _clients import QbtClient, SabClient


def search(cfg: _config.Config, query: str, indexer_ids: list[int], limit: int) -> list[dict]:
    # Prowlarr requires indexerIds repeated per ID, NOT comma-joined
    # (comma-joined returns HTTP 400).
    params: list[tuple[str, str]] = [("query", query), ("limit", str(limit))]
    params += [("indexerIds", str(i)) for i in indexer_ids]
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{cfg.prowlarr_url}/api/v1/search?{qs}",
        headers={"X-Api-Key": cfg.prowlarr_key},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        import json
        return json.loads(r.read())


def pick(results: list[dict], match: str | None, prefer_protocol: str) -> dict | None:
    pool = results
    if match:
        m = match.lower()
        pool = [r for r in pool if m in r.get("title", "").lower()]
        if not pool:
            return None
    preferred = [r for r in pool if r.get("protocol") == prefer_protocol]
    if preferred:
        pool = preferred
    pool.sort(key=lambda r: r.get("seeders") or 0, reverse=True)
    return pool[0] if pool else None


def fetch_torrent(download_url: str) -> bytes:
    with urllib.request.urlopen(download_url, timeout=30) as r:
        data = r.read()
    if not data.startswith(b"d"):
        raise RuntimeError(f"downloadUrl did not return a torrent: {data[:200]!r}")
    return data


def refresh_media_server(cfg: _config.Config) -> None:
    ms = cfg.media_server
    if not ms:
        return
    try:
        if ms["type"] == "jellyfin":
            req = urllib.request.Request(
                f"{ms['url'].rstrip('/')}/Library/Refresh",
                method="POST",
                headers={"Authorization": f'MediaBrowser Token="{ms["token"]}"'},
            )
            urllib.request.urlopen(req, timeout=15)
        elif ms["type"] == "plex":
            url = f"{ms['url'].rstrip('/')}/library/sections/all/refresh?X-Plex-Token={ms['token']}"
            urllib.request.urlopen(url, timeout=15)
        print(f"Triggered {ms['type']} library refresh.")
    except Exception as e:  # noqa: BLE001 — refresh is best-effort
        print(f"(media-server refresh failed, non-fatal: {e})", file=sys.stderr)


def cmd_list_indexers(cfg: _config.Config) -> int:
    indexers = _config.list_indexers(cfg)
    print(f"{'ID':<4} {'PROTO':<8} {'EN':<3} NAME")
    for i in sorted(indexers, key=lambda x: x["id"]):
        en = "y" if i.get("enable", True) else "n"
        print(f"{i['id']:<4} {i.get('protocol','?'):<8} {en:<3} {i.get('name','?')}")
    return 0


def cmd_show_config(cfg: _config.Config) -> int:
    print(f"config file : {cfg.path}")
    print(f"prowlarr    : {cfg.prowlarr_url}")
    qbt = cfg.client("qbittorrent")
    sab = cfg.client("sabnzbd")
    print(f"qbittorrent : {qbt['url'] if qbt else '(disabled)'}")
    print(f"sabnzbd     : {sab['url'] + ' [' + sab.get('impl','sabnzbd') + ']' if sab else '(disabled)'}")
    ms = cfg.media_server
    print(f"media server: {ms['type'] + ' ' + ms['url'] if ms else '(disabled)'}")
    print(f"categories  : {', '.join(cfg.categories) or '(none)'}")
    aliases = cfg.tracker_aliases
    print(f"aliases     : {aliases if aliases else '(none — using dynamic discovery)'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Prowlarr and grab to a download client.")
    ap.add_argument("--query", help="Prowlarr query string")
    ap.add_argument("--tracker", help="Tracker name(s)/alias(es) or 'all' (e.g. 'ptp,btn' or 'all')")
    ap.add_argument("--indexers", help="Raw Prowlarr indexer IDs, comma-separated (e.g. 4,6)")
    ap.add_argument("--category", default="movies", help="Category key from config (default: movies)")
    ap.add_argument("--match", help="Case-insensitive substring filter on the release title")
    ap.add_argument("--prefer-protocol", default="torrent", choices=["torrent", "usenet"])
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true", help="Show the chosen release, don't grab")
    ap.add_argument("--no-refresh", action="store_true", help="Skip media-server refresh after grab")
    ap.add_argument("--list-indexers", action="store_true", help="List Prowlarr indexers and exit")
    ap.add_argument("--show-config", action="store_true", help="Print resolved config and exit")
    args = ap.parse_args()

    try:
        cfg = _config.load()
    except _config.ConfigError as e:
        _config.die(str(e))

    if args.show_config:
        return cmd_show_config(cfg)
    if args.list_indexers:
        return cmd_list_indexers(cfg)

    if not args.query:
        _config.die("--query is required (or use --list-indexers / --show-config)")
    if not args.tracker and not args.indexers:
        _config.die("specify --tracker (name/alias/'all') or --indexers (raw IDs)")

    spec = args.indexers or args.tracker
    try:
        indexer_ids = _config.resolve_indexers(cfg, spec)
    except _config.ConfigError as e:
        _config.die(str(e))

    # Validate the category up front so we fail before searching.
    try:
        cat = cfg.category(args.category)
    except _config.ConfigError as e:
        _config.die(str(e))

    try:
        results = search(cfg, args.query, indexer_ids, args.limit)
    except urllib.error.HTTPError as e:
        _config.die(f"Prowlarr search failed: HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        _config.die(f"Could not reach Prowlarr: {e.reason}")

    if not results:
        print(f"NO RESULTS for query={args.query!r} indexers={indexer_ids}", file=sys.stderr)
        return 2

    chosen = pick(results, args.match, args.prefer_protocol)
    if chosen is None:
        print(f"NO MATCH (match={args.match!r}). Top 5 by seeders:", file=sys.stderr)
        for r in sorted(results, key=lambda x: x.get("seeders") or 0, reverse=True)[:5]:
            s = r.get("seeders") if r.get("seeders") is not None else "-"
            print(f"  [{r.get('protocol') or '?':7}] s={s:>4} {r.get('title','')[:100]}", file=sys.stderr)
        return 3

    s = chosen.get("seeders") if chosen.get("seeders") is not None else "-"
    print(f"CHOSEN: [{chosen['protocol']}] s={s} {chosen['title']}")
    if args.dry_run:
        print("(dry-run, not grabbing)")
        return 0

    protocol = chosen["protocol"]
    try:
        if protocol == "torrent":
            client_conf = cfg.client("qbittorrent")
            if not client_conf:
                _config.die("Result is a torrent but [clients.qbittorrent] is disabled.")
            qbt = QbtClient(client_conf)
            qbt.add(fetch_torrent(chosen["downloadUrl"]), cat["save_path"], cat["qbt_category"])
            ref = f"qbittorrent:{cat['qbt_category']}"
        elif protocol == "usenet":
            client_conf = cfg.client("sabnzbd")
            if not client_conf:
                _config.die("Result is usenet but [clients.sabnzbd] is disabled.")
            sab = SabClient(client_conf)
            nzo = sab.addurl(chosen["downloadUrl"], cat["sab_category"])
            ref = f"sabnzbd:{nzo}"
        else:
            _config.die(f"Unknown protocol: {protocol}")
    except urllib.error.HTTPError as e:
        body = e.read()[:500].decode(errors="replace")
        _config.die(f"Grab failed: HTTP {e.code} {e.reason}: {body}")

    print(f"GRABBED: {ref}")
    if protocol == "torrent" and not args.no_refresh:
        refresh_media_server(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
