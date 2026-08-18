# Greek Express TV — Feed Catalog

This repository hosts the **updatable channel catalog** for the
[my-greek-tv](https://github.com/kelimira/my-greek-tv) Roku channel.

The channel fetches `channels.json` from GitHub Pages
(`https://kelimira.github.io/kelimira-tv-feeds/channels.json`) on launch, on
the **Ανανέωση** button, and every 6 hours — so editing the file here **updates
the lineup on users' Rokus without redistributing the channel**.

## Updating the lineup

1. Edit `channels.json` (schema in the channel repo: `docs/FEED.md`).
2. Commit and push to `main` — GitHub Pages rebuilds automatically.
3. The channel picks up the change on its next refresh.

## Pushing a message to users

To show a banner on users' screens at startup, set the `message` field:

```json
{
  "feedVersion": 1,
  "updated": "2026-08-18T09:00:00Z",
  "message": "⚠️ Συντήρηση ροών — ορισμένα κανάλια ενδέχεται να μην λειτουργούν προσωρινά.",
  "channels": [ ... ]
}
```

Leave `message` as `""` when there is nothing to announce.

## Regenerating the catalog

The catalog is generated from the public
[iptv-org](https://github.com/iptv-org/iptv) Greek-language index (CC BY-NC 4.0)
by `tools/fetch_feeds.py` + `tools/gen_sample_feed.py` in the channel repo:

```bash
make feeds        # fetch + probe + regenerate feed/channels.json
```

Then copy the result here and push.

> Attribution: channel list data from [iptv-org/iptv](https://github.com/iptv-org/iptv)
> is licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
