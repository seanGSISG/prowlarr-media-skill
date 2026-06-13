# prowlarr-media — guided install (read this as Claude Code)

**You are Claude Code. A user has pointed you at this document and asked you to
install and configure the `prowlarr-media` skill for them.** This file is your
runbook. Drive the whole process: run the commands yourself, inspect the user's
system to auto-fill values, ask the user only for what you genuinely can't
discover, and validate as you go.

The end state: the `prowlarr-media` skill is installed in the user's Claude Code
skills directory with a working `config.toml`, verified against their live
Prowlarr and download client(s).

---

## Operating principles (follow these the whole way)

1. **One thing at a time.** Ask a single question, wait, act, confirm. Never
   dump the whole questionnaire at once.
2. **Discover before asking.** For every value, first try to find it on the
   user's machine (see the detection recipes). Only ask when discovery fails or
   needs confirmation. When you auto-discover something, show it and ask the
   user to confirm rather than asking them to type it.
3. **Never invent values.** No guessed IPs, ports, keys, or paths. If unknown,
   ask.
4. **Secrets go in `config.toml`** (which is gitignored), never in
   `config.example.toml`. Don't echo full secrets back in chat — confirm with a
   masked value (e.g. `abc…789`).
5. **Validate after each major section** so failures surface early, next to the
   value that caused them.
6. **Respect the host boundary.** You can auto-read config files only for
   services reachable from where you're running (localhost, local Docker, or a
   host you can SSH to). For services on a NAS/other box you can't reach, ask the
   user to paste the values.

---

## Step 1 — Get the files onto the user's machine

This is always first: right now you only have this document, not the code.

1. Confirm `git` and `python3 --version` (need **3.11+** for stdlib `tomllib`).
   - No git? Tell the user to install it, or download the repo zip from
     `https://github.com/seanGSISG/prowlarr-media-skill/archive/refs/heads/main.zip`
     and unzip it, then continue.
2. Clone into a working location (ask if they have a preference; default below):
   ```bash
   git clone https://github.com/seanGSISG/prowlarr-media-skill.git ~/prowlarr-media-skill
   ```
3. Decide the skill install scope and copy the skill folder there:
   - **User scope** (available in every project): `~/.claude/skills/`
   - **Project scope** (one repo only): `<that project>/.claude/skills/`
   ```bash
   mkdir -p ~/.claude/skills
   cp -r ~/prowlarr-media-skill/prowlarr-media ~/.claude/skills/prowlarr-media
   ```
4. From now on, **work inside the installed skill dir** — the scripts use
   same-directory imports and read `config.toml` from the current directory:
   ```bash
   cd ~/.claude/skills/prowlarr-media
   cp config.example.toml config.toml
   ```

You'll edit `config.toml` in place through the next steps.

---

## Step 2 — Discover the user's services

Goal: find Prowlarr (required), a torrent client (qBittorrent), optionally a
usenet client and a media server. Run these probes, then summarize what you
found before configuring anything.

### Find running services (Docker)

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' \
  | grep -iE 'prowlarr|qbit|sabnzbd|rdt|jellyfin|plex|sonarr|radarr' || true
```

The `Ports` column gives you host ports. If Docker isn't installed or returns
nothing, the services may be bare-metal or on another host — ask the user where
they run (and for an IP/hostname if not local).

### Quick port check (bare-metal or to confirm)

Default ports: Prowlarr `9696`, qBittorrent `8080`/`8081`, SABnzbd `8080`,
Jellyfin `8096`, Plex `32400`.

```bash
for p in 9696 8080 8081 8096 32400; do
  (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null && echo "open: $p" && exec 3>&- || true
done
```

### Establish the base host

If everything is local, use `http://localhost` / `http://127.0.0.1`. If services
live on another machine, ask for its IP/hostname once and reuse it. Note: you can
only auto-read config files (below) on hosts you can reach a shell on.

---

## Step 3 — Prowlarr (required) and prove the connection

### Get the URL
From Docker ports or the port check (e.g. `http://localhost:9696`). Confirm with
the user.

### Get the API key — try to read it, don't ask
Prowlarr stores it in `config.xml` as `<ApiKey>...</ApiKey>`.

- **Docker:**
  ```bash
  docker exec <prowlarr_container> cat /config/config.xml | grep -oP '(?<=<ApiKey>)[^<]+'
  ```
- **Bare-metal (try these paths):**
  ```bash
  for f in ~/.config/Prowlarr/config.xml /var/lib/prowlarr/config.xml \
           /opt/Prowlarr/config.xml /config/config.xml; do
    [ -f "$f" ] && grep -oP '(?<=<ApiKey>)[^<]+' "$f"
  done
  ```
- **Fallback:** ask the user to copy it from Prowlarr → Settings → General →
  API Key.

Write `[prowlarr] url` and `api_key` into `config.toml`.

### Prove it immediately
```bash
./grab.py --show-config      # should print the resolved Prowlarr URL, no errors
./grab.py --list-indexers    # MUST list their indexers — this validates the key
```
Show the user the indexer list. This both confirms the connection **and** tells
you exactly which trackers they have. Offer to add friendly `[trackers]` aliases
for the ones they'll use often (e.g. map a long name to `ptp`). Aliases are
optional — `--tracker <name>` already substring-matches these names.

If `--list-indexers` fails, fix the URL/key before continuing.

---

## Step 4 — Download clients

### qBittorrent (torrents)
- **URL:** from Docker ports / port check (commonly `:8080`). Confirm.
- **Username:** default `admin`. Confirm.
- **Password:** you usually can't read this (qBittorrent hashes it in
  `qBittorrent.conf`). Two options:
  - Newer qBittorrent prints a temporary password in its log on first run:
    ```bash
    docker logs <qbit_container> 2>&1 | grep -i 'temporary password' | tail -1
    ```
  - Otherwise ask the user (offer: WebUI → Tools → Options → Web UI to set/see it).
- Set `[clients.qbittorrent] enabled = true` and fill `url`/`username`/`password`.

### Usenet client (optional — ask if they use one)
Set `[clients.sabnzbd] enabled = true` only if they do. Pick `impl`:
- **`sabnzbd`** (real SABnzbd): get the API key from `sabnzbd.ini`:
  ```bash
  docker exec <sab_container> cat /config/sabnzbd.ini | grep -oP '(?<=^api_key = ).*'
  # bare-metal: grep it from ~/.sabnzbd/sabnzbd.ini or the configured path
  ```
  Fill `url` + `api_key`.
- **`rdt-client`** (RDT-Client SAB-emulation): needs `username`/`password` (cookie
  login, not api key). Ask the user for the RDT-Client web creds. Fill
  `url` + `username` + `password`.

If they don't use usenet, leave the section `enabled = false`.

### Media server (optional — for auto library refresh after a grab)
- **Jellyfin:** `type = "jellyfin"`, `url` (commonly `:8096`). The `token` is an
  API key the user creates: Jellyfin → Dashboard → API Keys → +. Walk them through
  it and have them paste it.
- **Plex:** `type = "plex"`, `url` (`:32400`), `token` = their X-Plex-Token.
- Don't use it? Leave `enabled = false`.

---

## Step 5 — Categories (save paths)

Each `[categories.<name>]` maps a category to a `save_path` (where the client
writes files) plus per-client category labels. Get the real paths instead of
guessing:

- **qBittorrent default save path** (after the client is configured you can ask
  the user, or read it): WebUI → Options → Downloads → Default Save Path.
- **If they run Sonarr/Radarr**, their root folders are the right `save_path`s
  for `tv`/`movies`.
- Map `sab_category` to whatever their usenet client knows (RDT-Client typically
  only has `sonarr`/`radarr`).

Keep the example's `movies`/`tv` (and `music`/`other` if useful), but replace the
`save_path` values with the user's real ones. Confirm each path exists / is
writable by the download client.

---

## Step 6 — Final validation

Run, from the skill dir:

```bash
./grab.py --show-config        # all enabled services resolve, no placeholders
./grab.py --list-indexers      # trackers listed
./grab.py --query "<a movie or show you know exists>" --tracker all --dry-run
./monitor.py                   # shows current client activity (or empty table)
```

The `--dry-run` should print a `CHOSEN:` line. If it does, the install works
end to end. (Don't actually grab anything unless the user asks.)

---

## Step 7 — Hand off

Tell the user it's ready and how to use it — they just talk to Claude Code
naturally now ("search Prowlarr for …", "grab the 4K of …"), or run the CLI:

```bash
cd ~/.claude/skills/prowlarr-media
./grab.py --query "Some Movie 2024 2160p" --tracker all --dry-run
./grab.py --query "Some Movie 2024 2160p" --tracker all --match remux --category movies
./monitor.py --only-active
```

Point them at `docs/configuration.md` (in the clone) for the full config schema,
and `prowlarr-media/references/` for Prowlarr/usenet internals.

---

## Detection cheat-sheet (quick reference)

| Need | Try first | Fallback |
|------|-----------|----------|
| What's running | `docker ps` filtered by name | port check on defaults; ask user |
| Prowlarr API key | `<ApiKey>` in `config.xml` (docker exec / file grep) | Prowlarr → Settings → General |
| qBittorrent password | `docker logs` → "temporary password" | ask user (WebUI → Options → Web UI) |
| SABnzbd API key | `api_key` in `sabnzbd.ini` | SABnzbd → Config → General |
| Jellyfin token | — | user creates one: Dashboard → API Keys |
| Save paths | qBittorrent default save path / *arr root folders | ask user |

## Gotchas to remember

- Run all `./grab.py` / `./monitor.py` commands **from the skill directory** —
  they import sibling modules and read `config.toml` from cwd.
- Prowlarr indexer IDs differ per instance; `--tracker` resolves names
  dynamically, so you never hardcode IDs.
- If a value is a secret and the user would rather not store it on disk, it can
  go in an env var instead (`PROWLARR_API_KEY`, `QBT_PASSWORD`, `SAB_API_KEY`,
  `SAB_PASSWORD`, `MEDIA_SERVER_TOKEN`) — these override the file.
