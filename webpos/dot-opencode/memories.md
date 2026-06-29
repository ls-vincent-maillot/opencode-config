# Personal Memories (migrated from Cursor user rules)

These are personal, project-scoped guidelines for the webPOS / R-Series repo.

## Sort-Sensitive Files: Verify Order After Conflict Resolution

`DIC.config.php` (and other alphabetically-sorted config files) have automated tests that fail when entries are out of order. When resolving a "keep both" merge/rebase conflict in such a file, **do not trust the order the conflict markers presented** — conflict markers preserve insertion source order (HEAD vs incoming), not alphabetical order. After resolving, re-sort the affected section.

Either:
- Compare FQCNs character-by-character before committing, or
- Run `make sort-dic-config` (or the project's equivalent) and stage the resulting diff.

**Common offenders:** `DIC.config.php` (keys sorted by class FQCN, `testDicConfigIsSorted`), translation files, service registrations, autoloader maps.

**Verification checklist before committing a conflict resolution in a sorted file:**
1. Identify the sort key (class FQCN, string key, file path, etc.).
2. Compare the resolved adjacent entries character-by-character — especially when class names share a long prefix (e.g. `EInvoiceLogRepositoryInterface` < `EInvoiceRepositoryInterface` because `L` < `R` at character 9).
3. If the project has an automated sort command, run it and stage the result.
4. Don't rely on CI to catch it — verify locally.

## Backend Code Must Be UI-Agnostic

Backend code — domain classes, data models, repositories, services, schema docblocks — must not reference UI concepts, design language, wireframe names, or screen flows. UI changes; backend contracts don't.

**Forbidden in backend code/comments:** wizard step numbers (`Wizard step 1`), screen names (`Settings page`, `Send Invoice modal`), tab/button/modal labels, design-doc references (`see Figma`), "X shown on screen Y" mappings, phrases like "wizard snapshot" / "form field".

**Allowed:** domain concepts (company info, banking details, primary identifier, status, audit trail), behavioural notes ("auto-updated by MySQL"), cross-BE references by class name (`CheckStorecoveReadinessJob`).

Test: would this comment still be correct if the wizard becomes a single-page form, or the feature gets a standalone API client? If not, it's UI-coupled — rewrite it.

## Code Comments — Conciseness and Convention

Comments must be short, relevant, and consistent with what already exists.

- **Short**: one sentence per docblock or inline comment.
- **Relevant**: explain *why*, not *what*. Don't restate the property name, method signature, or framework-wide behavior.
- **No restatement in `@property`**: if the property is `$createTime` and the type is `Carbon|null`, no description needed. Only annotate properties whose meaning isn't obvious (enum-backed strings, semantic conventions, self-references).
- **Match existing section markers**: use the class's existing conventions (`// Fields`, `// Foreign keys`, `// Relations`, `// Children`). Don't invent new sub-sections (`// Lifecycle`, `// Audit`).
- **Keep framework gotchas**: comments explaining non-obvious framework behavior stay (e.g. `$nullable_fields` is required because `bs_table` coerces `null` to `''`).
