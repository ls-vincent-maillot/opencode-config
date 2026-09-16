---
name: pr-thread-audit
description: Audit unreplied PR review threads and craft concise replies, distinguishing stale (already-addressed) from new (needs code or substantive reply). Use when triaging open review threads on a pull request, especially after pushing new commits that may have implicitly resolved earlier feedback.
---

# PR Thread Audit

Triage open reviewer threads on a pull request:

1. Identify which threads are still unreplied.
2. Map each to the **current** code state — many old threads are stale, already addressed by later commits.
3. Reply concisely per `pr-reply-style.mdc`.

## Step 1 — Pull all feedback

Three endpoints, all required:

```bash
# Inline (file-anchored) review comments
gh api "repos/<owner>/<repo>/pulls/<num>/comments"

# Top-level reviews (approval / changes-requested / commented summaries — bodies often contain action items!)
gh api "repos/<owner>/<repo>/pulls/<num>/reviews"

# PR-level issue comments (general conversation)
gh api "repos/<owner>/<repo>/issues/<num>/comments"
```

## Step 2 — Identify unreplied threads

```bash
gh api "repos/<owner>/<repo>/pulls/<num>/comments" --jq '[.[] | {id, user: .user.login, in_reply_to_id, body, created_at, path, line: (.line // .original_line)}]' | python3 -c "
import sys, json
comments = json.load(sys.stdin)
replies = {}
for c in comments:
    if c['in_reply_to_id']:
        replies.setdefault(c['in_reply_to_id'], []).append(c)
me = '<your-github-login>'  # e.g. ls-vincent-maillot
for c in [x for x in comments if not x['in_reply_to_id']]:
    my_reply = any(r['user'] == me for r in replies.get(c['id'], []))
    flag = 'REPLIED' if my_reply else 'OPEN'
    print(f\"[{c['id']}] {flag} | {c['user']} @ {c['path']}:{c['line']} | {c['body'][:80]}\")
"
```

## Step 3 — Categorise each open thread

For each unreplied thread, classify before drafting a reply:

| Category | Indicator | Reply pattern |
|---|---|---|
| **Stale — already addressed** | The concern was about code that has since changed in a later commit | `"Done in commit X — <one-line summary of how>."` |
| **Obsolete — file/section removed** | The thread references code that no longer exists | `"File deleted in <commit> — no longer applicable."` |
| **New — needs code change** | The concern is still valid against the current code | Apply the change, then reply with the new commit SHA |
| **New — defensible disagreement** | The concern is valid in principle but the current code is intentional | Push back politely with the reasoning |
| **Misread — reviewer is wrong** | The concern is based on a misreading of the code | Cite the line / behaviour that refutes it, briefly |

## Step 4 — Reply

Apply `pr-reply-style.mdc`: short, direct, with commit SHA when applicable.

```bash
# Reply to inline thread
gh api -X POST "repos/<owner>/<repo>/pulls/<num>/comments/<thread-id>/replies" \
  -f body="Applied in <sha> — <one-line summary>."

# Reply to top-level review (post as a regular issue comment, not a review reply)
gh api -X POST "repos/<owner>/<repo>/issues/<num>/comments" \
  -f body="Tests added per your suggestion in <sha>: ..."
```

## Common traps

### Top-level reviews carry action items

A reviewer posts an **APPROVED** review whose body says:

> "LGTM, please consider adding tests to cover the newly introduced repositories."

The PR badge shows green; the action item is in the body. Always read review bodies even on APPROVED reviews.

### Stale threads from a previous review pass

Pre-existing threads from days/weeks ago may be entirely resolved by later commits. Don't assume — open the file at HEAD and check before replying.

### Don't reply with boilerplate

Each thread asks something different. Tailor each reply to that thread. Reusing the same "Done in <sha>" line for every thread looks lazy and misses nuance (e.g. when the change is partial, or when you're pushing back).

### One pending review per user per PR

REST refuses to create a second pending review for the same user on the same PR (404 or `user_id can only have one pending review per pull request`). To add comments to an existing pending review you must use GraphQL — `addPullRequestReviewThread` — not REST. `addPullRequestReviewComment` (GraphQL) is also wrong here: it takes the old position-based API and rejects `line` / `side`. Always reach for `addPullRequestReviewThread`.

```bash
# Get the pending review's GraphQL node id
gh api graphql -f query='
  query {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <num>) {
        reviews(states: PENDING, first: 1) { nodes { id } }
      }
    }
  }'

# Add a comment thread to it
gh api graphql -f query='
  mutation {
    addPullRequestReviewThread(input: {
      pullRequestReviewId: "PRR_..."
      path: "src/File.php"
      line: 42
      side: RIGHT
      body: "comment text"
    }) { thread { id } }
  }'
```

REST review payloads also have an event-field gotcha: omit `event` for PENDING (the string `"PENDING"` is not a valid value); the valid values are `APPROVE`, `REQUEST_CHANGES`, `COMMENT`.

## Batch posting

Once replies are drafted, fire them in parallel:

```bash
gh api -X POST "repos/.../comments/<id1>/replies" -f body="..." & \
gh api -X POST "repos/.../comments/<id2>/replies" -f body="..." & \
gh api -X POST "repos/.../comments/<id3>/replies" -f body="..." & \
wait
```

(Subject to `no-push-without-approval.mdc` — get the user's go-ahead before posting.)
