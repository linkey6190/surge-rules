#!/usr/bin/env python3
"""Build rules/AI.list from a list of upstream rule sets.

Deterministic and fail-closed: no model, no manual editing of the output. If a
build would break coverage, grow/shrink suspiciously, or publish an Apple AI
domain, it aborts without touching rules/AI.list, so Surge keeps the last good
copy and the workflow run turns red.
"""
import datetime
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONF = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
OUT = ROOT / "rules" / "AI.list"

KEEP_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}
ORDER = {"DOMAIN": 0, "DOMAIN-SUFFIX": 1, "DOMAIN-KEYWORD": 2}
APPLE_MARKERS = ("icloud.com", "apple-relay", "guzzoni.apple.com", "cp4.cloudflare.com")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "surge-rule-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace").splitlines()


def parse(lines, drop_suffix, drop_keyword, stats):
    rules = []
    for line in lines:
        raw = line.split("#")[0].strip()
        if not raw or "," not in raw:
            continue
        parts = [p.strip() for p in raw.split(",")]
        kind, value = parts[0].upper(), parts[1].lower()
        stats[kind] = stats.get(kind, 0) + 1
        if kind not in KEEP_TYPES:
            continue
        if (value in drop_suffix
                or any(value.endswith("." + s) for s in drop_suffix)
                or any(k in value for k in drop_keyword)):
            stats["dropped"] = stats.get("dropped", 0) + 1
            continue
        rules.append((kind, value))
    return rules


def covers(rules, host):
    host = host.lower()
    for kind, value in rules:
        if kind == "DOMAIN" and host == value:
            return True
        if kind == "DOMAIN-SUFFIX" and (host == value or host.endswith("." + value)):
            return True
        if kind == "DOMAIN-KEYWORD" and value in host:
            return True
    return False


def fail(msg):
    print("BUILD FAILED: " + msg, file=sys.stderr)
    sys.exit(1)


def main():
    drop_suffix = {s.lower() for s in CONF["drop_suffix"]}
    drop_keyword = [s.lower() for s in CONF["drop_keyword"]]

    stats, seen, rules = {}, set(), []
    for url in CONF["sources"]:
        try:
            lines = fetch(url)
        except Exception as exc:  # a dead upstream must not wipe the list
            fail(f"cannot fetch {url}: {exc}")
        for rule in parse(lines, drop_suffix, drop_keyword, stats):
            if rule in seen:
                stats["duplicate"] = stats.get("duplicate", 0) + 1
                continue
            seen.add(rule)
            rules.append(rule)

    rules.sort(key=lambda r: (ORDER[r[0]], r[1]))

    # Gate 1: no Apple AI domain may leak in.
    leaked = [v for _, v in rules if any(m in v for m in APPLE_MARKERS)]
    if leaked:
        fail("Apple AI domains present: " + ", ".join(leaked))

    # Gate 2: every canonical endpoint must be covered.
    missing = []
    for service, hosts in CONF["coverage"].items():
        for host in hosts:
            if not covers(rules, host):
                missing.append(f"{service}/{host}")
    if missing:
        fail("coverage regression: " + ", ".join(missing))

    # Gate 3: reject implausible size jumps against the published list.
    if OUT.exists():
        old = sum(1 for ln in OUT.read_text(encoding="utf-8").splitlines()
                  if ln and not ln.startswith("#"))
        if old:
            delta = (len(rules) - old) / old * 100
            if delta < -CONF["max_shrink_pct"] or delta > CONF["max_growth_pct"]:
                fail(f"rule count moved {delta:+.0f}% ({old} -> {len(rules)})")

    header = [
        f"# NAME: {CONF['name']}",
        f"# DESC: {CONF['description']}",
        f"# BUILT: {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M:%S} UTC",
        f"# TOTAL: {len(rules)}",
    ] + [f"# SRC: {u}" for u in CONF["sources"]]
    body = [f"{kind},{value}" for kind, value in rules]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(header + body) + "\n", encoding="utf-8")

    print(f"wrote {OUT} with {len(rules)} rules "
          f"({len(header) + len(body)} lines); source stats: {stats}")


if __name__ == "__main__":
    main()
