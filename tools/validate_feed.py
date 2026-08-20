#!/usr/bin/env python3
"""Validate a channels.json catalog for the Greek Express TV channel.

Usage:
  python3 validate_feed.py [path/to/channels.json]
  python3 validate_feed.py feed/channels.json --probe          # check stream URLs
  python3 validate_feed.py feed/channels.json --probe --max 5  # limit probes

Exit code 0 = valid, 1 = invalid. `--probe` reports each stream's HTTP status.
"""
import argparse
import json
import sys
from datetime import datetime, timezone


def parse_iso(s):
    if not isinstance(s, str) or not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="feed/channels.json")
    ap.add_argument("--probe", action="store_true", help="HTTP-probe stream URLs")
    ap.add_argument("--max", type=int, default=10, help="max probes")
    args = ap.parse_args()

    with open(args.path, encoding="utf-8") as f:
        feed = json.load(f)

    errors = []
    warnings = []

    if not isinstance(feed.get("feedVersion"), int):
        errors.append("feedVersion must be an integer")
    if not isinstance(feed.get("channels"), list) or not feed["channels"]:
        errors.append("channels must be a non-empty array")
    else:
        seen = set()
        for ch in feed["channels"]:
            cid = ch.get("id")
            if not cid:
                errors.append("channel missing 'id'")
            elif cid in seen:
                errors.append("duplicate channel id: " + str(cid))
            seen.add(cid)
            if not ch.get("name"):
                errors.append("channel %s missing 'name'" % cid)
            if not isinstance(ch.get("streams"), list) or not ch["streams"]:
                errors.append("channel %s missing streams" % cid)
            else:
                for s in ch["streams"]:
                    if not s.get("url"):
                        errors.append("channel %s has a stream without 'url'" % cid)
                    elif s["url"].startswith("https://your-stream-provider.example"):
                        warnings.append("channel %s uses a placeholder stream URL" % cid)
            if ch.get("verified") is False:
                warnings.append("channel %s marked unverified" % cid)

    epg = feed.get("epg") or []
    if not isinstance(epg, list):
        errors.append("epg must be an array")
    else:
        for p in epg[:500]:
            if p.get("channelId") not in seen:
                warnings.append("epg entry for unknown channelId: %s" % p.get("channelId"))
            s = parse_iso(p.get("start"))
            e = parse_iso(p.get("end"))
            if s is None:
                errors.append("epg entry has bad start: %s" % p.get("start"))
            if e is None:
                errors.append("epg entry has bad end: %s" % p.get("end"))
            if s is not None and e is not None and e <= s:
                errors.append("epg entry end <= start: %s" % p.get("start"))

    for w in warnings:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)

    if errors:
        print("INVALID — %d error(s)" % len(errors))
        sys.exit(1)

    print("VALID — %d channel(s), %d epg entries" % (len(feed["channels"]), len(epg)))

    if args.probe:
        import urllib.request
        urls = []
        for ch in feed["channels"]:
            for s in ch.get("streams", []):
                u = s.get("url", "")
                if u and not u.startswith("https://your-stream-provider.example"):
                    urls.append((ch["id"], u))
        for cid, u in urls[: args.max]:
            try:
                req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "validate-feed"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    print("OK  %-14s %s %s" % (cid, resp.status, u))
            except Exception as ex:
                print("FAIL %-14s %s (%s)" % (cid, u, ex))


if __name__ == "__main__":
    main()
