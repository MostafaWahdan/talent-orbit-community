# Graph Schema and CLI

`graph.json` is the single source of truth for a run. All writes go through `scripts/graph.py`, which validates provenance and computes stats. Do not hand-edit the JSON or hold the whole graph in context; use `summary` to refresh.

## Schema

```json
{
  "meta": {
    "company": "ExampleCo", "role": "Tech Lead", "mode": "engaged|work_sample",
    "created": "2026-01-01", "budget": 80, "flags": ["low_confidence", "concentration"],
    "overrides": {}, "jd_delta": {"confirmed_bar": [], "jd_only": [], "incumbents_only": []}
  },
  "people": [{
    "id": "p1", "name": "…", "role_title": "…", "company_id": "c1", "ring": 0,
    "tier": "observed|inferred", "sources": ["url"], "basis": "required if inferred",
    "status": "verified|parked|rejected",
    "attributes": {
      "prior_companies": ["…"], "tenure_months": 30, "promoted": true,
      "joined": "2023-06", "stack": ["…"], "scope": "…", "geo": "…"
    },
    "notes": "…"
  }],
  "companies": [{
    "id": "c2", "name": "…", "ring": 1,
    "discovered_via": ["flow", "attribute"], "tier_rank": "1|2F|2A",
    "tier": "observed|inferred", "sources": ["url"], "basis": "…",
    "status": "candidate|verified|parked|rejected", "probed": true,
    "park_reason": "thin_footprint|no_anchor|off_market|…",
    "attributes": {"stage": "…", "journey": ["…"], "geo": "…", "eng_brand": "strong|thin"},
    "verification_anchor": "p7"
  }],
  "edges": [{
    "id": "e1", "from": "p1", "type": "worked_at|moved_to|peer_of|hired_by", "to": "c2",
    "window": "2019-2022", "tier": "observed|inferred", "sources": ["url"], "basis": "…"
  }],
  "hypotheses": [{
    "id": "h1", "statement": "…", "support": ["p1", "p3"], "against": [],
    "status": "open|supported|weakened|dead", "probe": "search design that would falsify"
  }],
  "rings": [{
    "n": 1, "surfaced": 22, "added": 9, "probed": 8, "verified": 5,
    "relevance_rate": 0.62, "novelty_rate": 0.41, "decision": "continue|stop", "notes": "…"
  }]
}
```

Rules enforced by the CLI:
- Every person, company, and edge requires `sources` (non-empty) OR `tier: inferred` plus a `basis`.
- `tier_rank` 1 requires both engines in `discovered_via`.
- `verified` company status requires a `verification_anchor` pointing at an existing person.

## CLI

```bash
python scripts/graph.py init --run-dir DIR --company "X" --role "Y" [--mode engaged] [--budget 80]
python scripts/graph.py add-person --run-dir DIR --data '{"name": "...", "ring": 0, "tier": "observed", "sources": ["..."], "attributes": {...}}'
python scripts/graph.py add-company --run-dir DIR --data '{"name": "...", "ring": 1, "discovered_via": ["flow"], "tier": "observed", "sources": ["..."]}'
python scripts/graph.py add-edge --run-dir DIR --data '{"from": "p1", "type": "worked_at", "to": "c2", "window": "2019-2022", "tier": "observed", "sources": ["..."]}'
python scripts/graph.py add-hypothesis --run-dir DIR --data '{"statement": "...", "support": ["p1"], "probe": "..."}'
python scripts/graph.py set --run-dir DIR --kind company --id c2 --field status --value verified
python scripts/graph.py set --run-dir DIR --kind company --id c2 --field verification_anchor --value p7
python scripts/graph.py set-meta --run-dir DIR --field flags --append low_confidence
python scripts/graph.py concentration --run-dir DIR
python scripts/graph.py ring-stats --run-dir DIR --ring 1 --surfaced 22 [--commit]
python scripts/graph.py summary --run-dir DIR
python scripts/graph.py mermaid --run-dir DIR [--out orbit.mmd]
```

`--data` also accepts `@file.json` or `-` for stdin, which is safer than long shell strings on Windows.

`ring-stats` reads probed and verified counts from the data; you supply `--surfaced` (raw company names you encountered this ring, including duplicates and rejects) from your batch assessment, because the graph only stores what survived your filter. Honest surfaced counts keep the novelty metric honest.

`summary` prints a compact state dump (meta, ring table, companies by tier, open hypotheses, flags, calls used). Run it to re-orient after compaction instead of re-reading search output.
