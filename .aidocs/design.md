# Design notes — prowlarr-media

## Goal

Take the personal, homelab-specific `ipt` skill (in command-center) and produce
a shareable, tracker-agnostic skill that any Claude Code user can drop in and
configure for their own Prowlarr + download clients, without editing code.

## Source → generic mapping

| Original (`ipt`) | Generic (`prowlarr-media`) |
|------------------|-----------------------------|
| Hardcoded `10.10.10.10` URLs, API key, qBT/RDT/Jellyfin creds | `config.toml` (`[prowlarr]`, `[clients.*]`, `[media_server]`) + env overrides |
| Hardcoded indexer IDs (`4=IPT`, `6=PTP`, `5=BTN`, `7=TorBox`) | Dynamic `/api/v1/indexer` discovery; `--tracker name/all`, optional `[trackers]` aliases |
| `CATEGORY_PATHS` dict literal in `grab.py` | `[categories.*]` config tables |
| RDT-Client assumed for all usenet | `clients.sabnzbd.impl = sabnzbd | rdt-client` |
| Duplicate qBT/RDT session code in grab.py + monitor.py | Shared `_clients.py` (`QbtClient`, `SabClient`) |
| Jellyfin token hardcoded; scan inline | Optional `[media_server]`, `refresh_media_server()` (jellyfin/plex) |
| `.secrets.env`, `docker-host-01` SSH, Sonarr DB cred lookup | Removed — not portable |

## Decisions

- **TOML config** via stdlib `tomllib` (3.11+). Keeps zero-dependency promise;
  cleaner than JSON for hand-editing. Documented the 3.11+ requirement.
- **Gitignored `config.toml` + committed `config.example.toml`**, plus per-secret
  env overrides for users who don't want secrets on disk.
- **Dynamic indexer resolution** is the headline portability feature: IDs/names
  differ per instance, so we never bake them in. Aliases are an optional
  convenience, not a requirement.
- **Carried over the `indexerIds`-repeat fix** (Prowlarr returns 400 for
  comma-joined `indexerIds=4,6`; must repeat the param).
- **Atomic search+grab preserved** — the one-shot `downloadUrl` constraint is
  unchanged and is the core reason `grab.py` exists.

## Deliberately out of scope (for now)

- Plugin/marketplace packaging (`plugin.json`) — could come later for `/plugin`
  install UX. Current distribution is copy-the-dir.
- Unit tests — it's a thin stdlib CLI over HTTP APIs; validated against a live
  Prowlarr instead.
- Using Prowlarr's own `release/grab` + registered download clients (would
  remove the manual usenet path) — only viable if the user has RDT-Client wired
  into Prowlarr as a download client; kept the manual path for portability.

## Validation performed

Against the author's live homelab Prowlarr (results recorded in the build
session journal): `--show-config`, `--list-indexers`, and a real `--dry-run`
search confirmed parity with the original `ipt` skill.
