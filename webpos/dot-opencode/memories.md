# Personal Memories

Personal, project-scoped guidelines for the webPOS / R-Series repo. Originally migrated from
Cursor user rules; extended 2026-08-07 with the Claude Code memory store.

Cross-project memories live in `~/.config/opencode/memories.md`.

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

### Over-documentation is a review finding

`.opencode/rules/pr-review-substance.mdc` §2 governs comment density here. It flags three things:

1. Multi-line comments on trivial / one-line helpers ("6 lines for a 1-line method is abusive").
2. Comments that restate the code — the *what*, not the *why*.
3. JIRA ticket IDs in code; git blame is enough, unless tagging a real TODO.

**How to apply:** before cutting, measure the sibling file's density — the e-invoicing domain runs ~29% comment lines in `src/` and ~10% in `tests/`, and `MerchantRegistrationServiceTest.php` uses `// ---- register() ----` banner separators. Match the neighbour rather than stripping to zero; `match-existing-code-conventions.mdc` cuts the other way. A one-line `return Features::x()` helper needs no docblock at all.

### State what is true, don't narrate the history

Write comments as statements of current fact, not explanations of the steps that led to the current design. Banned shapes: "used to X", "X 4xx'd for every merchant", "instead of Y", "previously", "no longer", "how a stuck merchant recovers", "pre-toggle flow".

Rewrite by asking "what is true?" instead of "why did we change this?":

- ✗ `A Peppol identifier is globally unique, so claiming one 4xx'd for every merchant already registered elsewhere — so under the flag the identifier half drops out instead of parking at pending_approval.`
- ✓ `Under \`e_invoicing.sender_only\` the merchant onboards as a sender: no identifier is derived or registered, and a successful Storecove call activates outright.`

**Why:** the history belongs to git blame and the PR description. In the code it drifts out of date, and it costs the reader the fact they actually came for.

**How to apply:** it is still fine to state a *mechanism* or *constraint* that isn't visible in the line below ("'' not null: a null write is skipped by the legacy mapper", "only createLegalEntity is stubbed: any identifier call fails the mock"). The test is whether it describes the system as it stands versus the journey to it. Cut length first, then cut narration.

## Agent Routing and Repo Rules

Before editing/running anything in `/Volumes/dev/webPOS`, read `AGENTS.md` (routing file) and load the matching handlers it points to — `.agents/*.md` (e.g. `php-conventions.md`, `branches-and-prs.md`) and `.opencode/rules/*.mdc`. Skipping it has caused a rule violation.

**Single source of truth (consolidated 2026-07-27):** agent **skills and `.mdc` rules** live once under `.opencode/{skills,rules}`; `.cursor/{skills,rules}` and `.claude/skills` are symlinks to it — edit `.opencode/...` and every tool sees it. When a task matches a repo skill, read it from `.opencode/skills/` (reviewing a webPOS PR → `review-webpos-pr` + `pr-thread-audit`; data-layer PR → `review-data-layer-pr` + `r-series-data-layer-conventions`).

**Never embed a JIRA/`LSR-` ticket ID in a code comment** unless it tags a real planned `TODO` (`.opencode/rules/pr-review-substance.mdc` — "git blame is enough"). Commit messages and PR bodies SHOULD carry the ticket; markdown design docs (gherkin, jira-outline) reference tickets by their own convention — the ban is specifically **code comments**. **Why:** user is strict on this; confirmed 2026-07-16. **How to apply:** grep added code for `LSR-`/ticket IDs in comments before committing; reword to drop the ID (or make it a `TODO`).

**There is a second, user-global layer above this one** — don't declare a convention "missing" after searching only the repo. opencode reads `~/.config/opencode/AGENTS.md` and `~/.config/opencode/memories.md`. That's where the **agent-artifacts storage convention** lives: write reports/audits/scratch SQL to `~/Documents/AgentFiles/<TICKET-ID>/<descriptive-name>` (or `<YYYY-MM-DD-HHMM>-<keyword>/` with no ticket), **never** inside a repo — and its hard rule #2 forbids copying that convention into any project rule file.

`.opencode/.gitignore` is `*` (except `.gitignore`), so everything here is personal and untracked — teammates don't have these files. Never reference `.opencode` paths from a team-tracked file such as `.claude/CLAUDE.md`.

## Reviewing a GitHub PR

Do these BEFORE concluding:

1. **Pull the existing review state first** — not just `gh pr view` / `gh pr diff`. Fetch threads + decision via GraphQL (`reviewThreads{isResolved, comments}`, `reviews{state,body}`, `reviewDecision`). Lead the write-up with any unresolved / "must fix" comments. Never silently re-derive and risk missing or contradicting a reviewer, and never report "Approve" while the PR sits at `REVIEW_REQUIRED` with unresolved blocking comments.

2. **Trace the full data round-trip, and diff against sibling code** — bugs hide where a value crosses a layer, not at the render site. For each field a change touches: (a) follow it end to end (an in-memory model read vs a DB read-back can differ in encoding / normalization / null-vs-empty), and (b) check how the nearest sibling handler in the SAME module treats the same field. A guard/decode/normalize the neighbours all do but this change omits is a top bug class. A security-only lens (XSS/leak) is not enough — over-encoding (mangled display) and cross-endpoint inconsistency matter too.

**Why:** on PR #27307 both failures happened at once — a reviewer's must-fix comments were missed (threads never pulled) and the underlying bug was missed too: a persisted `errorMessage` came back HTML-entity-encoded and would render as `&quot;...`, while sibling transformers in the same directory already decoded it. The conclusion "React escapes it, safe" was true for XSS and still wrong, and it was marked Approve while blocked.

## Legacy Data Layer Entity-Encodes Strings

The legacy data layer (`bs_table` / `data_Base` / `StaticFieldBase` mapper) **HTML-entity-encodes string fields on write**, so a string column read back from the DB round-trips **entity-encoded** (`"`→`&quot;`, `&`→`&amp;`, `<`→`&lt;`). Before exposing a persisted string to the frontend/API, decode it with `cust_html_entity_decode()`.

- Established precedent (e-invoicing module): `EInvoicingStatusTransformer::rejectionReason()` and `EInvoicingShopOptionTransformer::nullableString()` both call `cust_html_entity_decode()` for exactly this reason, documented in their docblocks.
- Related gotcha: these legacy string columns return `''` (never `null`) for NULL values, so `$x->field !== null` guards on them are dead code — treat `''` as absent.
- Failure mode if you skip the decode: a persisted JSON blob (e.g. an `errors[]` array) renders as `[{&quot;source&quot;:...}]`; and an **in-memory** model read returns the RAW string while a **DB** read-back returns the ENCODED one → the same record shows differently across endpoints.

## TIMESTAMP vs DATETIME and the Shop Timezone

Every DB connection runs `SET time_zone = login_state::getTimeZone()` (`ConnectionMaker.class.php:395` → `Connection.class.php:517`), which resolves to the **shop's** timezone (`$_shop_time_zone ?: SYSTEM_TIMEZONE`). Consequences when touching date columns:

- **`TIMESTAMP` columns**: MySQL interprets the literal you send in the connection timezone. Writing a `Carbon::now(SYSTEM_TIMEZONE)` string stores an instant off by `shop_offset − LA_offset`. Always write `Carbon::now(login_state::getTimeZone())`. `SYSTEM_TIMEZONE` is `America/Los_Angeles` (`Bootstrappers/Timezone.php:13`), so bugs of this shape are invisible on US-West shops and on every LA-defaulted test.
- **`DATETIME` columns**: stored verbatim; they hold the shop's *wall clock*.
- **Comparing the two in SQL requires `CONVERT_TZ`** on the DATETIME side. The helper is the `reports_shop_timezone` trait (`includes/gui_defs/reports/traits/`), which no-ops unless `login_state::multiShop()` — safe, because single-shop accounts have session TZ == shop TZ by construction.
- `bs_datetime::resetTo()` (`includes/bs_datetime.class.php:116-170`) deliberately skews its internal epoch so `toSQLString()` renders shop-local wall clock. Code using it is already correct — don't "fix" it.
- `DateTimeTransformer::toBSValue` uses `SYSTEM_TIMEZONE` only for `create_time` and `time_stamp`, and `login_state::getTimeZone()` for everything else, so data-layer writes are correct. Direct `bs_table` writes bypass it.

To detect already-corrupted TIMESTAMP data, session-TZ-independently:

```sql
UNIX_TIMESTAMP(ts_col) <> UNIX_TIMESTAMP(CONVERT_TZ(datetime_col, shop.time_zone, @@session.time_zone))
```

Testing this needs a shop outside `America/Los_Angeles` **and** the connection pointed at it (`SET time_zone`) — `TransactionalTestCase` seeds shop 1 as `America/Los_Angeles`, where every such bug reads as zero skew.

## Cash Rounding Behaviour

Feature `REGISTER_SALES_CASH_ROUNDING` + account option `CASH_ROUNDING_ENABLED`; `src/Domain/CashRounding/CashRoundingService.php`.

- **Default rule = `nearest_increment_midpoint_up` @ denomination `0.05`** for every cash-rounding currency (AUD, CAD, DKK, EUR, NZD, USD — `includes/config/currencies.php`): round to nearest 0.05, exact midpoint goes up. Merchants *can* override rule/denomination via `CASH_ROUNDING_RULE`/`CASH_ROUNDING_DENOMINATION` (also `always_round_down|always_round_up|nearest_increment_midpoint_down`), but none ship as default. Max |delta| under nearest-0.05 is 0.025.
- Example: **11.59 → 11.60** (1¢ up), not 11.55. `delta = total − rounded = 11.59 − 11.60 = −0.01`. **Negative delta = customer pays MORE (rounded up); positive = pays less (rounded down).**
- For a completed pure-cash rounded sale the settling cash payment is recorded at the **rounded** amount: `calcPayments = 11.60`, `balance = −0.01` (sale completes sitting at balance == delta), and the cash SalePayment carries the same delta (`amount 11.60`, `cashRoundingDelta −0.01`). Non-cash payments show delta 0. Delta is written on both transaction and cash payment (`applyCashRoundingDelta`).
- Refund is the **exact negation** of the sale (the refund path mirrors original payments, it doesn't recompute): sale delta −0.01 → refund delta +0.01, rounded total −11.60, payment −11.60/+0.01.
- **API serializer strips trailing zeros**: 11.60 serializes as `"11.6"`, −11.60 as `"-11.6"`. `cashRoundedTotal`/`cashRoundedBalance` are Sale-level only; `cashRoundingDelta` is on both Sale and SalePayment (hidden when the feature is off).

**Verification technique (reliable for API-example questions):** add a throwaway method to the transactional tests (`includes/tests/transactional/controller/control/account/SaleTest.php` / `SaleSaleRefundTest.php`), enable rounding via `FeaturesContext`+`OptionsContext`, complete the sale/refund through the controller, then `fwrite(STDERR, $view->write())` to capture the **real serialized JSON**; run with `make -C cli/tester php-test SUITE=transactional TEST_FILE=… FLAGS='--filter …'`, then `git restore` the file. Beats hand-deriving entangled fields (balance/calcPayments/amount).

## Module Grants Are Memcached

`login_state::hasModule()` → `Session::hasModule()` → `AccountModuleService::accountHasModules()` → **`SystemAccountModuleCachingRepository`**, which caches the whole enabled-module list per account under one key with `MODULE_CACHE_TTL_SECONDS = 600`. The cache is only invalidated by that repo's own `enableModuleForAccounts()` / `disableModuleForAccounts()` / `delete()`.

So a manual `INSERT INTO customer.cust_module ...` (or flipping `archived`) is **invisible to the app for up to 10 minutes**, and re-logging in does not help — the cache is per account, not per session. Symptom: a module-gated code path behaves as if the module is off, with no error.

Flush after any manual change:

```bash
docker exec webpos-retail-app-1 php -r \
  '$m=new Memcached(); $m->addServer("retail-memcache",11211); $m->flush();'
```

(`docker exec webpos-retail-memcache-1 sh -c '...>/dev/tcp/...'` does **not** work — that image's `sh` has no `/dev/tcp`.)

Two more things are needed before a module is usable locally:

- A row in `customer.module` (the registry). `hasModule()` resolves the name there first via `bs_module::findValidation`, so an unregistered name is always false. Adding a `helpers\Modules` constant in PHP is **not** enough — registration is a RAD operation, not a code change.
- A row in `customer.cust_module` with `archived=0`. `default_on=1` on the registry row does **not** auto-grant to existing accounts.

Verify what the app actually sees: any page's HTML contains `lsCloud.Modules.setModules({...})` with the live list. Local account map: `cust_customer_id=1` = "Test1" / shop "Test Shop" → per-account DB `cust1`.

## `make clean-code` Needs a TTY

`make clean-code` pipes changed files through `xargs -o`, and `-o` reopens stdin as `/dev/tty` — which agent shells don't have. It dies with `xargs: docker: Device not configured` / `make: *** [clean-code] Error 126`.

Run the same container directly instead (flags must be **separate** args — the Makefile relies on shell word-splitting of a single quoted `FLAGS` variable):

```bash
docker compose --project-directory ./ \
  -f cli/tester/docker/_base.yml -f cli/tester/docker/php-lint.yml \
  run --rm test-runner --no-interaction --show-progress=dots --verbose \
  $(git diff --name-only HEAD~1 --diff-filter=d '*.php' | tr '\n' ' ')
```

Notes:

- `clean-code` hardcodes `SINCE=HEAD~1` via `$(eval ...)`, so it cannot be overridden from the command line.
- Passing paths overrides the compose `command:`, which is where `--dry-run` lives — so this **fixes** files rather than just reporting. That matches `make clean-code`.
- `make check-feature-flags` reports `✘ Not sorted: DefaultProvider.php` on pristine `develop-retail` (a stray double blank line, from `6d8117893d`). Verify against a pristine checkout before assuming your own toggle entry is misplaced. It is not referenced in `.circleci/` or `.github/`, so it is not a merge gate.

## E-Invoicing: Tooling and Verification

Before starting substantive e-invoicing work, read the tooling reference `~/Documents/AgentFiles/LSR-35251/agent-tooling.md` and actually use it. Key sources beyond JIRA+code: the **spec** (`/Volumes/dev/r-series-core-docs/docs/Features/E-Invoicing/` — FR1–FR6, `gherkin-scenarios.md` = canonical acceptance), **local MySQL** (`debugging-mysql-local` skill; container `webpos-retail-database-1`, root/root, per-account DB `cust<RAD_ID>`, system DB `customer`), and the **local app** (`https://rad.localdev/`, test/testtest) for UI-behaviour tickets. Sibling repos are at `/Volumes/dev/` (`r-series-core-docs`, `lsp-data-classification-policy`).

**Why:** confirmed 2026-07-24 — LSR-38863 was implemented from JIRA + code + unit tests without consulting the tooling ref. The spec check then materially reframed the ticket.

**How to apply:** for any e-invoicing ticket, cross-check the spec/gherkin for what's *actually* required, verify column shapes / feature enablement in local MySQL, and for UI-behaviour bugs drive `rad.localdev` to reproduce-then-confirm. The e_invoicing module (id 234) is enabled on local account **cust1**.

**Domain fact:** per FR2 §Validation rules, the canonical **B2B-customer** required fields were originally **company (`customer.company`), invoice email (`contact.email`), `vat_number`, and country-conditional `company_registration_number`** — billing address was only *reused* from `contact.address*`, not required, and the sole gherkin save-validation scenario covered VAT+email. (FR6's per-country "Address" mandatory is the *Merchant* wizard, not the customer.) **LSR-38863 extends this**: `validate_b2b_einvoicing_requirements()` now requires, for B2B e-invoicing customers, **`company` + `vat_number` + valid `contact_id.email` + a complete postal address** — street (`contact_id.address1`, falling back to `contact_id.address2`) + `contact_id.city` + `contact_id.zip`. Country is deliberately NOT presence-checked (governed by VAT/Peppol per-country logic). `company` (→ `party.companyName`) is mandatory under EN16931 BR-07 — verified against Storecove's Swagger (`https://api.storecove.com/api/v2/openapi.json`: `Invoice.required` includes `accountingCustomerParty`; `Address.required=[country]` only, but street/city/zip are "mandatory in most countries"; VAT is NOT Storecove-required, it's our rule + Peppol-id derivation; email is routing). LSR-38411 wants to consolidate all this into `CustomerEInvoicingEligibility`.

## E-Invoicing: Availability Gate

Availability for an account = `Features::hasEInvoicing()`, bound in `src/Framework/FeatureToggles/Config/DefaultProvider.php` to `RequireAllToggle(ModuleToggle(Modules::E_INVOICING), EInvoicingCountryToggle)`. So availability requires BOTH the `e_invoicing` module AND the account country ∈ `E_INVOICING_ALLOWED_COUNTRIES` (global.config.php, `BE` only at launch; `EInvoicingCountryToggle` checks `login_state::getLocale()->getCountryCode()`, fail-closed). Every call site (~20: admin endpoints, `SaleActions` trigger, `SubmitEInvoiceJob`, `CheckStorecoveReadinessJob`, Storecove webhook, customer/transaction UI) goes through `hasEInvoicing()`, so the single binding is the one gate. (Added in LSR-38696 / PR #27304.)

This is ORTHOGONAL to `localization\Locale::supportsEInvoicing()` (true for BE/FR/DE/NL/ES) — that is the Peppol *registration-country* registry (which countries a merchant may register a legal entity in; enforced in `MerchantRegistrationService`, `PeppolVatValidator`, `EInvoicingController::listCountries`), pinned by `EInvoicingLocaleSupportTest` / `EInvoicingCountryControllerTest`. Don't conflate the rollout allow-list with `supportsEInvoicing()`.

**Testing gotcha:** to make e-invoicing available in a test, use `FeaturesContext(['EInvoicing' => true])` (force-binds the toggle, bypassing both module and country) — NOT `ModulesContext([Modules::E_INVOICING])`, which only sets the module and fails the country gate on the default (US) test account. The readiness cron `CheckStorecoveReadinessJob` selects pending rows by status only and evaluates `hasEInvoicing()` inside each account's swapped context, so non-allowed-country accounts are loaded then skipped.

**Front-end gotcha:** the raw module list (`login_state::getModules()`, country-blind) is serialized to the browser (`window.lsCloud.Modules`, e.g. `www/company_branding.php`), so client-side `Modules.hasModule('e_invoicing')` is true for any account with the module regardless of country. To gate e-invoicing UI on the full rule, use the `<RouteIfRights feature="EInvoicing" .../>` prop (async-resolves `/admin/features` → `hasEInvoicing()`), NOT `modules="e_invoicing"`. The `/customers/e-invoicing` route (`assets/js/apps/pages/views/customers/e-invoicing/routes.tsx`) uses `feature="EInvoicing"`.

## E-Invoicing: Line Tax vs Storecove (rounding 422)

`InvoiceMapper` sends `taxSystem = tax_line_amounts` and derives each line's `tax.amount` as **gross − net** (VAT *extracted* from the tax-inclusive gross), while Storecove validates `tax.amount == round2(percentage × amountExcludingVat)` (VAT *applied* to the net). The two disagree by one cent for **`r/(1+r)` of amounts — 17.36 % at BE 21 %** (e.g. €100.00 → we send 17.36, Storecove wants 17.35), producing HTTP 422 `"Tax amount does not equal percentage * amount excluding tax"` → `validation_error`, no retry.

**Why:** the behaviour is deliberate and pinned by `InvoiceMapperTest::testLineTaxReconcilesNetAndGrossToTheCent` — tax was derived as gross−net so `net + tax` equals the total the POS actually charged. For the failing amounts **no** 2-decimal net/tax split satisfies both that and Storecove's check, so this cannot be fixed by re-rounding; Storecove's spec itself recommends `tax_line_percentages`.

**How to apply:** not refund-specific — a plain invoice line at a "bad" amount fails identically. **Careful: this error string is ambiguous.** The refund discount defect below produces the *same* Storecove message from a completely different cause, so never attribute a 422 to rounding without checking the line's actual amount against `r/(1+r)` first — that mistake was made on staging sale 1220 (−€180.00, which is rounding-*consistent*). Full diagnosis and fix options: `~/Documents/AgentFiles/LSR-35251/refund-creditnote-422-tax-mismatch.md`.

## E-Invoicing: Refund Discount Double Sign Flip

A refund line carrying a **fixed-amount** discount whose price rule is `CustomerGetsOption::DISCOUNT_ON_ALL_ITEMS` gets its discount **added** to the refund magnitude instead of subtracted, because two sign conventions compose: `LineCalculatorTrait::getQuantityMultiplier()` returns the **raw negative** quantity (so `getDiscountCalc()` yields `−D·Q`, asserted by `LineCalculatorTraitTest:113-119`), then `FixedCalculator::_calculateDiscount()` negates **again** because the line amount is negative. Result: the live re-price gives `−(P·Q + D·Q)` instead of `−(P·Q − D·Q)` — off by `2·D·Q`.

**Why it matters:** `InvoiceMapper` builds each line from two sources — `amountExcludingVat` from that **live** re-price (`getSubtotalWithAllDiscounts()`), gross from the **persisted** `transaction_line_calc.total` (which is parent-derived at `abs(qty)`, so correct) — and sends `tax = gross − net`. On such a refund the line tax is off by ~`2·D·Q` and usually has the wrong sign, so Storecove 422s with *"Tax amount does not equal percentage * amount excluding tax"* — the same string as the unrelated rounding defect above. Invoices are unaffected: at positive quantity both flips are absent/correct.

**How to apply:** when a credit note 422s on tax, check the line's `discount_id` / `is_percent` / `price_rule.customer_gets_option` before blaming rounding. Discriminator in Datadog: only the broken submission's trace contains `SELECT pr.price_rule_id FROM price_rule pr INNER JOIN discount d`, whose sole origin is `needsQuantityMultiplier()`. Note the mapper re-prices at submission time only because `EInvoiceSubmitter::buildDocument()` doesn't hydrate `SaleLines.Discount` — reading the persisted calc net instead would avoid both defects. `LineCalculatorTrait` is shared with `bs_transaction_line`, so don't "fix" the multiplier without checking every consumer. Evidence, worked example and the confirming SQL: `~/Documents/AgentFiles/LSR-35251/refund-creditnote-422-tax-mismatch.md`.

## E-Invoicing: Prod Storecove Webhook (resolved 2026-08-03)

Two distinct prod-only webhook faults, 2026-07-31 → 08-03, both in the **Storecove dashboard**, neither in our code (nothing in this repo registers the URL or its header). **Both fixed** — first successful prod callback 2026-08-03T18:42:13Z (200, `result: dispatched`, `document_submission.succeeded`, account 313649, host `retail.lightspeedapp.com`), ten minutes after the last 403:

1. **404** — URL was `https://us.lightspeed.app/...`. Not an R-Series vhost: `charts/values.prd.miku.yaml` serves only `*.lightspeedapp.com` + `*.merchantos.com` (`retail-app`), `app-edge.*`, `api*`/`internalapi*`. (`*.retail.lightspeed.app` in this repo is **X-Series/Vend**.) Live host, from access-log `custom.http.referer`: `https://us.merchantos.com`. Don't target `app-edge.*` — that pins webhooks to the canary; staging's callbacks land on `service:retail-app-edge` only because staging `retail-app` runs `istio.edgeRoute.weight: 100` (prod: 50).
2. **403 `invalid secret header`** — the `X-LS-Storecove-Webhook-Secret` header was **not being sent** to prod at all. Prod's `STORECOVE_WEBHOOK_HEADER_SECRET` *was* configured (48 chars), so the "never provisioned / empty env var" theory was wrong.

**Why the staging control matters:** on the identical build, staging's header dump recorded 26 keys **including** `x-ls-storecove-webhook-secret` (→ 200), prod recorded 24 **without** it (→ 403), with the same `cf-*` / `x-envoy-*` / `x-shopkeep-auth-proxy` / `x-ls-delegate` chain in both. That proves Cloudflare → Istio → auth gateway does **not** strip it, so absence means the sender omitted it. Always get the staging control before blaming infrastructure — and before trusting an "absent from the log dump" conclusion, confirm the attribute is actually returned (a query that omits it yields a false negative).

**How to apply:** `"Storecove webhook"` in Datadog distinguishes never-arrived from arrived-and-broke, because the controller logs one INFO (`triggered.`) per verified request **and** a WARNING per rejection; corroborate at nginx with `env:production "/v1/webhooks/storecove"` (raw access lines with method + status). 404 with zero POSTs in our logs = wrong hostname; 403 = reached PHP. Storecove retries non-2xx for ~5 days and never after a 200, so a queued backlog drains itself once fixed — but nothing polls `document_submissions/{guid}/evidence` and there's no reconciliation job, so anything still queued when the window closes freezes at `submitted` with no UI action. Note the public path carries a `/system` prefix the route declaration (`v1/webhooks/storecove`) doesn't show.

⚠ Commit `143701c2da` (#27336, on `develop-retail`) logs `STORECOVE_WEBHOOK_HEADER_SECRET` and the full header map in plaintext — needs reverting + a secret rotation via the `_PREVIOUS` var. Evidence: `~/Documents/AgentFiles/LSR-35251/prod-313649-qa-session-findings.md`.
