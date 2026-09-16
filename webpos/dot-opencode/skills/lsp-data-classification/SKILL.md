---
name: lsp-data-classification
description: >-
  Data Lake classification for Lightspeed repositories — add or update field
  classifications in `lsp-data-classification-policy` (datasets/*/*.csv), bump
  policy_version, open the PR with the right title prefix (`LSP-XXXXX:`), and
  coordinate approval from the Data Owner on GitHub + lsp-data-devs. Use when
  adding new columns to a classified dataset, reclassifying a field, creating
  a new LSP ticket for a schema change, or responding to a Data Owner review
  comment on an existing PR. Read this before editing any CSV under
  `datasets/` of the classification policy repo.
---

# Data Lake Classification — LSP Data Classification Policy

The repo at `~/Documents/dev/lsp-data-classification-policy` (or wherever it's checked out) holds the field-level classifications that gate access to the Data Lake. This is a **process skill** — most of the value is in the ordering and the anti-patterns, not the CSV mechanics.

## When this skill applies

- You are asked to "classify" / "tag" / "add a label for" fields on a dataset.
- A new column or table was added to webPOS (or another source system) and needs a Data Lake entry.
- A reviewer flagged an existing classification; you need to correct it and re-open the approval flow.
- You are about to touch `datasets/*/*.csv` **or** `metadata.json`.

## Two sources of truth — consult before picking ANY tag

The single most common failure mode is guessing a tag by analogy from a similarly-named but differently-meaning column (e.g. assigning "Identifier" because the column contains an id-shaped value). Before classifying a field, do **both** of these:

1. **Precedent check.** grep for prior classifications of the *same* or a *similarly-purposed* column across all `datasets/*/*.csv`:

   ```bash
   grep -rn '<exact-field-name>\|<conceptual-synonym>' datasets/ | grep '\.csv:'
   ```

   Look at what other tables (any business unit, any dataset) called a field with the same *meaning*. A field that is an in-row internal attempt counter is not the same thing as a field that references another entity. Precedent in one BU is valid precedent for the whole policy — classification tags are cross-BU by design.

2. **Definition check.** Open `taxonomy_index.csv` and read the line for the candidate tag. The column definitions there are more precise than any of your analogies. Typical trap: `General - Internal - Identifier` is defined as a primary/foreign key or other *global reference identifier*, not "any column that looks like an id". If your candidate tag's definition doesn't literally describe the field's purpose, the tag is wrong even if it *feels* right.

If either check contradicts your initial guess, trust the check. The Data Owner's approval flow exists because wrong classifications are expensive to unwind (grant access to a team that shouldn't have it), so getting this right the first time is worth a minute of grepping.

## File-scope rules

| File | Edit? | Note |
|---|---|---|
| `datasets/<bu>_binlog_row/<table>.csv` | yes | This IS the classification. One row per source column. |
| `metadata.json` | local only | Bump `policy_version` locally for validation; CI bumps it on merge — do not ship the bump separately. |
| `datasets/__schema.sql` or any `*.json` under `datasets/` | **NO** | The repo's own `AGENTS.md` says "Ignore all the \*.json files in the dataset directory". Don't edit, don't create, don't reference. |
| `taxonomy_index.csv` | NO (unless Data Owner asks) | Taxonomy is policy-owned. Adding a new tag is a bigger conversation with the Data Owner first. |

## Workflow

1. **Create the LSP ticket first if none exists.** Project `LSP`, type `Task`. Description in the standard order: Context → Scope → Acceptance criteria → Docs/Refs. Reporter should be the author asking for the change, not an auto-created bot user. Use `acli` or a Jira-mutation skill — see your available tools.

2. **Branch from `origin/main`** (or the repo's declared main branch) with the prefix `<LSP-key>-<kebab-summary>`. Never edit `main` directly.

3. **Edit the CSV(s).** Add/replace rows for the affected columns. Keep the existing column order in the file. Use the *exact* tag strings that appear elsewhere in `datasets/**/*.csv` — never invent a near-synonym (e.g. "Identifier (local)" doesn't exist; pick the closest existing tag).

4. **Bump `policy_version`** locally in `metadata.json` so you can run validation. Format is dotted decimal, lowest digit +1 unless the change warrants more.

5. **Run structural validation** against your local tree:

   ```bash
   ./scripts/tool.sh validate --structural
   ```

   (`scripts/validate_for_ci.sh` is just a thin wrapper around this that pretty-prints the result on failure — running it directly gives you cleaner output.)

6. **Open the PR.** Title MUST match the regex `[A-Z]+-[0-9]+:` (enforced by `.github/pr-title-checker-config.json`), e.g. `LSP-17114: Classify e_invoice idempotency_guid and pending_at`. Body follows the repo's PR template; checklist items from the team's standard (usually 4 checkboxes). CODEOWNERS will route it to `@LightspeedData/lsp-data-devs` — do not manually tag reviewers beyond that.

7. **Wait for two kinds of approval**:
   - **lsp-data-devs** review + merge approval from CI.
   - **Data Owner** approval, which arrives as a *GitHub issue comment* on the PR with the literal text `Approved ✅`. Precedent: PR [#1942](https://github.com/LightspeedData/lsp-data-classification-policy/pull/1942). The ticket gets a note like "Data owner approved in GH PR".
   - Only after both, post to the `#data-eng-requests` Slack channel with the PR link + a one-line summary.

8. **On approval**: close the LSP ticket. If the Data Owner pushes back, respond inline on the PR (short, direct, with evidence — the same grep / taxonomy line that convinced you it's right), and re-open after their confirmation.

## Anti-patterns

- ❌ **Guessing tags from column names.** `idempotency_guid` looks like an identifier; the Data Owner will not approve it as one if it's really an internal retry key. Check the definition.
- ❌ **Adding a new tag to the taxonomy on your own initiative** because your field doesn't fit existing ones. That's a Data Owner decision, and they'll prefer you to pick the closest existing tag or open a taxonomy-change discussion first.
- ❌ **Editing files under `datasets/` that are `.json`.** The repo explicitly ignores those.
- ❌ **Shipping the `metadata.json` bump as a separate PR or forgetting it** — CI auto-bumps on merge; your local edit is only for validation.
- ❌ **Opening the PR before running structural validation.** If `--structural` fails, you'll just churn the repo and waste a review cycle.
- ❌ **Merging before the Data Owner posts `Approved ✅`.** lsp-data-devs approval alone does not clear Data Owner sign-off; they're separate gates.

## Reference

- Classification-policy taxonomy definitions: `taxonomy_index.csv` (root of the repo).
- Process doc inside the repo: `AGENTS.md` + `docs/015-pick-a-class.md`.
- Canonical example PR (full approval flow): [#1942](https://github.com/LightspeedData/lsp-data-classification-policy/pull/1942).
- Example LSP ticket that came from a webPOS side change: [LSP-17114](https://lightspeedhq.atlassian.net/browse/LSP-17114) ← [LSR-39478](https://lightspeedhq.atlassian.net/browse/LSR-39478).
