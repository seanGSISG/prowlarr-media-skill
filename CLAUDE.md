# prowlarr-media-skill

<identity>
A portable, shareable Claude Code skill — `prowlarr-media` — that searches any
Prowlarr instance and grabs releases to qBittorrent (torrents) or
SABnzbd/RDT-Client (usenet), with optional Jellyfin/Plex refresh. Generalized
from a personal homelab skill so it works for any user's trackers with no code
edits. Public repo: github.com/seanGSISG/prowlarr-media-skill.
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
.aidocs/design.md          # design notes & provenance
```

## Provenance

Derived from the command-center `ipt` skill (kept untouched). Key generalizations:
hardcoded IPs/keys → `config.toml`; hardcoded indexer IDs → dynamic discovery +
optional aliases; RDT-Client-only usenet → SABnzbd-or-RDT-Client via `impl`;
duplicated session code in grab/monitor → shared `_clients.py`. The
`indexerIds`-repeat fix (Prowlarr 400 on comma-joined IDs) is carried over.

## Testing changes

No unit-test harness yet (stdlib CLI tool). Validate against a live Prowlarr:
`./grab.py --show-config`, `./grab.py --list-indexers`, then a real
`--dry-run` search. Confirm both torrent and usenet routing if both clients
are configured.
