# Configuration reference

All runtime settings live in `config.toml`, next to the scripts (or in
`$XDG_CONFIG_HOME/prowlarr-media/` or `~/.config/prowlarr-media/`). Start from
`config.example.toml`.

## Config file search order

First match wins:

1. `$PROWLARR_MEDIA_CONFIG` — explicit path
2. `./config.toml` — next to the scripts
3. `$XDG_CONFIG_HOME/prowlarr-media/config.toml`
4. `~/.config/prowlarr-media/config.toml`

## Environment-variable overrides (secrets)

Any of these, when set, override the corresponding file value — so you can keep
secrets out of the file entirely:

| Env var | Overrides |
|---------|-----------|
| `PROWLARR_API_KEY` | `prowlarr.api_key` |
| `QBT_PASSWORD` | `clients.qbittorrent.password` |
| `SAB_API_KEY` | `clients.sabnzbd.api_key` |
| `SAB_PASSWORD` | `clients.sabnzbd.password` |
| `MEDIA_SERVER_TOKEN` | `media_server.token` |

## Sections

### `[prowlarr]` (required)

| Key | Required | Description |
|-----|----------|-------------|
| `url` | yes | Base URL, e.g. `http://prowlarr.lan:9696` |
| `api_key` | yes | Prowlarr → Settings → General → API Key |

### `[clients.qbittorrent]`

Handles `protocol == "torrent"`.

| Key | Description |
|-----|-------------|
| `enabled` | `true` to use it |
| `url` | qBittorrent WebUI URL |
| `username` / `password` | WebUI credentials |

### `[clients.sabnzbd]`

Handles `protocol == "usenet"`. Supports real SABnzbd or RDT-Client.

| Key | Description |
|-----|-------------|
| `enabled` | `true` to use it |
| `impl` | `"sabnzbd"` (api_key auth) or `"rdt-client"` (cookie login) |
| `url` | client URL |
| `api_key` | for `impl = "sabnzbd"` |
| `username` / `password` | for `impl = "rdt-client"` |

### `[media_server]` (optional)

Triggers a library refresh after a successful **torrent** grab.

| Key | Description |
|-----|-------------|
| `enabled` | `true` to use it |
| `type` | `"jellyfin"`, `"plex"`, or `"none"` |
| `url` | media server URL |
| `token` | API token |

### `[categories.<name>]`

Define one table per category you use. The category name is what you pass to
`grab.py --category <name>`.

| Key | Description |
|-----|-------------|
| `save_path` | where the download client writes files |
| `qbt_category` | qBittorrent category label (created if missing) |
| `sab_category` | SABnzbd/RDT-Client category |

### `[trackers]` (optional)

Friendly aliases → Prowlarr indexer IDs. Usually unnecessary — `--tracker` does
dynamic name matching by default. Use when a name is ambiguous or you want a
shorthand. Find IDs with `./grab.py --list-indexers`.

```toml
[trackers]
ptp = 6
btn = 5
```

## Verifying

```bash
./grab.py --show-config      # resolved connections (no secrets printed)
./grab.py --list-indexers    # live indexers from your Prowlarr
```
