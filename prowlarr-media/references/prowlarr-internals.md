# Prowlarr internals & quirks

Read this when: searches return parse errors, downloadUrls return `Invalid
Prowlarr link`, no results when results were expected, or you need a
category/indexer detail.

## Connection

All requests go to `<prowlarr.url>/api/v1/...` with header `X-Api-Key: <api_key>`
from your `config.toml`. Health check (`[]` = healthy; non-empty = an indexer's
cookies/auth broke):

```bash
curl -s -H "X-Api-Key: $KEY" "$PROWLARR/api/v1/health"
```

## `indexerIds` must be REPEATED, not comma-joined

The single most common 400. Prowlarr's `/api/v1/search` rejects
`indexerIds=4,6` (HTTP 400). You must repeat the parameter:

```
GET /api/v1/search?query=foo&indexerIds=4&indexerIds=6&limit=30
```

`grab.py` builds the query this way. If you hand-roll a curl, do the same.

## `downloadUrl` is a one-shot token

The `downloadUrl` on a search result is NOT stable. Prowlarr keeps the real
tracker URL in memory keyed by an opaque `link=` token that expires within
seconds and is invalidated by:
- a new search clearing the cache slot
- a Prowlarr restart
- a few minutes passing

Failure mode: `{"message":"Invalid Prowlarr link"}`, HTTP 400.

**Always search and grab in the same process.** That's the entire reason
`grab.py` exists. If you must split them (e.g. to present options), preserve
`guid` + `indexerId` + `title`, then re-search and re-match before grabbing —
never reuse a displayed `downloadUrl` across a tool-call boundary.

## Search endpoint fields

```
GET /api/v1/search?query=<text>&indexerIds=<id>&indexerIds=<id>&limit=30
```

Result fields this skill uses:
- `title` — release name
- `size` — bytes
- `seeders` / `leechers` — torrent only; null/0 for usenet
- `protocol` — `"torrent"` | `"usenet"` (KEY for routing)
- `indexerId` — which indexer produced it
- `downloadUrl` — one-shot, see above
- `guid` — stable release identifier

## Indexers

List them (this is what `grab.py --list-indexers` and dynamic `--tracker`
resolution use):

```bash
curl -s -H "X-Api-Key: $KEY" "$PROWLARR/api/v1/indexer" \
  | jq '.[] | {id, name, protocol, enable}'
```

`id` and `name` differ on every Prowlarr instance — that's why this skill
resolves trackers dynamically instead of hardcoding IDs. See
`indexer-discovery.md`.

## Categories (newznab v1 standard)

| Category | ID |  | Category | ID |
|----------|----|--|----------|----|
| Movies (all) | 2000 | | TV (all) | 5000 |
| Movies/HD | 2040 | | TV/HD | 5040 |
| Movies/UHD | 2045 | | TV/UHD | 5045 |
| Music | 3000 | | Games | 4000 |
| Books/Audiobooks | 7000 / 7020 | | | |

Most searches don't need a category — the query disambiguates. Add
`&categories=2000` only for noisy crossover (a movie sharing a TV show's name).

## When to give up on a search

1. Exact title + quality (`Title 2160p`)
2. Title + year, drop quality (`Title 2024`)
3. Title only
4. Add more trackers (`--tracker all`)
5. Try usenet (`--prefer-protocol usenet`) as a last resort

Some content genuinely doesn't exist in 4K. Flag DVD-source upscales rather
than passing them off as native HD.
