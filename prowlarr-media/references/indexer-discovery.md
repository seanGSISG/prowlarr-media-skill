# Indexer discovery & `--tracker` resolution

Read this when: `--tracker X` doesn't match what you expect, or you want to
understand how the skill stays portable across different Prowlarr instances.

## Why dynamic

Indexer IDs (`4`, `6`, ...) and names are assigned per Prowlarr instance and
differ for every user. Hardcoding `4 = IPTorrents` would break the moment
someone else installs this skill. So `grab.py` resolves trackers at runtime
against the live `/api/v1/indexer` list.

## How a `--tracker` / `--indexers` spec resolves

Implemented in `_config.resolve_indexers()`. The spec is comma-separated; each
token is resolved independently and de-duplicated:

1. **`all`** → every indexer with `enable: true`.
2. **digits** (`4`) → used as a raw ID, no lookup.
3. **a `[trackers]` alias** (from config) → its mapped ID.
4. **anything else** → case-insensitive **substring** match against live
   indexer `name`s (enabled only). All matches are included.

If a name matches nothing, you get an error listing the available indexer names
plus a hint to run `--list-indexers` or add an alias.

## Inspecting

```bash
./grab.py --list-indexers
# ID   PROTO    EN  NAME
# 4    torrent  y   IPTorrents
# 6    torrent  y   PassThePopcorn
# ...
```

## Aliases (optional)

Only needed when a substring is ambiguous or you want a shorthand. In
`config.toml`:

```toml
[trackers]
ptp = 6
btn = 5
```

Then `--tracker ptp` skips name matching and uses ID 6 directly.

## Caching

`list_indexers()` caches the `/api/v1/indexer` response for the life of the
process, so repeated resolution within one `grab.py` run costs a single HTTP
call.
