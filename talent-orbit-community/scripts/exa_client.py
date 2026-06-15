#!/usr/bin/env python3
"""Thin Exa API client for the talent-orbit skill. Stdlib only.

Subcommands: check, search, similar, contents. Run with --help for usage.
Reads EXA_API_KEY from the environment, then .env in CWD, ~/.env, ~/.claude/.env.
When --run-dir is passed, every call is appended to <run-dir>/exa_calls.jsonl and
the budget (graph.json meta.budget, else EXA_BUDGET env, else 80) is enforced.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.exa.ai"
DEFAULT_BUDGET = 80

# Redistributed tool: force UTF-8 stdout so JSON output does not crash on
# Windows consoles that default to a legacy code page (cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def load_key():
    key = os.environ.get("EXA_API_KEY", "").strip()
    if key:
        return key
    candidates = [Path.cwd() / ".env", Path.home() / ".env", Path.home() / ".claude" / ".env"]
    for p in candidates:
        try:
            if not p.is_file():
                continue
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() in ("EXA_API_KEY", "export EXA_API_KEY"):
                    return v.strip().strip('"').strip("'")
        except OSError:
            continue
    return None


def die(msg, code=1):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(code)


def budget_for(run_dir):
    g = Path(run_dir) / "graph.json"
    if g.is_file():
        try:
            b = json.loads(g.read_text(encoding="utf-8")).get("meta", {}).get("budget")
            if isinstance(b, int) and b > 0:
                return b
        except (json.JSONDecodeError, OSError):
            pass
    try:
        return int(os.environ.get("EXA_BUDGET", DEFAULT_BUDGET))
    except ValueError:
        return DEFAULT_BUDGET


def calls_used(run_dir):
    f = Path(run_dir) / "exa_calls.jsonl"
    if not f.is_file():
        return 0
    try:
        return sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def log_call(run_dir, kind, payload, n_results):
    f = Path(run_dir) / "exa_calls.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "query": payload.get("query") or payload.get("url") or payload.get("urls"),
        "n_results": n_results,
    }
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def enforce_budget(run_dir, force):
    if not run_dir:
        return
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    used, budget = calls_used(run_dir), budget_for(run_dir)
    if used >= budget and not force:
        die(f"budget exhausted: {used}/{budget} calls used. Raise meta.budget in graph.json or pass --force.", 2)
    if used >= int(budget * 0.75):
        print(json.dumps({"warning": f"budget {used}/{budget} used"}), file=sys.stderr)


def post(path, payload, key, retries=2):
    body = json.dumps(payload).encode("utf-8")
    last = "unknown error"
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            API + path, data=body, method="POST",
            headers={"x-api-key": key, "Content-Type": "application/json",
                     "User-Agent": "talent-orbit-skill/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="ignore")[:300]
            except OSError:
                pass
            last = f"HTTP {e.code} on {path}: {detail}"
            if e.code in (408, 429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last = f"network error on {path}: {e}"
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
    die(last)


def contents_options(args):
    opts = {}
    if getattr(args, "text", False) or getattr(args, "max_chars", None):
        opts["text"] = {"maxCharacters": args.max_chars} if args.max_chars else True
    if getattr(args, "highlights", None):
        opts["highlights"] = {"query": args.highlights, "numSentences": 3, "highlightsPerUrl": 3}
    if getattr(args, "summary", None):
        opts["summary"] = {"query": args.summary}
    return opts


def slim(results):
    out = []
    for r in results:
        item = {k: r.get(k) for k in ("title", "url", "publishedDate", "author") if r.get(k)}
        if r.get("highlights"):
            item["highlights"] = r["highlights"]
        if r.get("summary"):
            item["summary"] = r["summary"]
        if r.get("text"):
            item["text"] = r["text"]
        out.append(item)
    return out


def emit(kind, payload, data, args):
    results = data.get("results", [])
    if args.run_dir:
        log_call(args.run_dir, kind, payload, len(results))
    out = {"results": slim(results)}
    if data.get("autopromptString"):
        out["autoprompt"] = data["autopromptString"]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_check(args, key):
    if not key:
        die("EXA_API_KEY not found in environment, ./.env, ~/.env, or ~/.claude/.env")
    masked = key[:4] + "…" + key[-4:] if len(key) > 8 else "(short key)"
    if not args.live:
        print(json.dumps({"ok": True, "key": masked, "live": False}))
        return
    data = post("/search", {"query": "test", "numResults": 1, "type": "keyword"}, key)
    print(json.dumps({"ok": True, "key": masked, "live": True, "results": len(data.get("results", []))}))


def cmd_search(args, key):
    payload = {"query": args.query, "type": args.type, "numResults": args.num}
    if args.category:
        payload["category"] = args.category
    if args.include_domains:
        payload["includeDomains"] = [d.strip() for d in args.include_domains.split(",") if d.strip()]
    if args.exclude_domains:
        payload["excludeDomains"] = [d.strip() for d in args.exclude_domains.split(",") if d.strip()]
    if args.start_published:
        payload["startPublishedDate"] = args.start_published
    if args.end_published:
        payload["endPublishedDate"] = args.end_published
    opts = contents_options(args)
    if opts:
        payload["contents"] = opts
    if args.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": "/search", "payload": payload}, indent=2))
        return
    enforce_budget(args.run_dir, args.force)
    emit("search", payload, post("/search", payload, key), args)


def cmd_similar(args, key):
    payload = {"url": args.url, "numResults": args.num,
               "excludeSourceDomain": not args.include_source}
    opts = contents_options(args)
    if opts:
        payload["contents"] = opts
    if args.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": "/findSimilar", "payload": payload}, indent=2))
        return
    enforce_budget(args.run_dir, args.force)
    emit("similar", payload, post("/findSimilar", payload, key), args)


def cmd_contents(args, key):
    payload = {"urls": args.urls}
    opts = contents_options(args)
    payload.update(opts if opts else {"text": True})
    if args.dry_run:
        print(json.dumps({"dry_run": True, "endpoint": "/contents", "payload": payload}, indent=2))
        return
    enforce_budget(args.run_dir, args.force)
    emit("contents", payload, post("/contents", payload, key), args)


def add_common(p):
    p.add_argument("--run-dir", default=None, help="run directory for call logging and budget enforcement")
    p.add_argument("--dry-run", action="store_true", help="print the request payload without sending")
    p.add_argument("--force", action="store_true", help="ignore budget exhaustion")
    p.add_argument("--highlights", default=None, help="ask for highlights focused on this question")
    p.add_argument("--summary", default=None, help="ask for a per-result summary focused on this question")
    p.add_argument("--text", action="store_true", help="return full page text")
    p.add_argument("--max-chars", type=int, default=None, help="cap full text characters per result")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="verify the API key is discoverable (--live spends 1 call)")
    pc.add_argument("--live", action="store_true")

    ps = sub.add_parser("search", help="POST /search")
    ps.add_argument("query")
    ps.add_argument("--type", default="auto", choices=["auto", "neural", "keyword"])
    ps.add_argument("--category", default=None, help='e.g. "linkedin profile", company, news, github')
    ps.add_argument("--num", type=int, default=10)
    ps.add_argument("--include-domains", default=None)
    ps.add_argument("--exclude-domains", default=None)
    ps.add_argument("--start-published", default=None, help="YYYY-MM-DD")
    ps.add_argument("--end-published", default=None, help="YYYY-MM-DD")
    add_common(ps)

    pf = sub.add_parser("similar", help="POST /findSimilar")
    pf.add_argument("url")
    pf.add_argument("--num", type=int, default=10)
    pf.add_argument("--include-source", action="store_true", help="allow results from the source domain")
    add_common(pf)

    pg = sub.add_parser("contents", help="POST /contents for one or more URLs")
    pg.add_argument("urls", nargs="+")
    add_common(pg)

    args = ap.parse_args()
    key = load_key()
    if args.cmd != "check" and not key and not args.dry_run:
        die("EXA_API_KEY not found. Run the check subcommand for search locations.")

    {"check": cmd_check, "search": cmd_search, "similar": cmd_similar, "contents": cmd_contents}[args.cmd](args, key)


if __name__ == "__main__":
    main()
