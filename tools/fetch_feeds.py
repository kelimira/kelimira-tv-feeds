#!/usr/bin/env python3
"""Fetch real Greek-language channel feeds from the public iptv-org index,
probe every stream URL, and write tools/feeds_probed.json for gen_sample_feed.

Sources (data licensed CC BY-NC 4.0, see README):
  https://iptv-org.github.io/iptv/languages/ell.m3u   (Greek-language worldwide)

Usage:
  python3 tools/fetch_feeds.py              # fetch + probe all
  python3 tools/fetch_feeds.py --max 12     # probe only the first N (quick test)
  python3 tools/fetch_feeds.py --probe-only # reuse cached feeds_probed.json, only re-probe
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "feeds_probed.json")
GRTV_OUT = os.path.join(HERE, "grtv_probed.json")
M3U_URLS = [
    "https://iptv-org.github.io/iptv/languages/ell.m3u",
    "https://iptv-org.github.io/iptv/countries/gr.m3u",
    "https://iptv-org.github.io/iptv/countries/cy.m3u",
]
# Secondary source: Greek TV playlist with multiple backup (BUP) streams per
# channel — used to build stream failover alternates and add missing channels.
GRTV_URL = "https://raw.githubusercontent.com/jimgate07/grtv/refs/heads/master/android.m3u"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch_m3u(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def parse_m3u(text, source):
    entries = []
    current = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            current = {"name": "", "tvgId": "", "logo": "", "group": "", "country": "", "language": "", "source": source}
            m = re.search(r'tvg-id="([^"]*)"', line)
            if m: current["tvgId"] = m.group(1)
            m = re.search(r'tvg-logo="([^"]*)"', line)
            if m: current["logo"] = m.group(1)
            m = re.search(r'group-title="([^"]*)"', line)
            if m: current["group"] = m.group(1)
            m = re.search(r'tvg-country="([^"]*)"', line)
            if m: current["country"] = m.group(1)
            m = re.search(r'tvg-language="([^"]*)"', line)
            if m: current["language"] = m.group(1)
            name = re.sub(r"^#EXTINF:[^,]*,", "", line).strip()
            current["name"] = name
        elif line and not line.startswith("#") and current is not None:
            current["url"] = line
            entries.append(current)
            current = None
    return entries


def probe(entry, timeout=8):
    """Classify a stream URL. Returns 'ok' (HLS content served), 'dead'
    (HTTP gone — 404/410/451), 'blocked' (403 — often geo/hotlink), or
    'error' (unreachable/timeout). The nightly GitHub Action runs from a US
    runner, so 'blocked'/'error' must NOT prune streams — they may work for
    viewers in Greece/Europe."""
    try:
        req = urllib.request.Request(
            entry["url"],
            headers={"User-Agent": UA, "Range": "bytes=0-8191", "Accept": "*/*"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(8192)
            status = getattr(r, "status", 200)
            ctype = r.headers.get("Content-Type", "")
        if status in (200, 206) and (
            b"#EXTM3U" in body or b".m3u8" in body or "mpegurl" in ctype.lower()
        ):
            return "ok"
        if status in (404, 410, 451):
            return "dead"
        if status == 403:
            return "blocked"
        return "error"
    except urllib.error.HTTPError as e:
        if e.code in (404, 410, 451):
            return "dead"
        if e.code == 403:
            return "blocked"
        return "error"
    except Exception:
        return "error"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0, help="only probe first N entries (0 = all)")
    ap.add_argument("--probe-only", action="store_true", help="reuse cached m3u parse, only re-probe")
    args = ap.parse_args()

    if args.probe_only and os.path.exists(OUT) and os.path.exists(GRTV_OUT):
        entries = json.load(open(OUT, encoding="utf-8"))
        grtv = json.load(open(GRTV_OUT, encoding="utf-8"))
    else:
        seen = {}
        for url in M3U_URLS:
            print("Fetching", url, file=sys.stderr)
            try:
                for e in parse_m3u(fetch_m3u(url), url):
                    key = (e["name"].lower(), e["url"])
                    seen.setdefault(key, e)
            except Exception as ex:
                print("  fetch failed:", ex, file=sys.stderr)
        entries = list(seen.values())
        print("Parsed %d unique entries" % len(entries), file=sys.stderr)

        # grtv playlist: HLS-only alternates + missing channels
        print("Fetching", GRTV_URL, file=sys.stderr)
        grtv = []
        try:
            for e in parse_m3u(fetch_m3u(GRTV_URL), GRTV_URL):
                if ".m3u8" in e["url"].lower():
                    grtv.append(e)
        except Exception as ex:
            print("  fetch failed:", ex, file=sys.stderr)

    def run_probes(items):
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            statuses = list(pool.map(probe, items))
        for e, st in zip(items, statuses):
            e["status"] = st
            e["ok"] = (st == "ok")

    run_probes(entries[: args.max] if args.max > 0 else entries)
    if args.max == 0:
        print("Probing %d grtv URLs..." % len(grtv), file=sys.stderr)
        run_probes(grtv)

    json.dump(entries, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(grtv, open(GRTV_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    good = sum(1 for e in entries if e.get("ok"))
    good_grtv = sum(1 for e in grtv if e.get("ok"))
    print("Wrote %s — %d/%d working" % (OUT, good, len(entries)), file=sys.stderr)
    print("Wrote %s — %d/%d working" % (GRTV_OUT, good_grtv, len(grtv)), file=sys.stderr)
    print("WORKING:" if args.max == 0 else "PREVIEW (first %d probed):" % args.max)
    for e in entries:
        mark = "OK " if e.get("ok") else "FAIL"
        print("  %s %-40s [%s] %s" % (mark, e["name"][:40], e.get("country", ""), e["url"][:60]))


if __name__ == "__main__":
    main()
