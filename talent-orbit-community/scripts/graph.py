#!/usr/bin/env python3
"""Persistent evidence graph for the talent-orbit skill. Stdlib only.

graph.json is the source of truth for a run. This CLI validates provenance on
every write, computes ring stats and concentration, and exports a Mermaid orbit
diagram. Run with --help, or see references/graph-schema.md for the schema.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Redistributed tool: force UTF-8 stdout so diagrams and summaries do not crash
# on Windows consoles that default to a legacy code page (cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

THRESHOLDS = {"relevance_stop": 0.30, "novelty_stop": 0.20, "max_rings": 3,
              "concentration_flag": 0.60, "min_calibration_n": 4}


def die(msg, code=1):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(code)


def gpath(run_dir):
    return Path(run_dir) / "graph.json"


def load(run_dir):
    p = gpath(run_dir)
    if not p.is_file():
        die(f"no graph.json in {run_dir}. Run init first.")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"graph.json is corrupt: {e}")


def save(run_dir, g):
    gpath(run_dir).write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")


def read_data(arg):
    if arg == "-":
        raw = sys.stdin.read()
    elif arg.startswith("@"):
        raw = Path(arg[1:]).read_text(encoding="utf-8")
    else:
        raw = arg
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"--data is not valid JSON: {e}")
    if not isinstance(d, dict):
        die("--data must be a JSON object")
    return d


def next_id(items, prefix):
    n = 0
    for it in items:
        i = str(it.get("id", ""))
        if i.startswith(prefix) and i[len(prefix):].isdigit():
            n = max(n, int(i[len(prefix):]))
    return f"{prefix}{n + 1}"


def check_provenance(d, kind):
    tier = d.get("tier")
    if tier not in ("observed", "inferred"):
        die(f"{kind} requires tier: observed or inferred")
    sources = d.get("sources") or []
    if tier == "observed" and not sources:
        die(f"{kind} with tier observed requires at least one source URL. No source, no claim.")
    if tier == "inferred" and not (sources or d.get("basis")):
        die(f"{kind} with tier inferred requires a basis (and ideally sources). No source, no claim.")


def cmd_init(args):
    p = gpath(args.run_dir)
    Path(args.run_dir).mkdir(parents=True, exist_ok=True)
    if p.is_file() and not args.force:
        die(f"{p} already exists. Pass --force to overwrite.")
    g = {"meta": {"company": args.company, "role": args.role, "mode": args.mode,
                  "created": date.today().isoformat(), "budget": args.budget,
                  "flags": [], "overrides": {},
                  "jd_delta": {"confirmed_bar": [], "jd_only": [], "incumbents_only": []}},
         "people": [], "companies": [], "edges": [], "hypotheses": [], "rings": []}
    save(args.run_dir, g)
    print(json.dumps({"ok": True, "path": str(p)}))


def cmd_add_person(args):
    g = load(args.run_dir)
    d = read_data(args.data)
    for f in ("name", "ring"):
        if f not in d:
            die(f"person requires field: {f}")
    check_provenance(d, "person")
    d.setdefault("status", "verified" if d["tier"] == "observed" else "parked")
    d.setdefault("attributes", {})
    d["id"] = d.get("id") or next_id(g["people"], "p")
    g["people"].append(d)
    save(args.run_dir, g)
    print(json.dumps({"ok": True, "id": d["id"]}))


def cmd_add_company(args):
    g = load(args.run_dir)
    d = read_data(args.data)
    for f in ("name", "ring"):
        if f not in d:
            die(f"company requires field: {f}")
    check_provenance(d, "company")
    if any(c["name"].strip().lower() == d["name"].strip().lower() for c in g["companies"]):
        die(f"company already in graph: {d['name']} (duplicates poison the novelty metric)")
    via = d.get("discovered_via") or []
    d["tier_rank"] = "1" if {"flow", "attribute"} <= set(via) else ("2F" if "flow" in via else "2A")
    d.setdefault("status", "candidate")
    d.setdefault("probed", False)
    d.setdefault("attributes", {})
    d["id"] = d.get("id") or next_id(g["companies"], "c")
    g["companies"].append(d)
    save(args.run_dir, g)
    print(json.dumps({"ok": True, "id": d["id"], "tier_rank": d["tier_rank"]}))


def cmd_add_edge(args):
    g = load(args.run_dir)
    d = read_data(args.data)
    for f in ("from", "type", "to"):
        if f not in d:
            die(f"edge requires field: {f}")
    if d["type"] not in ("worked_at", "moved_to", "peer_of", "hired_by"):
        die("edge type must be worked_at, moved_to, peer_of, or hired_by")
    known = {x["id"] for x in g["people"]} | {x["id"] for x in g["companies"]}
    for end in (d["from"], d["to"]):
        if end not in known:
            die(f"edge endpoint not in graph: {end}")
    check_provenance(d, "edge")
    d["id"] = d.get("id") or next_id(g["edges"], "e")
    g["edges"].append(d)
    save(args.run_dir, g)
    print(json.dumps({"ok": True, "id": d["id"]}))


def cmd_add_hypothesis(args):
    g = load(args.run_dir)
    d = read_data(args.data)
    if not d.get("statement") or not d.get("probe"):
        die("hypothesis requires statement and probe (how would we falsify it?)")
    d.setdefault("support", [])
    d.setdefault("against", [])
    d.setdefault("status", "open")
    d["id"] = d.get("id") or next_id(g["hypotheses"], "h")
    g["hypotheses"].append(d)
    save(args.run_dir, g)
    print(json.dumps({"ok": True, "id": d["id"]}))


def find(g, kind, item_id):
    coll = {"person": "people", "company": "companies", "edge": "edges",
            "hypothesis": "hypotheses"}[kind]
    for it in g[coll]:
        if it["id"] == item_id:
            return it
    die(f"{kind} not found: {item_id}")


def cmd_set(args):
    g = load(args.run_dir)
    it = find(g, args.kind, args.id)
    val = args.value
    if val in ("true", "false"):
        val = val == "true"
    if args.kind == "company" and args.field == "status" and val == "verified":
        anchor = args.anchor or it.get("verification_anchor")
        if not anchor or anchor not in {p["id"] for p in g["people"]}:
            die("verified status requires --anchor <person id> already in the graph (the verification bar).")
        it["verification_anchor"] = anchor
        it["probed"] = True
    if args.append:
        it.setdefault(args.field, [])
        if not isinstance(it[args.field], list):
            die(f"field {args.field} is not a list")
        it[args.field].append(val)
    else:
        it[args.field] = val
    save(args.run_dir, g)
    print(json.dumps({"ok": True, "id": args.id, "field": args.field}))


def cmd_set_meta(args):
    g = load(args.run_dir)
    val = args.value
    if args.append:
        g["meta"].setdefault(args.field, [])
        if val not in g["meta"][args.field]:
            g["meta"][args.field].append(val)
    else:
        try:
            g["meta"][args.field] = json.loads(val)
        except json.JSONDecodeError:
            g["meta"][args.field] = val
    save(args.run_dir, g)
    print(json.dumps({"ok": True, "meta": {args.field: g["meta"][args.field]}}))


def cmd_concentration(args):
    g = load(args.run_dir)
    slots = []
    ring0 = [p for p in g["people"] if p.get("ring") == 0 and p.get("status") != "rejected"]
    for p in ring0:
        slots += [c.strip().lower() for c in p.get("attributes", {}).get("prior_companies", []) if c.strip()]
    if not slots:
        print(json.dumps({"ok": True, "note": "no prior_companies recorded yet", "n_profiles": len(ring0)}))
        return
    counts = {}
    for s in slots:
        counts[s] = counts.get(s, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])
    top2_share = round(sum(v for _, v in top[:2]) / len(slots), 2)
    flagged = top2_share >= THRESHOLDS["concentration_flag"]
    if flagged and "concentration" not in g["meta"]["flags"]:
        g["meta"]["flags"].append("concentration")
        save(args.run_dir, g)
    low_n = len(ring0) < THRESHOLDS["min_calibration_n"]
    if low_n and "low_confidence" not in g["meta"]["flags"]:
        g["meta"]["flags"].append("low_confidence")
        save(args.run_dir, g)
    print(json.dumps({"ok": True, "n_profiles": len(ring0), "prior_company_slots": len(slots),
                      "top_companies": top[:5], "top2_share": top2_share,
                      "concentration_flag": flagged, "low_confidence_flag": low_n,
                      "note": "flagged: cap Tier 1 list at 40% from flagged companies" if flagged else ""},
                     ensure_ascii=False))


def cmd_ring_stats(args):
    g = load(args.run_dir)
    ring = [c for c in g["companies"] if c.get("ring") == args.ring]
    added = len(ring)
    probed = sum(1 for c in ring if c.get("probed"))
    verified = sum(1 for c in ring if c.get("status") == "verified")
    relevance = round(verified / probed, 2) if probed else 0.0
    novelty = round(added / args.surfaced, 2) if args.surfaced else 0.0
    reasons = []
    if probed and relevance < THRESHOLDS["relevance_stop"]:
        reasons.append(f"relevance {relevance} < {THRESHOLDS['relevance_stop']}")
    if args.surfaced and novelty < THRESHOLDS["novelty_stop"]:
        reasons.append(f"novelty {novelty} < {THRESHOLDS['novelty_stop']}")
    if args.ring >= THRESHOLDS["max_rings"]:
        reasons.append(f"max rings ({THRESHOLDS['max_rings']}) reached")
    decision = "stop" if reasons else "continue"
    row = {"n": args.ring, "surfaced": args.surfaced, "added": added, "probed": probed,
           "verified": verified, "relevance_rate": relevance, "novelty_rate": novelty,
           "decision": decision, "notes": "; ".join(reasons)}
    if args.commit:
        g["rings"] = [r for r in g["rings"] if r.get("n") != args.ring] + [row]
        save(args.run_dir, g)
    print(json.dumps({"ok": True, **row, "committed": bool(args.commit)}))


def cmd_summary(args):
    g = load(args.run_dir)
    m = g["meta"]
    calls = 0
    log = Path(args.run_dir) / "exa_calls.jsonl"
    if log.is_file():
        calls = sum(1 for line in log.read_text(encoding="utf-8").splitlines() if line.strip())
    lines = [f"TALENT ORBIT · {m['role']} @ {m['company']} · mode={m.get('mode')} · {m['created']}",
             f"calls {calls}/{m.get('budget')} · flags: {', '.join(m.get('flags', [])) or 'none'}",
             f"people: {len(g['people'])} (ring0 observed: "
             f"{sum(1 for p in g['people'] if p.get('ring') == 0 and p.get('tier') == 'observed')})",
             ""]
    by_tier = {"1": [], "2F": [], "2A": []}
    for c in g["companies"]:
        by_tier.setdefault(c.get("tier_rank", "2A"), []).append(c)
    for t in ("1", "2F", "2A"):
        names = [f"{c['name']}[{c['status'][:1]}]" for c in by_tier.get(t, [])]
        lines.append(f"Tier {t} ({len(names)}): {', '.join(names[:15])}{' …' if len(names) > 15 else ''}")
    lines.append("")
    for h in g["hypotheses"]:
        lines.append(f"{h['id']} [{h['status']}] {h['statement']} (for {len(h['support'])}, against {len(h['against'])})")
    if g["rings"]:
        lines.append("")
        for r in sorted(g["rings"], key=lambda r: r["n"]):
            lines.append(f"ring {r['n']}: added {r['added']}, verified {r['verified']}, "
                         f"rel {r['relevance_rate']}, nov {r['novelty_rate']} → {r['decision']}")
    print("\n".join(lines))


def cmd_mermaid(args):
    g = load(args.run_dir)
    core = g["meta"]["company"]
    out = ["flowchart LR", f'    core(("{core}"))']
    style = {"1": "==>", "2F": "-->", "2A": "-.->"}
    rings = sorted({c.get("ring", 1) for c in g["companies"]})
    for ring in rings:
        members = [c for c in g["companies"] if c.get("ring") == ring and c.get("status") != "rejected"]
        if not members:
            continue
        out.append(f'    subgraph R{ring}["Ring {ring}"]')
        for c in members:
            mark = "✓" if c.get("status") == "verified" else ("…" if c.get("status") == "candidate" else "·")
            out.append(f'        {c["id"]}["{c["name"]} {mark} T{c.get("tier_rank", "?")}"]')
        out.append("    end")
        for c in members:
            arrow = style.get(c.get("tier_rank"), "-->")
            out.append(f'    core {arrow} {c["id"]}')
    text = "\n".join(out)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(json.dumps({"ok": True, "path": args.out}))
    else:
        print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("--company", required=True)
    pi.add_argument("--role", required=True)
    pi.add_argument("--mode", default="engaged", choices=["engaged", "work_sample"])
    pi.add_argument("--budget", type=int, default=80)
    pi.add_argument("--force", action="store_true")

    for name in ("add-person", "add-company", "add-edge", "add-hypothesis"):
        p = sub.add_parser(name)
        p.add_argument("--data", required=True, help="JSON object, @file.json, or - for stdin")

    ps = sub.add_parser("set")
    ps.add_argument("--kind", required=True, choices=["person", "company", "edge", "hypothesis"])
    ps.add_argument("--id", required=True)
    ps.add_argument("--field", required=True)
    ps.add_argument("--value", required=True)
    ps.add_argument("--append", action="store_true")
    ps.add_argument("--anchor", default=None, help="person id, required when verifying a company")

    pm = sub.add_parser("set-meta")
    pm.add_argument("--field", required=True)
    pm.add_argument("--value", required=True)
    pm.add_argument("--append", action="store_true")

    sub.add_parser("concentration")

    pr = sub.add_parser("ring-stats")
    pr.add_argument("--ring", type=int, required=True)
    pr.add_argument("--surfaced", type=int, required=True,
                    help="raw company names encountered this ring, including rejects")
    pr.add_argument("--commit", action="store_true")

    sub.add_parser("summary")

    pz = sub.add_parser("mermaid")
    pz.add_argument("--out", default=None)

    args = ap.parse_args()
    {"init": cmd_init, "add-person": cmd_add_person, "add-company": cmd_add_company,
     "add-edge": cmd_add_edge, "add-hypothesis": cmd_add_hypothesis, "set": cmd_set,
     "set-meta": cmd_set_meta, "concentration": cmd_concentration,
     "ring-stats": cmd_ring_stats, "summary": cmd_summary, "mermaid": cmd_mermaid}[args.cmd](args)


if __name__ == "__main__":
    main()
