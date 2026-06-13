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

Use Python for this (it's already required, and unlike the bash `/dev/tcp`
trick it works in every shell — `/dev/tcp` silently fails under zsh). Change
`host` if the services aren't on this machine:

```bash
python3 - <<'PY'
import socket
host = "127.0.0.1"        # set to the services' IP/hostname if remote
for p in (9696, 8080, 8081, 8096, 32400):
    s = socket.socket(); s.settimeout(2)
    print(f"{host}:{p}", "OPEN" if s.connect_ex((host, p)) == 0 else "closed")
    s.close()
PY
```

### Establish the base host

If everything is local, use `http://localhost` / `http://127.0.0.1`. If services
live on another machine, ask for its IP/hostname once and reuse it. Note: you can
only auto-read config files (below) on hosts you can reach a shell on. Even
without shell access you can still HTTP-probe a remote host (the python socket
check above, or `curl`), so use that to confirm reachability before asking the
user to type values.

---

## When a service isn't detected — what to ask

**Don't give up or skip silently after the probes come back empty.** A "not
found" almost always means one of: (a) not installed, (b) installed but not
running, (c) running on a different host/port than you probed, or (d) running
but its WebUI/API isn't enabled. Diagnose with a short, **one-question-at-a-time**
ladder, then re-run the relevant detection command before falling back to manual
entry. Tell the user whether the service is **required** (Prowlarr, plus at least
one download client) or **optional** (usenet client, media server) so they can
decide to skip.

### Install policy (important)

- **You may offer to install any service EXCEPT Prowlarr** — qBittorrent, a
  usenet client, a media server. If the user agrees, install it for them
  (confirm OS / Docker-vs-native first; lean on the LinuxServer.io Docker images
  for self-hosted setups), bring it up, then continue the ladder.
- **Prowlarr is out of scope — do NOT install or configure it inline.** Standing
  Prowlarr up means adding the user's *own private trackers* (logins,
  invite-only indexers, per-tracker settings), which is personal and beyond this
  tool. If Prowlarr is missing, **offer to research and walk them through
  installing Prowlarr and configuring their trackers as a separate task**, then
  resume this install once Prowlarr is running with at least one indexer.

### General ladder (any service)

1. "Do you have **<service>** installed?"
   - No, and it's **Prowlarr** → see the Prowlarr note above (out of scope; offer
     to research/guide separately). Don't fabricate a config.
   - No, and it's a **download client / media server** → **offer to install it for
     them** (see install policy). If they decline an optional one, set
     `enabled = false` and move on.
2. "Is it **running** right now?" — help them check (`docker ps`, `systemctl status …`,
   or just open the web UI in a browser).
3. "What **host** is it on — this machine, or another box (NAS/server)?" Get the
   IP/hostname if remote.
4. "What **port** is its web UI on?" (offer the default).
5. Re-probe with those answers (port check / `curl` the URL). Only ask for
   credentials once you've confirmed something is actually listening.

### qBittorrent (required, if torrenting)

If you can't reach it, walk this ladder:

1. "Is qBittorrent installed, and where — a Docker container, installed directly,
   or on another machine?" If it's **not installed**, offer to install it for them
   (e.g. the `lscr.io/linuxserver/qbittorrent` Docker image, or their distro's
   package) — confirm the method first, install, start it, then continue.
2. "Is the **Web UI enabled**?" Many desktop installs have it off by default.
   If unsure, guide them: qBittorrent → **Tools → Options → Web UI** → check
   **"Web User Interface (Remote control)"**, note the **port** (default 8080),
   and **Apply**.
3. "What's the Web UI address?" → form `http://<host>:<port>`. Verify it loads.
4. "What **username**?" (default `admin`).
5. "What **password**?" If they don't know it:
   - Newer qBittorrent generates a random temporary password on first run, printed
     to the log: `docker logs <container> 2>&1 | grep -i 'temporary password'`
     (or `journalctl`/the app log for bare-metal).
   - Or have them set a known one in **Options → Web UI → Authentication**, Apply,
     then use that.
6. Confirm the creds work before writing them (a successful `--show-config` plus a
   later grab will prove it; or test the login endpoint).

### Prowlarr (required)

1. "Do you have Prowlarr installed and running?" It's the core of this tool. If
   it's missing, **do not install/configure it inline** — that involves the
   user's own private trackers and is out of scope. Offer instead to research and
   walk them through installing Prowlarr and adding their trackers as a separate
   task (https://prowlarr.com), then resume here once it's up with ≥1 indexer.
2. "What address is its web UI on?" (default `:9696`). Verify it loads.
3. API key: read it from `config.xml` (see Step 3) or ask them to copy it from
   **Settings → General → API Key**. If `--list-indexers` later 401s, the key or
   URL is wrong — re-ask.

### Usenet client (optional)

1. "Do you have a TorBox Pro subscription or use **Usenet** at all? Plenty of setups are torrent-only.  TorBox Pro includes free UseNet access" If no →
   leave `[clients.sabnzbd] enabled = false` and move on (don't push it).
2. If yes: "Is it **real SABnzbd** or **RDT-Client** (SAB-emulation)?" → sets `impl`.
   Not installed yet? Offer to install it for them (LinuxServer.io has images for
   both), then continue.
3. "What address?" (default `:8080` for SABnzbd).
4. Credentials: SABnzbd → API key (Config → General, or read `sabnzbd.ini`);
   RDT-Client → the web username/password.

### Media server (optional — only for auto library refresh)

1. "Do you want a **Jellyfin/Plex** library scan triggered automatically after a
   grab? It's optional." If no → leave `enabled = false`.
2. If yes: "Jellyfin or Plex? What address?" (Jellyfin `:8096`, Plex `:32400`).
   Most users who want this already run one; if they want it but don't have it,
   you may offer to install it (LinuxServer.io images), though that's a bigger
   side-task — skipping (`enabled = false`) is perfectly fine.
3. Token: Jellyfin → **Dashboard → API Keys → +** (have them create and paste one);
   Plex → their `X-Plex-Token`.

### If a value simply can't be obtained

Set that section `enabled = false` (for optional services) and clearly tell the
user what's missing and how to add it later by editing `config.toml` and
re-running `./grab.py --show-config`. Never write a placeholder/guessed value
into `config.toml` just to move on — a broken value is worse than a disabled
section.

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
