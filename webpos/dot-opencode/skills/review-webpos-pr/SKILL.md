---
name: review-webpos-pr
description: End-to-end workflow for reviewing a merchantos/webPOS pull request (or any LSR-tagged repo following the same conventions). Use when the user asks to review a PR, look at a PR, or audit a PR's changes. Read-only by default per pr-review-interaction.mdc; produces a structured verdict in chat.
---

# Review a webPOS Pull Request

End-to-end workflow that complements:

- `pr-review.mdc` — the 8 review criteria and architectural discipline (what to look for)
- `pr-review-interaction.mdc` — how to behave (read-only by default, verify before commenting)
- `pr-thread-audit/SKILL.md` — auditing unreplied threads (use when triaging existing feedback)
- `pre-merge-do-not-merge-check/SKILL.md` — before merging

This skill covers the **how** of executing a single review session.

## Phase 1 — Gather context (parallel)

Fire these five calls in parallel before reading any code:

```bash
gh pr view <num> --repo merchantos/<repo> \
  --json title,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,body,author,labels

gh pr checks <num> --repo merchantos/<repo>

gh api repos/merchantos/<repo>/pulls/<num>/commits \
  | jq -r '.[] | "\(.sha[0:10])  \(.commit.author.date)  \(.commit.message | split("\n")[0])"'

gh api repos/merchantos/<repo>/pulls/<num>/reviews \
  | jq -r '.[] | "\(.submitted_at) [\(.state)] \(.user.login) id=\(.id)"'

gh api repos/merchantos/<repo>/pulls/<num>/comments \
  | jq -r '.[] | "\(.created_at) [\(.user.login)] \(.path):\(.line // .original_line) in_reply_to=\(.in_reply_to_id // "none")"'
```

What to extract:

- **PR scope**: additions/deletions, file count, draft state, base branch, labels (look for `security`, `do-not-merge`, etc.).
- **CI**: any non-pass status is a blocker until verified.
- **Commits**: single commit vs. stacked iterations; squash-merge implication.
- **Existing reviews**: who has already approved/commented; per `pr-review-interaction.mdc`, you must read these before forming opinions.
- **Inline comments**: the threads you may NOT duplicate.

## Phase 2 — Thread resolution state (GraphQL)

REST doesn't expose `isResolved`. Use GraphQL when assessing what's pending:

```bash
gh api graphql -f query='
query {
  repository(owner: "merchantos", name: "<repo>") {
    pullRequest(number: <num>) {
      reviewThreads(first: 50) {
        nodes {
          isResolved
          isOutdated
          path
          line
          comments(first: 1) { nodes { author { login } } }
        }
      }
    }
  }
}' | jq -r '.data.repository.pullRequest.reviewThreads.nodes[] |
  "resolved=\(.isResolved) outdated=\(.isOutdated) \(.path):\(.line) opener=\(.comments.nodes[0].author.login)"'
```

Use the `pr-thread-audit` skill for deep triage of unreplied threads.

## Phase 3 — Get the diff (size-aware)

```bash
gh pr diff <num> --repo merchantos/<repo>
```

If the response is **HTTP 406 "diff exceeded the maximum number of files (300)"**, fall back to:

```bash
gh api repos/merchantos/<repo>/pulls/<num>/files --paginate \
  | jq -r '.[] | "\(.status) \(.additions)+/\(.deletions)- \(.filename)"'
```

Then fetch individual file patches as needed:

```bash
gh api "repos/merchantos/<repo>/contents/<path>?ref=<head-branch>" --jq '.content' | base64 -d
```

This is also how you read context files when the PR branch isn't fetched locally.

### Read every file at a pinned ref — never the working tree

`cat` / `sed` / `grep` answer for **whatever branch you happen to be on**, which during a review is almost never the PR. Resolve the head SHA once, then read everything through it:

```bash
HEAD_SHA="$(gh api repos/merchantos/<repo>/pulls/<num> --jq '.head.sha')"  # full 40-char SHA
git fetch origin pull/<num>/head --quiet
git show "$HEAD_SHA:<path>"

git rev-parse --abbrev-ref HEAD                 # what am I actually sitting on?
git rev-list --count HEAD..origin/develop-retail
```

Bind the verified SHA once and reuse that exact variable in every parallel Contents/API read; never manually retype it. If a pinned-ref request returns 404 or its requested ref differs from `HEAD_SHA`, stop analysis, correct the ref, and rerun the read before relying on the result.

A stale checkout doesn't give you one wrong answer — it gives you **N mutually-consistent wrong answers**. The assembler, the DTO, the config class and the fixture all agree with each other at the old commit, so *"I confirmed it four independent ways"* is exactly how a stale tree feels from the inside. Corroboration only counts when the sources sit at the **same, pinned** ref.

Apply the same rule before contradicting another reviewer: their citation may be correct and your checkout wrong.

This burned #27348 — a must-fix posted against `configuration.laneID` read from a tree 15 commits behind `develop-retail`, missing #27332 which had added that field at all four layers. The finding was false, the suggested fix would have broken working code, and a second reviewer's correct citation got waved off as a misread.

## Phase 4 — Apply review criteria

Per `pr-review.mdc`: Functionality, Maintainability, Reliability, Performance/Scalability, Reusability, Security, Readability, Testability, plus architectural discipline and feature-flag verification.

For each criterion, **cite evidence** from the diff or from a `Grep`/`Read` in the workspace. Don't make claims you can't anchor to a line.

## Phase 5 — webPOS-specific cross-checks

Things I've consistently caught (or missed and learned from) on webPOS PRs:

### Import hygiene after deletions

When a flag/method is removed, files may keep importing `Features` or `ToggleName` while no longer using them. Check both:

- Files where the `Features::` call was the only usage → import should be gone.
- Files where `Features::` remains for other flags → import stays.

### Test falsifiability

Reject "I added a test" claims without verifying the test would actually fail without the change. Watch for:

- Assertions broad enough to pass for the wrong reason (e.g. `assertNotNull` on something that's always non-null).
- Parameterized tests that exercise only one branch.
- Migration tests that don't assert idempotency (run twice, second run is a no-op).

### Feature flag gating

- New behavior should be flag-gated; existing behavior should be preserved when flag is off.
- Verify the same flag is checked at **every** entry point. A missing check at one call site silently leaks behavior.
- Treat silent behavioral narrowing as rollout-sensitive. Search filters, ranking changes, and eligibility rules can fail by returning valid-looking empty results rather than errors; require a rollback mechanism scoped to the new behavior instead of relying on disabling the entire parent feature.
- Gate request-driven behavior at both boundaries: the producer should stop emitting the field while disabled, and the authoritative backend consumer should ignore or reject it. A stale page or external caller can continue sending old values after a flag changes.
- Test flag-on behavior and exact flag-off parity, including degraded but still useful operations that existed before the PR.

### Fixture updates after schema or filter changes

When a SQL filter changes semantics (e.g. inclusion-based instead of exclusion-based), test fixtures often need to add backing rows. Watch for tests that previously passed by coincidence.

### Stacked PRs

If the PR is part of a stack, focus on the **last commit** as requested and explicitly note that earlier commits inherit from dependency PRs. Verify base branch points where you expect.

### Public-contract completeness (docblock + visibility)

New/changed public methods are where mechanical contract nits slip past logic-focused review (and PHPStan's `missingCheckedExceptionInThrows` is `false` in this repo, so `@throws` gaps aren't tool-caught). Cross-check each new public method:

- **`@throws` is complete** — lists every exception that can propagate, including **rethrows** (`catch (X $e) { ... throw $e; }`) and exceptions inherited from a foundation/base call. Mirror sibling methods in the same class.
- **Referenced symbols are caller-accessible** — anything a public signature or docblock `@see`s (constants, types) must be at least as visible as the method itself; match the sibling symbol's visibility.
- **Sibling parity** — a method added next to an existing one matches its contract-doc shape and conventions.

Both LSR-37248 review nits (missing `@throws PermanentStorecoveException` on `getEvidence`; `private NO_BODY_LIMIT` referenced in a public docblock) would have been caught here.

### Assembly-site consistency

When building a value object / DTO / array from inputs, prepare sibling fields the **same way** — normalize/validate each value at its **declaration** so the construction call reads uniformly (`new X(a: $a, b: $b)`), rather than mixing a pre-computed local with an inline-normalized expression for its sibling (`new X(a: $a, b: is_array($b) ? $b : [])`). Asymmetric field handling at the assembly site is a readability nit reviewers will flag — e.g. LSR-37248's `EvidenceResult::fromResponse()` built `$documents` into a local but normalized `evidence` inline in the `new self(...)` call.

### Data-layer string round-trip (entity-encoding + sibling parity)

When a PR newly exposes a **persisted string column** to the FE/API (a transformer, a `react_props` payload, a view field), verify the round-trip — the render site being XSS-safe is **not** enough; the more common bug is *over*-encoding that renders mangled:

- The legacy `bs_table`/`data_Base` layer **HTML-entity-encodes string columns on write**, so a value read back from the DB is entity-encoded (`"`→`&quot;`). Expose it via `cust_html_entity_decode()` or it renders as `&quot;…` (worst case a persisted JSON blob shows as `[{&quot;source&quot;:...}]`). Precedent: `EInvoicingStatusTransformer::rejectionReason()`, `EInvoicingShopOptionTransformer::nullableString()`. See `r-series-data-layer-conventions` for the encoding + null-vs-`''` rules.
- **Diff the field against the nearest sibling handler in the same module.** A decode/normalize the siblings all do but this change omits is the tell — this is the check that catches it, not a security lens.
- These columns return `''` (never `null`) for NULL values, so `$x->field !== null` guards on them are dead code; and an **in-memory** model read returns the RAW string while a **DB** read-back returns the ENCODED one → the same record can render differently across endpoints (e.g. the synchronous send response vs. a listing refresh).

LSR-38860's must-fix (persisted `errorMessage` exposed un-decoded on two read paths, inconsistent with its sibling transformers, marked Approve anyway) would have been caught here.

### Public API DTO string input round-trip

When a Public API write passes a DTO string into domain validation or persistence, trace the actual request parser before treating the DTO value as raw client input:

- Legacy `DTOControl` JSON input goes through `JSON::toXML()` and `APIXML::_loadValue()`, which XML-entity-encodes strings. A client value such as `R&D` therefore reaches the controller as `R&amp;D`; decode it before character-count validation or persistence when the receiving service expects domain text.
- Test special characters at semantic boundaries through the real request path, not a manually constructed DTO. Include a normal value such as `R&D` and a maximum-length value containing `&`, since entity expansion can reject valid input against a character limit.
- Assert the complete request → DTO → validation → persistence → response round-trip. An output serializer such as `FastJSON` decoding entities can make the response look correct while validation counted the encoded representation or persistence stored the wrong value.

#27419 exposed this: 26 ampersands are valid domain text but become 130 DTO characters and fail a 128-character service limit; direct controller tests built DTOs manually and bypassed the transformation.

### Authorization must match the stated contract

For new or changed endpoints, compare every CRUD action's effective rights with the ticket acceptance criteria, not only with sibling controllers. Trace the authorization implementation too: `controller_Master` OR-evaluates `getNeededPrivileges()`, so adding another right broadens access rather than requiring both. Sibling parity is supporting evidence, but it does not override an explicit endpoint contract; surface any discrepancy for resolution.

### Invariants the PR just invalidated (read outside the diff)

The highest-value findings are often in files the PR **doesn't** touch. When a change makes something variable that used to be fixed — a constant becomes user-selectable, one value becomes a list, a singleton becomes per-instance — every unchanged consumer that encoded the old invariant is now a bug.

Grep the newly-variable value's name across unchanged code and check each of:

- **Cache / storage keys** built from a subset of the identity (`sessionStorage`, `localStorage`, memcache, react-query `queryKey`).
- **Equality and dedupe** that assumed uniqueness on the old, narrower key.
- **Resume / retry paths** that reload prior state *before* the new input is consulted.
- **Memo and effect dependency arrays** missing the newly-variable input.

Ask literally: *what did the old code get to assume that it no longer can?*

#27348 made the terminal merchant-selectable, but `useTerminalSaveSession` still resumed a cached save session keyed on `customerId` alone (`terminalSavedCardsService.ts:151-165`), so reopening within the 60s TTL on a *different* reader resumed the old session and prompted the wrong device while the UI named the new one. Neither file was in the diff.

### Model semantic states before reviewing new guards

When a change adds an early return, disables a query, or introduces a new empty state, enumerate the complete state space before judging the happy path:

- Read the input control or model that defines the value. IDs often carry sentinel meanings such as `-1 = all`, `0 = none`, and `> 0 = a real record`; do not reduce them to truthy/falsy or a broad range check without verifying each meaning.
- Trace every cause of a derived empty value. An empty external ID can mean no selection, an explicit "None" selection, an ineligible account, an unmapped record, or a failed lookup. Those states may require different behavior and user-facing copy.
- Build a small cross-product when behavior depends on multiple states: account eligibility × selected value × mapping availability × feature state.
- For every new guard or early return, compare each state with pre-PR behavior. Do not turn a useful degraded path into a dead end merely because an optional filter or enhancement cannot be applied.
- Verify whether each source-domain value can be represented by the receiving API. A valid local filter may have no external equivalent and should not automatically become an integration failure.
- Test semantic states, not only payload shapes. Serialization tests do not prove that `all`, `none`, unmapped, ineligible, and mapped states preserve the intended behavior.

Ask explicitly: *what do `null`, `''`, `0`, `-1`, and positive values mean at the origin; which distinct states collapse into the same derived value; what happened for each state before this PR; and is the operation still useful without the optional enhancement?*

#27375 treated every empty NuORDER seller ID as an unmapped selected vendor. That collapsed "All," "None," an unlinked account, and an unmapped vendor into one dead-end state, removing the previously useful description-only search for some merchants.

### New branch with no test ≠ pre-existing gap

Don't wave a coverage gap away as inherited. Distinguish:

- **Pre-existing gap** — code that already shipped untested. Not this PR's job.
- **New gap** — a branch *this PR introduces* with nothing asserting it. New debt, in scope, even when the test file is untouched by the diff.

A new feature-flag branch is the usual case: nothing asserts that flag-on takes the new path and flag-off preserves the old one.

When you raise it, also find the **mechanical blocker** — the reason a test wasn't trivial to add — so the comment is a patch rather than a complaint. In #27348 that was `hasFeatureMock` resolving the same value for every feature name, which has to become per-feature before the two branches can be exercised independently.

### Failure paths must be distinguishable in telemetry

For every new error or empty state, ask: *if this fires in prod at 2am, can Datadog tell me which cause it was?*

- A branch that collapses "the API failed" into "there's genuinely nothing" is invisible — an outage and a correctly-empty account render identically.
- `useQuery` with `retry: false` and no `onError` swallows the failure entirely. Wire `onError` to `logError` with a `source`, mirroring the nearest sibling handler.
- This is a separate lens from the user-facing copy. A copy split and a missing log line are two distinct findings on the same branch — raising one doesn't cover the other.

### Split helpers when modes provide different guarantees

A boolean mode parameter can make two operations look interchangeable even when callers depend on materially different semantics. When a helper switches between advisory and authoritative behavior (`$forUpdate`, `$lock`, `$strict`, `$includeArchived`), inspect every caller and ask what each one actually needs:

- A guard that only asks whether any matching row exists should use an existence query (`SELECT 1 ... LIMIT 1`), not `COUNT(*)`; adding `LIMIT 1` to an aggregate does not avoid scanning all matches.
- A transactional safety check may need to scan and lock the full indexed range. Do not apply the existence-query optimization if it weakens the gap/range lock that prevents a concurrent insert or update.
- Give operations with different guarantees separate, intention-revealing methods rather than hiding them behind a boolean switch. This prevents a future optimization of the cheap path from silently weakening the locking path.
- Remove public options that have no production caller. Test-only calls do not justify widening an API or combining unrelated contracts.

#27404 combined a cheap `canDelete()` pre-check and an exhaustive `FOR UPDATE` recheck behind `countWorkordersUsingStatus(..., $forUpdate)`. The shared mechanism obscured both the unnecessary full count on the advisory path and the requirement not to short-circuit the locking path.

### React: state applied in an effect paints one frame late

A controlled input whose `value` is assigned by `useEffect` renders once with the pre-effect value. For a `<Select>` that means the merchant sees option 1 flash before the real preselection lands.

Derive it during render (`value={selected ?? preferred}`) rather than relying on the effect. Same class: anything computed via `useEffect` + `useState` that could have been a plain expression.

### Frontend field names: verify against the API assembler, not the mock

A hand-written TS interface and its Jest mock will happily describe a field the API never sends — they agree with each other and with nothing else. When new FE code reads a nested API field (`model.configuration?.someField`), confirm it exists **for the specific types being filtered**:

- Read the assembler (`includes/api/assemblers/…`) and its `switch` on entity type. A field assigned under one `case` is not set for the others, and fallthrough (`// no break`) makes it easy to misread which cases reach which assignment — count the lines, don't eyeball the block.
- Check the DTO schema for those types (`includes/api/dto/dtos/…::getSchema()`) and the terminal config class's `_getExpectedItemKeys()`.
- Note whether the assignment is **conditional** (`if (isset($config['x'])) { … }`). An optional field the FE then filters on (`x && …`) silently drops those records from the list — a real finding even when the field does exist.
- Corroborate against an existing repo fixture of a *real* response, not the PR's own mock.

All of these live in `includes/**`, so all of them must be read at the pinned head SHA. Running four of these checks against a stale tree is one wrong answer four times, not corroboration.

### Public API field mutability: verify the write path

Before asserting that a Public API DTO field is client-writable or identifying it as a collision path, trace create and update input through the corresponding assembler/controller mapping. Cite the first write or rejection guard; schema presence alone is not evidence of mutability.

For legacy or feature-gated endpoints, trace the requested route and API version through controller rewrites or dispatch, then verify the field in the active request and response schemas. A legacy controller or model alone is not evidence that clients can reach or receive the field.

### Don't defer a claim you can check

"Worth checking how often this happens in prod" is where a real finding goes to die. If the answer is derivable from source in this repo, derive it — *"this field is optional"* and *"this field is unset for the types being filtered, so the list is always empty"* are the same investigation, and only the second is actionable.

The failure on the other side is deriving it from the wrong snapshot and posting it as fact. Both are cured the same way: read the source at the pinned ref, and say which ref you read. Where the answer genuinely depends on runtime data you don't have — *does this config key exist on a real paired device?* — that part stays a **question to the author**, not a claim.

## Phase 6 — Produce the verdict

Use this structure in chat:

```markdown
## PR #<num> — <title>

**Author** | **Base** | **Files** (+adds/-dels) | **CI** | **Reviews so far**

---

### Summary
<2-4 sentence executive summary>

### 1. Functionality
<evidence-anchored claim>

### 2. Maintainability
…

[continue through the 8 criteria; skip any that aren't relevant]

### Minor observations (non-blocking)
- **N.M** — <observation>

### Verdict

**<Approve | Request changes | Approve with N follow-ups>.**
```

When there are must-fix items, lead with them in the Verdict so the user sees them first.

**Reconcile the verdict against the existing review state before finalizing.** Cross-check Phases 1–2 and `reviewDecision` (add it to the Phase 2 GraphQL query: `pullRequest { reviewDecision ... }`). If any unresolved thread is an unaddressed must-fix from another reviewer, or the PR sits at `REVIEW_REQUIRED` / carries a `CHANGES_REQUESTED` review, your verdict **cannot** be Approve — surface those threads at the top and defer to them. Never silently re-derive a clean bill over a reviewer's open blocking comment (this is exactly the LSR-38860 miss: an "Approve" issued while an unresolved must-fix thread was open).

## When to switch skills mid-session

- User says "challenge the code" / "intense review" / "would you find anything if you challenge again?" → re-sweep with skepticism; validate against established patterns by grep'ing for them; don't just re-summarize the same review.
- **Round 2+ on a PR you already reviewed** → re-read the changed files cold *before* verifying your own fixes. Continuity is a liability here: once the task becomes "did they fix my three findings?", you stop scanning for new classes of problem, and an independent reviewer will out-find you on the same diff. Treat each round as a fresh pass that happens to know the history.
- User asks for the status of existing threads → switch to `pr-thread-audit`.
- User asks to merge → switch to `pre-merge-do-not-merge-check` first.
- User says "EXCEPTIONALLY comment" → re-read `pr-review-interaction.mdc`; confirm the exact comment text before posting; use HEREDOC + `--input` to avoid shell escaping (see "Useful gh patterns" below).

## Useful gh patterns

### Posting a multi-line comment safely

Multi-line comment bodies with backticks/quotes break in shell interpolation. Write to a temp file and use `--input`:

```bash
cat > /tmp/comment.json <<'EOF'
{"body": "Your\nmulti-line\ncomment here.", "commit_id": "<full-40-char-sha>", "path": "<file>", "line": <n>, "side": "RIGHT"}
EOF

gh api --method POST "repos/merchantos/<repo>/pulls/<num>/comments" --input /tmp/comment.json
```

The `commit_id` MUST be the **full 40-character SHA**, not an abbreviation. The API returns `422 commit_id is not part of the pull request` for abbreviated SHAs. Resolve it with:

```bash
gh api repos/merchantos/<repo>/pulls/<num> --jq '.head.sha'
```

### Anchoring inline comments

Inline comments must point to a line **within a changed hunk** of the diff. If the API returns `pull_request_review_thread.line` error, the line you picked isn't in any hunk — find the closest changed line and anchor there.

### Self-mention in thread-audit scripts

When iterating over unreplied threads, the "me" identity to match against is your GitHub login (e.g. `ls-vincent-maillot`), not the user's IDE name.
