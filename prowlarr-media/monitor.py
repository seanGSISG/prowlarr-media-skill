#!/usr/bin/env python3
"""Unified download status across qBittorrent and SABnzbd/RDT-Client.

All connection details come from config.toml (see config.example.toml).

Usage:
    monitor.py
    monitor.py --category tv
    monitor.py --only-active
"""

from __future__ import annotations

import argparse
import sys

import _config
from _clients import QbtClient, SabClient


def fmt_size(b: float) -> str:
    return f"{b / (1024 ** 3):>6.2f}GB" if b else "  0.00GB"


def fmt_speed(bps: float) -> str:
    return f"{bps / (1024 ** 2):>5.1f} MB/s" if bps else "    -    "


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", help="qBittorrent/SAB category to filter by")
    ap.add_argument("--only-active", action="store_true", help="Hide completed/seeding")
    args = ap.parse_args()

    try:
        cfg = _config.load()
    except _config.ConfigError as e:
        _config.die(str(e))

    print(f"{'CLIENT':<6} {'PROG':<6} {'SIZE':<9} {'SPEED':<10} {'STATE':<14} TITLE")

    qbt_conf = cfg.client("qbittorrent")
    if qbt_conf:
        try:
            qbt = QbtClient(qbt_conf)
            torrents = qbt.info(category=args.category)
            for t in sorted(torrents, key=lambda x: x["name"]):
                state = t["state"]
                if args.only_active and state in {"uploading", "stalledUP", "pausedUP", "queuedUP"}:
                    continue
                p = t["progress"] * 100
                print(f"qbt    {p:>5.1f}% {fmt_size(t['size'])} {fmt_speed(t['dlspeed'])} "
                      f"{state:<14} {t['name'][:90]}")
        except Exception as e:  # noqa: BLE001
            print(f"qbt    ERROR: {e}", file=sys.stderr)

    sab_conf = cfg.client("sabnzbd")
    if sab_conf:
        try:
            sab = SabClient(sab_conf)
            for t in sab.queue():
                # RDT-Client native shape (rdName/rdProgress/rdStatus) vs SAB slots.
                if "rdName" in t or "rdStatus" in t:
                    name = t.get("rdName") or t.get("hash", "?")[:12]
                    prog = t.get("rdProgress")
                    prog_s = f"{prog:>5.1f}%" if prog is not None else "  ??? "
                    state = {0: "queued", 1: "downloading", 2: "completed", 3: "error"}.get(
                        t.get("rdStatus", 0), str(t.get("rdStatus")))
                    size = t.get("rdSize", 0) or 0
                else:
                    name = t.get("filename", "?")
                    prog_s = f"{float(t.get('percentage', 0)):>5.1f}%"
                    state = t.get("status", "?")
                    size = float(t.get("mb", 0)) * 1024 * 1024
                if args.only_active and state == "completed":
                    continue
                print(f"sab    {prog_s} {fmt_size(size)} {' ' * 9} {state:<14} {name[:90]}")
        except Exception as e:  # noqa: BLE001
            print(f"sab    ERROR: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
