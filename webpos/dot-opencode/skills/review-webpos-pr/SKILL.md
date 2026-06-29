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

## When to switch skills mid-session

- User says "challenge the code" / "intense review" / "would you find anything if you challenge again?" → re-sweep with skepticism; validate against established patterns by grep'ing for them; don't just re-summarize the same review.
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
