---
name: prowlarr-media
description: Search any Prowlarr instance for movies, TV, music, or other media across all configured indexers/trackers, grab releases to qBittorrent (torrents) or SABnzbd/RDT-Client (usenet), and optionally refresh a Jellyfin/Plex library. Use when the user asks to search torrents/usenet, find a movie/show/album, grab a release, "search Prowlarr", or download media via their indexers. Do NOT use for audiobook-specific trackers if a dedicated audiobook tool exists.
---

# Prowlarr Media

Search → grab → (optional) library refresh, against **your** Prowlarr instance.
All connection details live in `config.toml`; nothing is hardcoded.

```
User request
   ↓
Prowlarr  /api/v1/search   (indexers resolved dynamically)
   ↓
protocol == torrent → qBittorrent
protocol == usenet  → SABnzbd / RDT-Client
   ↓
save_path from config → (optional) Jellyfin/Plex refresh
```

## First-time setup

If `config.toml` doesn't exist yet, the scripts print exactly what to do. Setup:

```bash
cp config.example.toml config.toml      # then edit with your values
./grab.py --show-config                  # verify connections resolve
./grab.py --list-indexers                # see your tracker IDs/names
```

Secrets can also come from env vars (`PROWLARR_API_KEY`, `QBT_PASSWORD`,
`SAB_API_KEY`, `SAB_PASSWORD`, `MEDIA_SERVER_TOKEN`) which override the file.

## Workflow

### 1. Choose trackers

You almost never need to know indexer IDs. Pass `--tracker`:

- `--tracker all` — every enabled indexer (good default for "find me X")
- `--tracker ptp` — matches an indexer whose name contains "ptp" (case-insensitive)
- `--tracker ptp,btn` — multiple
- `--indexers 4,6` — raw IDs if you prefer

Run `./grab.py --list-indexers` to see what's available on this instance.

### 2. Search + grab — always use `grab.py` (atomic)

⚠️ **Prowlarr's `downloadUrl` is a one-shot token that expires in seconds.**
Never search in one call and grab in another. `grab.py` does both in one process.

Preview first with `--dry-run`, then grab:

```bash
./grab.py --query "Some Movie 2024 2160p" --tracker all --dry-run
./grab.py --query "Some Movie 2024 2160p" --tracker all --match remux --category movies
```

Key flags:
- `--query` — search string (include year for movies; `S01E01` / `S01` / `complete` for TV)
- `--tracker` / `--indexers` — which indexers (see step 1)
- `--category` — a category key from your config (`movies`, `tv`, ... ). Drives save path + client category.
- `--match SUBSTR` — disambiguate by title substring (e.g. `bluray`, `web-dl`, `remux`, a release group). Highest seeders among matches wins.
- `--prefer-protocol torrent|usenet` — default `torrent`; falls back to the other.
- `--no-refresh` — skip the media-server library refresh.

The script auto-routes by `protocol`: torrents → qBittorrent, usenet → SABnzbd/RDT-Client.

### 3. Monitor

```bash
./monitor.py                 # everything
./monitor.py --category tv   # one category
./monitor.py --only-active   # hide completed/seeding
```

Reports both clients in one table.

## Search strategy

- **Quality first**: try `2160p`, fall back to `1080p` only if no 4K exists.
- TV: episode (`S01E01`) → season pack (`S01`) → series (`complete`).
- Movies: include the year to disambiguate.
- Pre-2010 / SD-only content: native HD may not exist. Don't grab a "1080p DVDRip"
  upscale without flagging it as a DVD-source upscale, not real HD.

## Quality selection (when multiple match)

1. REMUX (untouched BluRay) → 2. BluRay x265/HEVC → 3. BluRay x264 →
4. WEB-DL (AMZN/NF/HMAX > generic) → 5. WEBRip → 6. HDTV → 7. DVDRip (SD only).
Prefer more seeders when quality is comparable.

## Presentation rules

- Show results sorted by seeders desc: Title | Size (GB) | Seeders | Quality | Protocol.
- Recommend the best option (quality × seeders × protocol). Flag usenet results (no seeders).
- Multi-item requests: present the full plan as one table, get one approval, then grab in parallel
  (each `grab.py` call is atomic, so links won't expire across the batch).

## Cross-seeding the same release

If an identical release exists on two trackers, grab one, let it finish, then grab the
other into the **same** `save_path`; the client rechecks to 100% and seeds both. Stage them
sequentially (not simultaneously) so two torrents don't write the same files at once.

## Deeper references

- `references/prowlarr-internals.md` — search endpoint, `indexerIds` repeat rule, one-shot `downloadUrl`, categories, health checks
- `references/usenet-sabnzbd.md` — torrent vs usenet routing, SABnzbd vs RDT-Client auth, where usenet files land
- `references/indexer-discovery.md` — how `--tracker` resolves to IDs

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No config.toml found` | not set up | `cp config.example.toml config.toml` and edit |
| `still has placeholder values` | unedited template | put your real Prowlarr url/api_key in |
| HTTP 400 on search | (handled) indexerIds must be repeated, not comma-joined | already fixed in `grab.py` |
| `Invalid Prowlarr link` | downloadUrl expired between calls | use `grab.py` (atomic) |
| `No enabled indexer matches X` | name didn't match | `--list-indexers`, or add a `[trackers]` alias |
| usenet file not in library | client doesn't move files | see `references/usenet-sabnzbd.md` |
