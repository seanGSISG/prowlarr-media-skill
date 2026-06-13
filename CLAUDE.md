# prowlarr-media-skill

<identity>
A Claude Code skill — `prowlarr-media` — that searches a Prowlarr instance and
grabs releases to qBittorrent (torrents) or a usenet client, with optional
media-server library refresh. Tracker-agnostic: indexers and all infra come
from config, not code.
</identity>

<principles>
- **Zero dependencies.** Pure Python 3.11+ stdlib (`tomllib`, `urllib`). Do NOT
  add third-party deps — it would break the copy-and-run install story.
- **No hardcoded infrastructure.** Every URL/credential/path/category lives in
  the user's `config.toml`. Never commit a real `config.toml` (it's gitignored);
  edit `config.example.toml` when the schema changes.
- **Trackers are runtime-discovered.** Never hardcode indexer IDs — resolve via
  `/api/v1/indexer`. See `prowlarr-media/references/indexer-discovery.md`.
- **Search and grab are atomic.** Prowlarr `downloadUrl` is a one-shot token;
  keep them in one process (`grab.py`).
</principles>

## Layout

```
prowlarr-media/            # the skill (users copy into .claude/skills/)
├── SKILL.md               # instructions + workflow
├── config.example.toml    # config schema / template (committed)
├── _config.py             # load/validate config + resolve_indexers()
├── _clients.py            # QbtClient + SabClient adapters
├── grab.py                # CLI: atomic search+grab, --list-indexers, --show-config
├── monitor.py             # CLI: unified status
└── references/            # prowlarr-internals, usenet-sabnzbd, indexer-discovery
docs/configuration.md      # end-user config reference
```

## Commands

Scripts are run from the skill directory (they read `config.toml` from cwd):

```bash
cp config.example.toml config.toml   # then edit
./grab.py --show-config              # verify config resolves (no secrets printed)
./grab.py --list-indexers            # live indexers from the configured Prowlarr
./grab.py --query "Movie 2024 2160p" --tracker all --dry-run    # preview
./grab.py --query "Show S01 1080p" --tracker btn --category tv  # grab
./monitor.py --only-active           # status across both clients
```

## Gotchas

- **Same-dir imports.** `grab.py`/`monitor.py` use `import _config` / `from _clients`.
  They must run from the skill dir (or have it on `sys.path`) — don't symlink a single
  script elsewhere.
- **Schema changes are a 3-file edit.** Any config key change must update
  `config.example.toml`, `_config.py` (parsing/validation + the `_ENV_OVERRIDES` map),
  and `docs/configuration.md` together.
- **Secrets via env.** `PROWLARR_API_KEY`, `QBT_PASSWORD`, `SAB_API_KEY`, `SAB_PASSWORD`,
  `MEDIA_SERVER_TOKEN` override file values (see `_ENV_OVERRIDES` in `_config.py`).

## Testing changes

No unit-test harness yet (stdlib CLI tool). Validate against a live Prowlarr:
`./grab.py --show-config`, `./grab.py --list-indexers`, then a real
`--dry-run` search. Confirm both torrent and usenet routing if both clients
are configured.
