# Exa Playbook for Talent Orbit

How to spend the call budget well. Endpoints, recipes per phase, and failure modes.

## Client basics

All calls go through `scripts/exa_client.py` (stdlib only, no installs needed).

```bash
python scripts/exa_client.py check [--live]
python scripts/exa_client.py search "QUERY" [--type auto|neural|keyword] [--category "linkedin profile"|company|news] \
    [--num 10] [--include-domains a.com,b.com] [--exclude-domains x.com] \
    [--start-published YYYY-MM-DD] [--highlights "focus question"] [--text] [--max-chars 4000] \
    [--run-dir DIR] [--dry-run]
python scripts/exa_client.py similar "https://company.com" [--num 10] [--include-source] [--run-dir DIR]
python scripts/exa_client.py contents URL [URL ...] [--highlights "q"] [--summary "q"] [--text] [--run-dir DIR]
```

Always pass `--run-dir` during a real run so calls are logged and the budget is enforced. `--dry-run` prints the payload without spending a call; use it to sanity-check a new query shape.

## Cost discipline

- Highlights first, full text only when a specific page must be parsed deeply. Highlights with a focused question are usually enough to extract attributes.
- `--type keyword` for exact names (people, companies). `--type neural` or `auto` for concept queries (journeys, lookalikes).
- Start with `--num 5` to `10`. Widen only if the batch assessment says the recall was the problem.
- One good `contents` call on a team page beats five profile searches.
- Do not re-fetch LinkedIn URLs with `contents`; LinkedIn blocks crawling. Work from the text and highlights Exa returns in the search response itself.

## Phase 1 recipes: finding incumbents (Ring 0)

LinkedIn profiles, exact-match style:
```bash
search '"<Company>" "<Role Title>"' --type keyword --category "linkedin profile" --num 10
```
Run title variants as separate cheap calls: the literal title, the internal-equivalent titles (Tech Lead / Lead Engineer / Staff Engineer and so on), and the function ("engineering" + seniority word). Profiles are not reliably date-filterable, so read tenure and join windows from the returned snippet text.

Team and about pages (often the cleanest roster):
```bash
search '<Company> engineering team' --num 5
contents https://<company>.com/about --highlights "engineering team members names roles"
```

Other roster sources: GitHub org members (`search '<Company> github engineering' --category github` if relevant to the stack), conference and meetup speaker pages, "X joins Company" press, podcast guest bios.

Attribute extraction per person: prior companies and rough date windows, tenure at target, promotion within target, stack and scope words, geography. Record what the snippet supports as `observed`; anything concluded is `inferred` with a basis note.

## Phase 3 recipes: flow engine

From a known person:
```bash
search '"<Full Name>" "<Prior Company>"' --type keyword --num 5
```
Joiner and leaver press, useful for date windows:
```bash
search '"joined <Company>" engineer' --type keyword --category news --start-published 2021-01-01
search '"<Company>" "previously at"' --type keyword --num 10
```
Add edges with windows. An edge without a rough date window is allowed but weak; prefer windowed edges when choosing what to expand.

## Phase 3 recipes: attribute engine

Characterize an origin company (only claim what sources support):
```bash
search '<Company> engineering blog' --num 5
search '<Company> migration OR scaling OR rewrite OR re-architecture' --num 8
search '<Company> funding series' --category news --num 5
```
Lookalike expansion, two complementary moves:
```bash
similar https://<company>.com --num 10
similar https://<company>.com/blog --num 10
search '<journey description> <geo>' --type neural --category company --num 10
```
Journey descriptions are short and concrete: "B2B SaaS that rebuilt a monolith into services while scaling past 1M users, <your target geography>". Run 2 to 3 phrasings; neural search rewards variation.

## Phase 3 recipes: verification probe

```bash
search '"<Candidate Company>" "<role title or equivalent>"' --type keyword --category "linkedin profile" --num 5
```
Pass bar: 1 named person, in an equivalent-scope role, whose snippet shows 2+ calibration attributes, from an observed source. Match on scope signals (team size, ownership, stack depth), not the literal title string.

## Layer 3 recipes (only when triggered)

Hiring managers and peers of incumbents:
```bash
search '"<Company>" "Engineering Manager"' --type keyword --category "linkedin profile" --num 5
```
Then run the flow recipes on those people. Keep Layer 3 nodes clearly marked (`edge type: peer_of` or `hired_by`) so their second-order nature stays visible in the deliverable.

## Thin-footprint fallbacks

When LinkedIn coverage or engineering blogs are thin (common for smaller or less-online markets):
- Company team pages and careers pages via `contents`.
- Local press and startup ecosystem databases for company discovery. These find companies, not people.
- GitHub activity and local meetup or conference speaker lists for people.
- If after fallbacks a company still cannot be characterized or verified, park it with reason `thin_footprint` and list it in the coverage gaps section. A parked honest gap is worth more to the client than a confabulated journey.

> Tuning these fallbacks to a specific geography (which local databases, which press, which corridors actually carry talent) is where the method earns its edge in practice. The recipes above are the general shapes; the local tuning is left to you.

## Failure modes to expect

- LinkedIn snippets truncate mid-career-history. Extract what is there; do not extrapolate the rest of the history.
- Stale profiles: someone may have left. Cross-check anchors against any newer source before relying on them.
- Title inflation and deflation across orgs. Normalize on scope.
- Neural search returns plausible-sounding but off-market companies. The verification probe is the filter; the search result alone never verifies a company.
- 429s: the client retries twice with backoff. If they persist, slow down and reduce `--num`.
