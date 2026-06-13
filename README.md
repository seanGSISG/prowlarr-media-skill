# prowlarr-media

A portable [Claude Code](https://docs.claude.com/en/docs/claude-code) **skill**
for searching and grabbing media through your own
[Prowlarr](https://prowlarr.com/) instance — across any indexers/trackers you
have configured — and routing releases to qBittorrent (torrents) or
SABnzbd / [RDT-Client](https://github.com/rogerfar/rdt-client) (usenet), with an
optional Jellyfin/Plex library refresh.

- **Zero dependencies.** Pure Python 3.11+ standard library.
- **No hardcoded infrastructure.** Every URL, credential, path, and category
  lives in a `config.toml` you own.
- **Works with anyone's trackers.** Indexers are discovered from Prowlarr at
  runtime; reference them by name (`--tracker ptp`), `all`, or raw ID.

> Tracker-agnostic by design — bring your own Prowlarr and indexers.

## Install

This is a Claude Code skill. Copy the `prowlarr-media/` directory into your
skills folder:

```bash
git clone https://github.com/seanGSISG/prowlarr-media-skill.git
cp -r prowlarr-media-skill/prowlarr-media ~/.claude/skills/prowlarr-media
# (or into a project's .claude/skills/ for project scope)
```

## Configure

```bash
cd ~/.claude/skills/prowlarr-media
cp config.example.toml config.toml      # then edit it
./grab.py --show-config                  # verify it connects
./grab.py --list-indexers                # confirm your trackers are visible
```

At minimum you need the `[prowlarr]` section (url + api_key) and one download
client. Secrets can be supplied via environment variables instead of the file
(`PROWLARR_API_KEY`, `QBT_PASSWORD`, `SAB_API_KEY`, `SAB_PASSWORD`,
`MEDIA_SERVER_TOKEN`) — these override the file values. See
[`docs/configuration.md`](docs/configuration.md) for the full schema.

`config.toml` is gitignored so your secrets are never committed.

## Use

Once installed, just ask Claude Code naturally ("search Prowlarr for …",
"grab the 4K of …"). Under the hood it runs:

```bash
# preview the best match without grabbing
./grab.py --query "Some Movie 2024 2160p" --tracker all --dry-run

# grab a specific encode to the movies category
./grab.py --query "Some Movie 2024 2160p" --tracker all --match remux --category movies

# TV from a specific tracker, into the tv category
./grab.py --query "Some Show S01 1080p" --tracker btn --category tv

# check progress across both clients
./monitor.py --only-active
```

`grab.py` does search **and** grab in one process because Prowlarr's
`downloadUrl` is a one-shot token that expires in seconds — see
[`prowlarr-media/references/prowlarr-internals.md`](prowlarr-media/references/prowlarr-internals.md).

## Requirements

- Python **3.11+** (uses stdlib `tomllib`)
- A reachable Prowlarr instance + API key
- qBittorrent (for torrents) and/or SABnzbd or RDT-Client (for usenet)

## Layout

```
prowlarr-media/            # the skill — copy this into .claude/skills/
├── SKILL.md               # instructions Claude reads
├── config.example.toml    # copy to config.toml and fill in
├── _config.py             # config load + indexer resolution
├── _clients.py            # qBittorrent + SABnzbd/RDT-Client adapters
├── grab.py                # atomic search + grab (CLI)
├── monitor.py             # unified status (CLI)
└── references/            # progressive-disclosure docs
```

## License

MIT — see [LICENSE](LICENSE).
