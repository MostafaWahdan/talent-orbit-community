# Talent Orbit (Community Edition)

A Claude Code skill for **incumbent-calibrated talent market mapping**.

<img width="1620" height="2025" alt="talent-orbit" src="https://github.com/user-attachments/assets/ac096294-2e6c-4d94-8756-0fa20139204a" />



Most market maps start from the job description. Talent Orbit starts from the
people a company **already hired** for the role. Those hires are revealed
preference; the JD is stated preference; and revealed preference beats stated
preference almost every time. The skill turns a handful of real incumbents into
a tiered, evidence-graded map of the companies and people that orbit them,
expanding outward in rings until the signal degrades.

You get a reasoning product, not a scraped list: a transparent map with testable
hypotheses, explicit provenance on every claim, and the sharp verification
questions a hiring team should actually answer.

## What this is (and what it is not)

This is the **open community edition**: the full method, published in the open.
Philosophy, the ring model, evidence grading, the two-engine expansion, the
stopping scorecard, the verification bar, and the run-level tooling are all here
and all yours to use, fork, and learn from.

The position is deliberate: **publish the algorithm, keep the weights.** The
parts that only compound with real reps stay out of this edition, namely the
cross-run learning loop that turns finished engagements into ground truth, the
geography-tuned query recipes, and the relevance scoring model. The general
query shapes are here; tuning them to your own market is the work, and it is
where the method earns its edge. Nothing here is crippled. It runs a complete,
honest map on its own.

## What is inside

```
talent-orbit-community/
  SKILL.md                          the method, end to end (Phases 0 to 5)
  references/
    exa-playbook.md                 Exa query recipes per phase, cost discipline
    graph-schema.md                 the run graph schema and CLI
    deliverable-template.md         the client-ready output structure
  scripts/
    exa_client.py                   thin Exa API client (stdlib only)
    graph.py                        the evidence graph CLI (stdlib only)
```

No third-party Python packages. Standard library only. Works on Windows, macOS,
and Linux.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3.8+
- An [Exa](https://exa.ai) API key (the skill uses Exa for all web evidence)

## Install

1. Copy the `talent-orbit/` folder into your skills directory:
   - macOS / Linux: `~/.claude/skills/talent-orbit`
   - Windows: `%USERPROFILE%\.claude\skills\talent-orbit`
2. Make your Exa key discoverable. Set `EXA_API_KEY` in your environment, or add
   a line `EXA_API_KEY=your-key` to a `.env` file in your working directory, your
   home directory, or `~/.claude/.env`.
3. In Claude Code, start a run with `/talent-orbit` or just ask it to "map the
   market around this team" for a given company and role.

Verify the key first if you want: `python scripts/exa_client.py check --live`.

## How a run goes

1. **Intake.** Give it a target company and role. JD, known incumbents, and
   geography are optional but help.
2. **Ring 0 calibration.** It finds real incumbents and extracts the pattern of
   what good has actually looked like for this role at this company.
3. **Hypotheses.** It writes competing, falsifiable hypotheses about the real
   hiring bar, then tries to break them.
4. **Ring expansion.** Two engines run in parallel, observed talent flows and
   attribute lookalikes. Companies found by both rank highest. Every kept company
   has to clear a verification bar before it counts.
5. **Scorecard stop.** After each ring it computes relevance and novelty and
   stops by the numbers, not by vibes.
6. **Deliverable.** A founder-readable map: tiers with provenance, an orbit
   diagram, coverage gaps and bias flags it is honest about, and the verification
   questions to take to the hiring team.

## The ground rules baked in

- **No source, no claim.** Every node carries a source URL and an evidence tier.
- **Inference never compounds silently.** Inferred nodes do not seed the next ring.
- **People are verification anchors, not a contact list.** Named people exist in
  the map only to prove a company holds matching talent. The method refuses to
  treat them as leads, and the deliverable says so.
- **Honest gaps beat confident fiction.** Thin-footprint companies get parked and
  listed, never given a made-up story.

## Credits and license

Talent Orbit is the talent-intelligence method behind **The HireOS**
([thehireos.co](https://thehireos.co)). If you build on it, a link back is
appreciated and keeps the canon pointing the right way.

Released under the MIT License (see `LICENSE`). Use it, fork it, ship maps with
it. If it helps you make a better hire, that is the whole point.
