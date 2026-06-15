---
name: talent-orbit-community
description: >
  Build an evidence-graded talent market map by calibrating on a company's
  existing team (the incumbents) instead of the JD alone, then expanding
  outward in rings through observed talent flows and lookalike companies
  using the Exa API. Use this skill whenever the user mentions incumbent
  calibration, calibration profiles, talent flow mapping, orbit or ring
  expansion, lookalike companies, reverse-engineering a hiring bar,
  "map the market around this team", "where did this team come from",
  "what does good look like for this role", or wants a sourcing map for a
  work sample without hiring team access. Also activate on /orbit or
  /talent-orbit-community. Requires EXA_API_KEY in env or a .env file.
---

# Talent Orbit (Community Edition)

Incumbent-calibrated market mapping. The premise: people a company already hired for a role are revealed preference, the JD is stated preference, and revealed beats stated. This skill turns a handful of real hires into a tiered, evidence-graded map of companies and verification-anchor people, expanding outward in rings until the signal degrades.

The output is a reasoning product, not a database dump: a transparent map with testable hypotheses, explicit provenance, and sharp verification questions for the hiring team.

> This is the open community edition of the Talent Orbit method: the algorithm, published in full. See the README for what it deliberately leaves out and why.

## Hard rules

These exist because every step of this method runs on inference, and inference errors compound across rings. The guardrails are the product.

1. **No source, no claim.** Every person, company, and edge in the graph carries at least one source URL and an evidence tier: `observed` (a page directly states it) or `inferred` (concluded from reasoning across sources, with the basis recorded). Never write a node without provenance.
2. **Inferred nodes never expand.** Only `observed` people and `verified` companies seed the next ring. One misread node in ring 1 otherwise grows a whole false branch in ring 2.
3. **Minimum N before patterns.** Do not extract a calibration pattern from fewer than 4 observed in-role profiles. Below 4, widen to adjacent titles at the same company and set the `low_confidence` flag on the run. An LLM will confidently find a narrative in 3 profiles; that confidence is the failure mode.
4. **Hypotheses, not narratives.** Phase 2 outputs 2 to 4 competing hypotheses about what good looks like, each with supporting profile IDs and a falsification probe. Each ring tries to break them, not confirm them.
5. **Two engines, intersection ranks.** Expand via observed flows AND via attribute lookalikes. Companies surfaced by both are Tier 1. Single-engine companies are Tier 2F (flow only) or Tier 2A (attribute only). Each engine checks the other's blind spot.
6. **Stop by scorecard, not vibes.** After each ring, compute the ring stats with `graph.py ring-stats`. Stop expanding when verified relevance drops below 0.30, novelty drops below 0.20, ring 3 is reached, or the call budget is exhausted. Whichever comes first.
7. **The graph on disk is the source of truth, not your context.** Write every finding to `graph.json` via `scripts/graph.py` as you go. After context compaction or a long run, refresh with `graph.py summary` instead of re-reading raw search results.
8. **Assess between every batch.** Never fire the next batch of searches without writing a batch assessment to `log.md` first (format in Phase 4). The next batch must be designed from the assessment, not from momentum.
9. **Budget discipline.** Default budget is 80 Exa API calls per run. `exa_client.py` enforces it when `--run-dir` is passed. Prefer highlights over full text, keyword type for exact names, and small `--num` values.
10. **Public professional data only.** Named people in the map are verification anchors that prove a company holds in-role talent matching the calibration. They are not a contact list and the deliverable must frame them that way.
11. **Output style.** Never use em-dashes or hyphens as punctuation in any written output, including the deliverable, log entries, and chat summaries. Use commas, colons, periods, or restructure the sentence.

## Setup

1. Read `references/exa-playbook.md` before the first API call. Read `references/graph-schema.md` before the first graph write.
2. Create a run directory: `orbit-runs/<company>-<role-slug>-<YYYYMMDD>/`.
3. Verify the API key: `python <skill_dir>/scripts/exa_client.py check` (add `--live` to spend 1 call confirming the key actually works).
4. Initialize the graph: `python <skill_dir>/scripts/graph.py init --run-dir <dir> --company "<name>" --role "<title>" [--budget 80]`.
5. Create `log.md` in the run dir with the intake summary as its first entry.

## Phase 0: Intake

Minimum viable input: target company + role title. Capture if available: JD text or URL, names of known incumbents, geography, seniority bounds, client context, and mode.

Two modes, set in graph meta:
- `engaged`: hiring team is reachable. Open questions become a verification agenda.
- `work_sample`: hiring team is not reachable by design. State assumptions explicitly and frame questions as "what I would verify first". The map demonstrates judgment, so showing the reasoning and its limits is the point.

If no JD is provided, note it. Skip the JD delta step but flag in the deliverable that stated-preference data was unavailable.

## Phase 1: Ring 0 calibration

Goal: a verified set of people currently or recently in the role at the target company, with extracted attributes.

1. Find incumbents using the Ring 0 recipes in the playbook (LinkedIn profile category searches, team pages, GitHub org, conference talks, press).
2. For each person, write a node with sources, tier, and attributes: prior companies (with rough date windows where visible), tenure, promotion signals, stack and scope signals, geography.
3. Apply hygiene rules:
   - Weight by tenure and trajectory. Someone with 2+ years and a promotion is strong ground truth. A 6 month joiner is weak signal. An 8 month contractor is not calibration data; park them.
   - Window by join date. A 2019 hire passed a different filter than a 2025 hire. Prefer hires from the last 2 to 3 years for the pattern; keep older ones as context.
4. Compute concentration: `graph.py concentration`. If the top 2 prior companies account for 60% or more of prior-company slots, set the `concentration` flag. This flag forces a diversification quota later: at most 40% of the final Tier 1 list may trace only to the flagged companies.
5. JD delta (if a JD exists): diff the incumbent pattern against the JD requirements.
   - Present in both: the confirmed bar.
   - JD only: probably the delta the HM wants in THIS hire (more senior, new specialty, a gap). This neutralizes the trap of calibrating toward "more of the same" when the role exists precisely because something is missing.
   - Incumbents only: unwritten requirements. Often the real filter.
   Record all three lists in the graph meta and turn the deltas into verification questions.

## Phase 2: Competing hypotheses

From the calibration set, write 2 to 4 hypotheses via `graph.py add-hypothesis`. Each needs: a statement ("the bar is X, not Y"), supporting profile IDs, and a falsification probe (a concrete search that would weaken it). Examples of good hypothesis shapes: "scale stage matters more than domain", "the real filter is having lived a specific migration", "geography is a proxy for a timezone constraint, not a hard gate".

Design Ring 1 searches to test these, especially to falsify them.

## Phase 3: Ring expansion loop

Repeat per ring (1, 2, 3 max):

1. **Flow engine.** From observed nodes in the previous ring, map where people came from and went to. Add `worked_at` and `moved_to` edges with date windows. New companies enter as `candidate` with `discovered_via: flow`.
2. **Attribute engine.** For each significant origin company, characterize what makes its talent distinctive: stage and scale journey, technical inflections lived (migrations, rewrites, scaling walls, regulatory regimes), engineering brand strength. Then expand to lookalikes via `findSimilar` on homepages and engineering blogs plus neural searches describing the journey in the target geography. New companies enter with `discovered_via: attribute`. If a company has a thin public engineering footprint (common in smaller or less-online markets), record `eng_brand: thin` and do NOT fabricate a journey; characterize only what sources support.
3. **Intersection ranking.** A company surfaced by both engines is Tier 1. Flow only is 2F, attribute only is 2A. Record provenance on the node.
4. **Verification probe.** For each candidate company worth keeping, search for at least 1 named person currently in the equivalent role whose profile shows 2 or more calibration attributes from an observed source. Found: mark `verified` and store the anchor. Not found after a reasonable probe: mark `parked` with a reason. Title normalization warning: one org's Tech Lead is another's Senior Engineer; match on scope signals, not the literal title.
5. **Ring scorecard.** Run `graph.py ring-stats --ring N --surfaced <raw company names seen this ring> --commit`. It computes relevance (verified / probed) and novelty (new qualifying companies / surfaced) and prints a continue or stop decision against the thresholds. Respect it.
6. **Layer 3 trigger (conditional).** Only if Ring 1 closes with fewer than 6 verified companies, add the peer and hiring-team flow layer: where the managers and peers of incumbents came from and went to. It is second-order signal at first-order cost, so it is a fallback for thin markets, not a default.

If Ring 1 stops due to low novelty but contains at least one high-quality parked or unresolved research lead, run a manual snowball extension before declaring the market exhausted.

Manual snowball may trace:
- alias/name variants
- prior companies
- peers at the same company
- hiring managers or technical leaders at the same company
- profiles who worked before/after the anchor in the same role family

All outputs must be labeled manual_extension and cannot be presented as Orbit-generated evidence unless separately verified.

## Phase 4: Batch assessment discipline

After every batch of searches, append to `log.md`:

```
## Batch <n> — <phase/ring> — <timestamp>
Queries run: <list with result counts>
Kept / discarded: <what entered the graph, what was rejected and why>
Learned: <2 to 4 lines of actual signal>
Hypotheses: <h1 supported by ... / h2 weakened by ...>
Next batch: <design, derived from the above>
Calls used: <n>/<budget>
```

This is what makes the run iterative instead of a search dump. The "Next batch" line must reference something from "Learned" or "Hypotheses".

## Phase 5: Deliverable

1. Read `references/deliverable-template.md` and follow it exactly.
2. Generate the orbit diagram: `graph.py mermaid --out <run-dir>/orbit.mmd` and embed it.
3. Mandatory sections regardless of mode: coverage gaps and bias flags (concentration flag, thin-footprint geographies, low N), and the verification questions list.
4. Every company row cites provenance (tier, engines, anchor person with source). Every confidence claim states its N.
5. Write the deliverable as `deliverable.md` in the run dir. Client ready means a founder could read it cold.

## Defaults

| Parameter | Default |
|---|---|
| MIN_CALIBRATION_N | 4 observed in-role profiles |
| Concentration flag | top 2 prior companies >= 60% of slots |
| Diversification quota when flagged | <= 40% of Tier 1 from flagged companies |
| Stop: relevance | < 0.30 |
| Stop: novelty | < 0.20 |
| Max rings | 3 |
| Layer 3 trigger | Ring 1 verified companies < 6 |
| API call budget | 80 per run |
| Verification bar | 1 named in-role person, 2+ calibration attributes, observed source |

The user can override any of these at intake; record overrides in graph meta.

## Files

| File | Read when |
|---|---|
| `references/exa-playbook.md` | Before the first Exa call. Query recipes per phase, cost discipline, thin-footprint fallbacks, failure modes. |
| `references/graph-schema.md` | Before the first graph write. Schema, statuses, CLI examples. |
| `references/deliverable-template.md` | At Phase 5. |
| `scripts/exa_client.py` | Execute, do not read. `--help` for usage. |
| `scripts/graph.py` | Execute, do not read. `--help` for usage. |
