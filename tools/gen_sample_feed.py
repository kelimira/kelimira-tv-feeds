#!/usr/bin/env python3
"""Generate feed/channels.json — the bundled catalog.

Preferred source: tools/feeds_probed.json (produced by tools/fetch_feeds.py,
which pulls real Greek-language streams from the public iptv-org index and
probes each URL). Falls back to the built-in curated list below when the
probed file is absent.

The sample EPG is generated relative to "now" so the TV guide shows real
content the moment the channel is sideloaded.
"""
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "feed", "channels.json")
PROBED = os.path.join(HERE, "feeds_probed.json")
GRTV = os.path.join(HERE, "grtv_probed.json")

# ---------------------------------------------------------------------------
# Greek -> Latin transliteration for cross-source channel matching
# ---------------------------------------------------------------------------
GR2LAT = {
    "α": "a", "ά": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "έ": "e",
    "ζ": "z", "η": "i", "ή": "i", "θ": "th", "ι": "i", "ί": "i", "ϊ": "i",
    "ΐ": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o",
    "ό": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y",
    "ύ": "y", "ϋ": "y", "ΰ": "y", "φ": "f", "χ": "ch", "ψ": "ps", "ω": "o",
    "ώ": "o",
}

def normalize_key(name):
    out = []
    for ch in (name or "").lower():
        if ch in GR2LAT:
            out.append(GR2LAT[ch])
        elif ch.isalnum():
            out.append(ch)
    key = "".join(out)
    for suf in ("hd", "bup", "tv", "channel", "cy", "international"):
        while key.endswith(suf) and len(key) > len(suf) + 1:
            key = key[: -len(suf)]
    return key

def keys_match(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
        return True
    return False

def grtv_display_name(name):
    n = re.sub(r"\s*\([^)]*\)", "", name)
    for suf in ("BUP", "HD", "CY", "O"):
        n = re.sub(r"\s+" + suf + r"\b", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s+", " ", n).strip()
    return n or name

def grtv_category(group):
    g = (group or "").lower()
    if any(k in g for k in ("ειδήσε", "news")):
        return "news"
    if any(k in g for k in ("αθλητ", "sport")):
        return "sports"
    if any(k in g for k in ("μουσικ", "music")):
        return "music"
    if any(k in g for k in ("παιδικ", "kids")):
        return "kids"
    if any(k in g for k in ("θρησκευτ", "ekklhsia", "church", "ορθοδοξ")):
        return "general"
    if any(k in g for k in ("διεθν", "international")):
        return "international"
    if any(k in g for k in ("κυπρ", "cyprus")):
        return "general"
    if any(k in g for k in ("τοπικ", "regional")):
        return "regional"
    return "general"

def grtv_country(name, group):
    n = name.lower()
    if "montreal" in n or "canada" in n:
        return "Καναδάς"
    if "hellenic tv" in n or "australia" in n:
        return "Αυστραλία"
    if "cy" in n or "cyprus" in (group or "").lower():
        return "Κύπρος"
    return "Ελλάδα"

# Streams we should not redistribute (adult / betting / trademarked content).
BLOCKLIST = ["extacy", "erotic", "pame stoxima", "opap", "baby shark",
             "mr bean", "duck tv", "f1 video", "adult", "xxx"]

# Catch-up (VOD) entries: kind="vod" with direct replay streams. Add entries
# here (or in the hosted feed repo) as you source legal replay links, e.g.
# from ERTFLIX/RIK. Placeholder structure:
#   { "id": "ertnews-replay", "name": "...", "url": "...", "format": "hls" }
CATCHUP = []

# ---------------------------------------------------------------------------
# Fallback curated list (used only when feeds_probed.json is missing):
#   id, name, country, geo, category, stream url, verified
# ---------------------------------------------------------------------------
ERT_CDN = "https://ert-live-gr-bcbs15228.simplecdn.net/ertlive/{id}_720p/index.m3u8"

FALLBACK_CHANNELS = [
    ("ert1", "ΕΡΤ1", "Ελλάδα", "world", "general", ERT_CDN.format(id="ert1"), False),
    ("ert2", "ΕΡΤ2", "Ελλάδα", "world", "culture", ERT_CDN.format(id="ert2"), False),
    ("ertnews", "ΕΡΤ News", "Ελλάδα", "world", "news", ERT_CDN.format(id="ertnews"), False),
    ("ertworld", "ΕΡΤ World", "Ελλάδα", "world", "international", ERT_CDN.format(id="ertworld"), False),
    ("rik1", "ΡΙΚ 1", "Κύπρος", "world", "general", "https://your-stream-provider.example/rik1/index.m3u8", False),
    ("ant1", "ΑΝΤ1", "Ελλάδα", "gr", "entertainment", "https://your-stream-provider.example/ant1/index.m3u8", False),
    ("mega", "MEGA", "Ελλάδα", "gr", "entertainment", "https://your-stream-provider.example/mega/index.m3u8", False),
    ("alpha", "ALPHA", "Ελλάδα", "gr", "general", "https://your-stream-provider.example/alpha/index.m3u8", False),
    ("star", "STAR", "Ελλάδα", "gr", "entertainment", "https://your-stream-provider.example/star/index.m3u8", False),
    ("skai", "ΣΚΑΪ", "Ελλάδα", "gr", "news", "https://your-stream-provider.example/skai/index.m3u8", False),
    ("mad", "MAD TV", "Ελλάδα", "gr", "music", "https://your-stream-provider.example/mad/index.m3u8", False),
    ("hellenictv", "Hellenic TV", "Αυστραλία", "world", "international", "https://your-stream-provider.example/hellenictv/index.m3u8", False),
]

# Working live radio stations (probed 2026-08): audio streams, kind=radio.
RADIO_STATIONS = [
    ("ert-kosmos", "ERT Kosmos", "https://radiostreaming.ert.gr/ert-kosmos", "mp3"),
    ("ert-voiceofgreece", "ΕΡΤ Φωνή της Ελλάδας", "https://radiostreaming.ert.gr/ert-voiceofgreece", "mp3"),
    ("era-komotini", "ΕΡΑ Κομοτηνής", "https://radiostreaming.ert.gr/ert-komotini", "mp3"),
    ("era-heraklio", "ΕΡΑ Ηρακλείου", "https://radiostreaming.ert.gr/ert-heraklio", "mp3"),
    ("era-larisa", "ΕΡΑ Λάρισας", "https://radiostreaming.ert.gr/ert-larisa", "mp3"),
    ("era-zakynthos", "ΕΡΑ Ζακύνθου", "https://radiostreaming.ert.gr/ert-zakynthos", "mp3"),
    ("era-volos", "ΕΡΑ Βόλου", "https://radiostreaming.ert.gr/ert-volos", "mp3"),
    ("era-serres", "ΕΡΑ Σερρών", "https://radiostreaming.ert.gr/ert-serres", "mp3"),
    ("enlefko-877", "En Lefko 87.7", "https://stream.radiojar.com/enlefko877", "aac"),
]

CATEGORY_GREEK = {
    "general": "γενικού περιεχομένου",
    "news": "ειδησεογραφικό",
    "entertainment": "ψυχαγωγικό",
    "sports": "αθλητικό",
    "music": "μουσικό",
    "culture": "πολιτιστικό",
    "kids": "παιδικό",
    "regional": "περιφερειακό",
    "international": "της ελληνικής διασποράς",
}

GROUP_TO_CATEGORY = {
    "general": "general",
    "news": "news",
    "sports": "sports",
    "music": "music",
    "kids": "kids",
    "entertainment": "entertainment",
    "movies": "entertainment",
    "cinema": "entertainment",
    "culture": "culture",
    "documentary": "culture",
    "religious": "general",
    "legislative": "general",
    "business": "news",
    "shop": "general",
    "travel": "general",
    "undefined": "general",
}


def slugify(name, idx):
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if c.isascii() and (c.isalnum() or c in "-_ ")).strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = "channel"
    return (s + "-" + str(idx)) if s in {"channel"} else s


def clean_name(name):
    """Strip iptv-org annotations like '(1080p)', '[Not 24/7]'."""
    n = re.sub(r"\s*\[[^\]]*\]", "", name)
    n = re.sub(r"\s*\([^)]*\)", "", n)
    return n.strip()


def build_from_probed():
    entries = json.load(open(PROBED, encoding="utf-8"))
    # Greek-language list only (the ell.m3u source is Greek by definition)
    ok = [e for e in entries if e.get("ok") and e["source"].endswith("ell.m3u")]
    ok.sort(key=lambda e: e["name"].lower())

    seen = set()
    channels = []
    for e in ok:
        name = clean_name(e["name"])
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        group = (e.get("group") or "Undefined").split(";")[0].strip().lower()
        category = GROUP_TO_CATEGORY.get(group, "general")

        cid = None
        if e.get("tvgId"):
            cid = slugify(e["tvgId"], len(channels))
        if not cid:
            cid = slugify(name, len(channels))

        country = e.get("country") or ""
        country_gr = {"GR": "Ελλάδα", "CY": "Κύπρος", "CA": "Καναδάς", "AU": "Αυστραλία", "US": "ΗΠΑ"}.get(country, country)
        geo = "gr" if country == "GR" else "world"

        logo = e.get("logo") or ""
        if not logo.startswith("http"):
            logo = "pkg:/images/placeholder_channel.png"

        desc = "Ζωντανή μετάδοση — «%s», κανάλι %s." % (name, CATEGORY_GREEK.get(category, "γενικού περιεχομένου"))
        if country_gr:
            desc += " Χώρα: %s." % country_gr

        channels.append({
            "id": cid,
            "name": name,
            "country": country_gr,
            "geo": geo,
            "category": category,
            "language": "el",
            "kind": "tv",
            "live": True,
            "description": desc,
            "logo": logo,
            "streams": [
                {"url": e["url"], "format": "hls", "quality": "auto", "verified": True}
            ],
        })

    # Live Greek radio stations (audio-only)
    for cid, name, url, fmt in RADIO_STATIONS:
        channels.append({
            "id": cid,
            "name": name,
            "country": "Ελλάδα",
            "geo": "world",
            "category": "music",
            "language": "el",
            "kind": "radio",
            "live": True,
            "description": "Ζωντανό ελληνικό ραδιόφωνο — «%s»." % name,
            "logo": "pkg:/images/placeholder_channel.png",
            "streams": [{"url": url, "format": fmt, "quality": "auto", "verified": True}],
        })

    # Merge grtv alternate streams (failover) + add missing channels
    if os.path.exists(GRTV):
        channels = merge_grtv(channels)

    # Catch-up (VOD) entries
    for c in CATCHUP:
        channels.append({
            "id": c["id"],
            "name": c["name"],
            "country": "Ελλάδα",
            "geo": "world",
            "category": "catchup",
            "language": "el",
            "kind": "vod",
            "live": False,
            "description": c.get("description", "Επιστροφή στο πρόγραμμα — «%s»." % c["name"]),
            "logo": c.get("logo", "pkg:/images/placeholder_channel.png"),
            "streams": [{"url": c["url"], "format": c.get("format", "hls"), "quality": "auto", "verified": c.get("verified", False)}],
        })

    return channels


def merge_grtv(channels):
    """Append grtv working HLS URLs as alternate streams on matching channels
    (failover), and add non-blocked channels we don't have yet (capped)."""
    import json as _json
    grtv = _json.load(open(GRTV, encoding="utf-8"))
    ok = [e for e in grtv if e.get("ok")]

    by_key = {}
    for ch in channels:
        by_key.setdefault(normalize_key(ch.get("name", "")), []).append(ch)

    new_count = 0
    for e in ok:
        name = e.get("name") or ""
        if any(b in name.lower() for b in BLOCKLIST):
            continue
        url = e.get("url", "")
        if not url:
            continue
        key = normalize_key(e.get("tvgName") or name)

        target = None
        for k, lst in by_key.items():
            if keys_match(key, k):
                target = lst[0]
                break
        if target is not None:
            # failover: append as alternate stream (dedupe, cap 4)
            urls = [s["url"] for s in target["streams"]]
            if url not in urls and len(urls) < 4:
                target["streams"].append({"url": url, "format": "hls", "quality": "auto", "verified": True})
        else:
            if new_count >= 50:
                continue
            display = grtv_display_name(name)
            dk = normalize_key(display)
            cid = slugify(dk, len(channels) + new_count)
            if cid in [c["id"] for c in channels]:
                cid = cid + "-" + str(new_count)
            group = e.get("group") or ""
            cat = grtv_category(group)
            country = grtv_country(name, group)
            channels.append({
                "id": cid,
                "name": display,
                "country": country,
                "geo": "world",
                "category": cat,
                "language": "el",
                "kind": "tv",
                "live": True,
                "description": "Ζωντανή μετάδοση — «%s»." % display,
                "logo": e.get("logo") or "pkg:/images/placeholder_channel.png",
                "streams": [{"url": url, "format": "hls", "quality": "auto", "verified": True}],
            })
            by_key.setdefault(dk, []).append(channels[-1])
            new_count += 1
    print("grtv merge: %d alternates appended, %d new channels" % (
        sum(1 for ch in channels if len(ch["streams"]) > 1) - sum(1 for ch in channels[:0]), new_count))
    return channels


def build_fallback():
    channels = []
    for cid, name, country, geo, category, url, verified in FALLBACK_CHANNELS:
        channels.append({
            "id": cid,
            "name": name,
            "country": country,
            "geo": geo,
            "category": category,
            "language": "el",
            "live": True,
            "description": "Ζωντανή μετάδοση — «%s»." % name,
            "logo": "pkg:/images/logos/" + cid + ".png",
            "streams": [{"url": url, "format": "hls", "quality": "720p", "verified": verified}],
        })
    return channels


# program pools per category: (title, description)
POOLS = {
    "news": [
        ("Καλημέρα Ελλάδα", "Πρωινή ενημερωτική εκπομπή με νέα, πολιτική και συνεντεύξεις."),
        ("Μεσημβρινό Δελτίο Ειδήσεων", "Οι κυριότερες εξελίξεις της ημέρας."),
        ("Κεντρικό Δελτίο Ειδήσεων", "Το βραδινό δελτίο ειδήσεων με αναλυτική κάλυψη."),
        ("Νυχτερινό Δελτίο", "Τελευταία ενημέρωση της ημέρας."),
        ("Επικαιρότητα", "Ανασκόπηση των γεγονότων της εβδομάδας."),
    ],
    "general": [
        ("Πρωινό Στούντιο", "Πρωινή ψυχαγωγική εκπομπή με καλεσμένους."),
        ("Μεσημεριανή Ζώνη", "Ελαφρύ μεσημεριανό πρόγραμμα."),
        ("Κεντρική Ζώνη", "Βραδινό πρόγραμμα με σειρές και εκπομπές."),
        ("Νυχτερινό Πρόγραμμα", "Ύστερο βραδινό πρόγραμμα."),
    ],
    "entertainment": [
        ("Σειρά — Δραματική", "Ελληνική δραματική σειρά."),
        ("Τηλεπαιχνίδι", "Διαγωνιστικό τηλεπαιχνίδι με έπαθλα."),
        ("Ψυχαγωγική Εκπομπή", "Βραδινή ψυχαγωγία με μουσική και χιούμορ."),
        ("Ριάλιτι", "Ρεάλιτι με καθημερινή παρακολούθηση."),
    ],
    "sports": [
        ("Αθλητικό Δελτίο", "Τα αποτελέσματα και οι ειδήσεις του αθλητισμού."),
        ("Ποδόσφαιρο — Αγώνας", "Ζωντανή μετάδοση ποδοσφαιρικού αγώνα."),
        ("Μπάσκετ — Αγώνας", "Ζωντανή μετάδοση αγώνα μπάσκετ."),
        ("Αθλητικό Μαγκαζίνο", "Αφιερώματα και αναλύσεις."),
    ],
    "music": [
        ("Ελληνικά Τραγούδια", "Οι μεγαλύτερες ελληνικές επιτυχίες."),
        ("Live Συναυλία", "Συναυλία με Έλληνες καλλιτέχνες."),
        ("Top 20", "Το ελληνικό top 20 της εβδομάδας."),
        ("Ρεμπέτικα & Λαϊκά", "Κλασικό ελληνικό ρεπερτόριο."),
    ],
    "culture": [
        ("Ντοκιμαντέρ", "Ντοκιμαντέρ για την Ελλάδα και τον πολιτισμό της."),
        ("Ταινία — Κλασική", "Κλασική ελληνική ταινία."),
        ("Θέατρο", "Θεατρική παράσταση από ελληνική σκηνή."),
        ("Μουσική Βραδιά", "Πολιτιστική μουσική εκπομπή."),
    ],
    "kids": [
        ("Παιδικά Κινούμενα", "Παιδικά κινούμενα σχέδια."),
        ("Πρωινό Παιδικό", "Πρωινό πρόγραμμα για παιδιά."),
    ],
    "regional": [
        ("Τοπικά Νέα", "Τα νέα της περιοχής."),
        ("Εκπομπή Περιφέρειας", "Θέματα και πρόσωπα της περιφέρειας."),
    ],
    "international": [
        ("Ελληνικά Νέα του Εξωτερικού", "Ενημέρωση για τους Έλληνες του εξωτερικού."),
        ("Ντοκιμαντέρ Ελλάδας", "Η Ελλάδα μέσα από ντοκιμαντέρ."),
        ("Ελληνική Κοινότητα", "Η ζωή των ελληνικών κοινοτήτων ανά τον κόσμο."),
    ],
}

DURATIONS = [1, 2, 1, 1, 2]  # hours per program block, cycled


def make_epg(now_utc, channels):
    floor = now_utc.replace(minute=0, second=0, microsecond=0)
    start = floor - timedelta(hours=1)
    end = floor + timedelta(hours=7)
    epg = []
    for ch in channels:
        if ch.get("kind") == "radio":
            continue  # radio has no scheduled programs
        pool = POOLS.get(ch["category"], POOLS["general"])
        t = start
        di = 0
        while t < end:
            dur = DURATIONS[di % len(DURATIONS)]
            e = t + timedelta(hours=dur)
            title, desc = pool[di % len(pool)]
            epg.append({
                "channelId": ch["id"],
                "start": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": e.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "title": title,
                "description": desc,
            })
            t = e
            di += 1
    return epg


def main():
    now = datetime.now(timezone.utc)
    if os.path.exists(PROBED):
        channels = build_from_probed()
        channels = retain_previous(channels)
        note = "Catalog from probed iptv-org + grtv feeds (see tools/fetch_feeds.py). Streams verified at build time; the nightly GitHub Action refreshes automatically."
    else:
        channels = build_fallback()
        note = "Fallback curated catalog. Run tools/fetch_feeds.py to populate real feeds."

    feed = {
        "feedVersion": 3,   # v3: multi-stream failover + kind=vod catch-up
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": note,
        "message": "",
        "channels": channels,
        "epg": make_epg(now, channels),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
    print("Wrote", os.path.abspath(OUT), "with", len(channels), "channels")


def retain_previous(channels):
    """Keep channels from the previously deployed catalog that the probe
    couldn't re-verify (geo-blocked from a US runner, etc.) — the bot must
    never silently remove channels a viewer was watching."""
    prev_path = os.path.join(HERE, "..", "feed", "channels.json")
    if not os.path.exists(prev_path):
        return channels
    try:
        with open(prev_path, encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        return channels
    ids = set(c["id"] for c in channels)
    kept = 0
    for pc in prev.get("channels", []):
        if pc.get("id") in ids:
            continue
        pc = dict(pc)
        streams = []
        for s in pc.get("streams", []):
            s = dict(s)
            s["verified"] = False
            streams.append(s)
        pc["streams"] = streams
        channels.append(pc)
        kept += 1
    if kept:
        print("retained %d previously-listed channel(s) the runner could not verify" % kept)
    return channels


if __name__ == "__main__":
    main()
