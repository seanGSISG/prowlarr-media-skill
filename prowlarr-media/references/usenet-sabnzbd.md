# Usenet routing: SABnzbd & RDT-Client

Read this when: a result has `protocol: "usenet"`, you hit 403s from the usenet
client, or a grabbed usenet file never shows up in the media library.

## Why routing matters

qBittorrent only accepts torrents. A Prowlarr result with `protocol: "usenet"`
has a `downloadUrl` that returns an NZB, which must go to a usenet client.
`grab.py` routes automatically by `protocol`. This skill supports two usenet
backends, selected by `clients.sabnzbd.impl` in `config.toml`:

| impl | Auth | Notes |
|------|------|-------|
| `sabnzbd` | `apikey` query param | Real SABnzbd. Set `api_key`. |
| `rdt-client` | ASP.NET session cookie | RDT-Client's SAB-emulation API. Set `username` + `password`. |

## RDT-Client auth (the 403 trap)

RDT-Client emulates SABnzbd's HTTP API but does **not** honor HTTP basic auth or
the `apikey` param. You must POST `/Api/Authentication/Login` with JSON, get the
`SID` cookie, then reuse that cookie. Without it:

- `mode=version` → 200 (public)
- `mode=queue`, `mode=addurl`, `mode=get_config` → 403

`_clients.py` `SabClient` handles this when `impl = "rdt-client"`.

## Submitting an NZB

After auth, POST `addurl`. The client fetches the NZB server-side, so the
Prowlarr `apikey=` link works even though you can't follow its redirects from
outside:

```
POST /api?mode=addurl&name=<prowlarr_download_url>&cat=<cat>&priority=-100&output=json
→ {"status": true, "nzo_ids": ["..."]}
```

`priority=-100` ("force") is what Sonarr/Radarr send; keep it.

## Categories

Map your config category's `sab_category` to whatever the usenet client knows.
RDT-Client typically only has `sonarr` and `radarr` configured, so:
- `tv`, `cartoons` → `sonarr`
- `movies` → `radarr`
- `music`, `other` → `sonarr` (or add real categories)

## Where usenet files land (important)

With RDT-Client specifically:
1. NZB submitted → uploaded to the debrid/usenet provider
2. Provider fetches from Usenet, returns a download URL
3. RDT-Client downloads the file to its own download dir
4. The file reaches `/data/media/...` **only if Sonarr/Radarr import it**

So for ad-hoc grabs with no Sonarr/Radarr managing the title, the file lands in
the client's download directory, **not** your media library. Tell the user: move
it manually or add the title to Sonarr/Radarr first if they want Jellyfin/Plex
to see it. (Real SABnzbd behaves per its own category/post-processing config.)

## Debugging 403s (RDT-Client)

| Tried | Why it failed |
|-------|---------------|
| `curl -u user:pass .../api?mode=queue` | only checks the ASP.NET cookie, not basic auth |
| `.../api?mode=queue&apikey=x` | apikey unused; auth is cookie-only |
| Following Prowlarr's `/download` redirect yourself | redirect targets need the provider API key; let the client fetch — pass the raw URL to `addurl` |

## Manual queue ops

```
POST /api?mode=queue&name=pause&value=<nzo_id>
POST /api?mode=queue&name=delete&value=<nzo_id>
POST /api?mode=resume
GET  /Api/Torrents      # RDT-Client native, richer fields (rdName/rdProgress/rdStatus)
```

`rdStatus`: 0=queued, 1=downloading, 2=completed, 3=error.
