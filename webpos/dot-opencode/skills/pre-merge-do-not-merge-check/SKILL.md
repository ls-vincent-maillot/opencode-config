---
name: pre-merge-do-not-merge-check
description: Before merging or enqueueing any pull request, check the PR's title, body, and labels for a "do not merge" indicator and refuse to proceed if present. Use before any `gh pr merge`, `gh pr ready`, or `enqueuePullRequest` GraphQL mutation.
---

# Pre-Merge "Do Not Merge" Check

Before initiating any merge action on a pull request — `gh pr merge`, marking ready-for-review, or the `enqueuePullRequest` GraphQL mutation — check whether the PR has been flagged as not-yet-mergeable by its author.

## Indicators to check

In order of priority:

1. **Labels** — any label whose name contains `do not merge`, `do-not-merge`, `dnm`, `wip`, `work in progress`, `blocked`, or `hold` (case-insensitive).
2. **PR title** — substring match against the same keywords (e.g. titles starting with `[WIP]`, `[DNM]`, `DO NOT MERGE:`).
3. **PR body** — search for the phrase `DO NOT MERGE` (any casing) appearing as a standalone notice (not in a quoted-block referencing some other PR).
4. **Draft status** — `isDraft: true`. Drafts are inherently not-for-merge.

## How to check

```bash
gh api "repos/<owner>/<repo>/pulls/<num>" --jq '{
  draft: .draft,
  title: .title,
  body: (.body // ""),
  labels: [.labels[].name]
}' | python3 -c "
import sys, json, re
d = json.load(sys.stdin)
keywords = r'(do[\s_-]?not[\s_-]?merge|\\bdnm\\b|\\bwip\\b|work in progress|blocked|on hold)'

blockers = []
if d['draft']:
    blockers.append('PR is a draft')
for label in d['labels']:
    if re.search(keywords, label, re.IGNORECASE):
        blockers.append(f'label: {label!r}')
if re.search(keywords, d['title'], re.IGNORECASE):
    blockers.append(f'title: {d[\"title\"]!r}')
# Match only DO NOT MERGE as a strong standalone phrase in the body
if re.search(r'\\bDO NOT MERGE\\b', d['body']):
    blockers.append('body contains \"DO NOT MERGE\"')

if blockers:
    print('BLOCKED — do not merge:')
    for b in blockers:
        print(f'  - {b}')
    sys.exit(1)
else:
    print('OK — no do-not-merge indicators')
"
```

## What to do when the check fails

**Stop**. Do not proceed with the merge action. Report the finding to the user with:

- Which indicators triggered (label name / title pattern / body match / draft)
- Quote of the relevant text
- Ask explicitly: "Do you still want to merge despite the `do not merge` indicator?"

Do not interpret the indicator yourself — it may be there because:

- The author wants offline review before merge
- A schema deployment is pending (the trigger for the INC-3723 incident with PR #26974 / #26968)
- A dependency PR hasn't merged yet
- The author is iterating and hasn't finalised

The cost of asking once is small; the cost of merging a hold-tagged PR is potentially an incident.

## When to skip this check

- The user is explicitly removing the `do-not-merge` indicator and merging in the same step (still confirm explicitly).
- The PR is the user's own work and they have directly instructed "merge it now" — and you've shown them the check result.

## Failure mode this prevents

The May 19 INC-3723 incident involved merging two data-layer PRs (#26974, #26968) while schema deployments were still pending. Had the author tagged either PR with a `pending-schema-deployment` or `do-not-merge` label as a guard, this check would have refused the merge and triggered a conversation before damage.
