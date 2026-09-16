---
name: r-series-data-layer-conventions
description: Framework-specific gotchas and conventions for adding tables, columns, repositories, and models in the R-Series data layer. Use when creating new bs_* classes, data_model_* classes, DatabaseRepository / CachingRepository implementations, or migrating schema.
---

# R-Series Data Layer Conventions

A cheatsheet of framework-specific gotchas that are easy to miss and cause silent bugs or production crashes. Each item is grounded in real defects found in this codebase.

## `$nullable_fields` is mandatory on `bs_*` classes

For every column declared nullable in the DDL, declare it in `$nullable_fields` on the `bs_<table>` class. Without this list, `bs_table::get_field_element()` silently coerces a PHP `null` to the empty string `''` (or `0` for ints) at save time.

Consequences when missing:

- **UNIQUE columns** (e.g. `udx_storecove_guid`) — the second null-save violates the constraint as soon as two rows are saved without a value.
- **JSON columns** — MySQL rejects `''` with `Invalid JSON text: "The document is empty."`.
- **All other nullable columns** — silently store `''` / `0` sentinels in place of NULL, corrupting partial-data saves.

```php
class bs_cust_e_invoicing extends stub_cust_e_invoicing
{
    public $nullable_fields = [
        'storecove_legal_entity_id' => true,
        'storecove_rejection_reason' => true,
        'storecove_onboarded_at' => true,
        // ... every nullable DDL column ...
    ];
}
```

## String columns round-trip HTML-entity-encoded

`bs_table`/`data_Base` **HTML-entity-encodes string columns on write**, so a value read back from the DB is entity-encoded (`"`→`&quot;`, `&`→`&amp;`, `<`→`&lt;`). Anything that exposes a persisted string to the FE/API must decode it with `cust_html_entity_decode()` first, or it renders mangled (a persisted JSON blob shows as `[{&quot;source&quot;:...}]`).

- Precedent: `EInvoicingStatusTransformer::rejectionReason()` and `EInvoicingShopOptionTransformer::nullableString()` both decode for exactly this reason (documented in their docblocks).
- Pairs with the `$nullable_fields` gotcha above: these columns read back `''` (never `null`) for NULL values, so treat `''` as absent rather than guarding on `!== null`. An **in-memory** model read returns the RAW string; only a **DB** read-back is entity-encoded — so the same value can render differently depending on the path.
- Real defect: LSR-38860 exposed `e_invoice.error_message` to the FE on two read paths without decoding.

Reference precedent: `bs_inventory_log` for JSON columns, `bs_e_invoice` / `bs_e_invoice_log` for the e-invoicing tables, `bs_cust_customer` for the system DB.

## Field-type conventions

| DDL column type | `data_model_*` field declaration | `bs_*` type_hints value |
|---|---|---|
| `varchar(N)` | `new data_Base_Field("string")` | `'string'` |
| `text` | `new data_Base_Field("string")` | `'textarea'` |
| `json` | `new data_Base_Field("string")` | `'string'` |
| `int` / `bigint` / `tinyint` (numeric) | `new data_Base_Field("number")` (or `"key"` for FKs) | `'number'` |
| `decimal` / monetary | `new data_Base_Field("money")` | `'money'` |
| `tinyint(1)` boolean | `new data_Base_Field("boolean")` | `'boolean'` |
| `timestamp` / `datetime` | `new data_Base_Field("datetime")` | `'datetime'` |
| `timestamp` auto-create | `new data_Base_Field("datetime", null, null, ["attributes" => ["createtime"]])` | `'datetime'` |
| `timestamp` auto-update | `new data_Base_Field("datetime", null, null, ["attributes" => ["timestamp"]])` | `'datetime'` |

Notes:

- **`"text"` field type is deprecated** per `Field.class.php:270` (TODO marker). The framework treats `"string"` and `"text"` identically — prefer `"string"`.
- **JSON columns use `'string'` (not `'textarea'`) on the `bs_*` type_hint** — this is the codebase precedent (`bs_inventory_log.manifest`, `bs_offending.metadata`). Only TEXT columns use `'textarea'`.

## Pass MyCLabs Enums directly to `Criteria::equals`

The criteria layer coerces MyCLabs `Enum` subclasses on its own. Do **not** call `->getValue()`.

```php
// ❌ BAD — off-convention
->addCriteria(Criteria::equals('status', $status->getValue()))

// ✅ GOOD — matches AccountStatus::DELETE, JobStatus::RUNNING, TaskStatus::PENDING usages
->addCriteria(Criteria::equals('status', $status))
```

Enum classes also need `@extends Enum<T>` in the class docblock so Phan accepts the inheritance:

```php
/**
 * @extends \MyCLabs\Enum\Enum<string>
 */
class StorecoveStatus extends \MyCLabs\Enum\Enum { ... }
```

## `createTime` is not echoed back to the model after INSERT

`bs_table` excludes columns with the `createtime` attribute from the bind list — MySQL's `DEFAULT CURRENT_TIMESTAMP` fills them in. The returned in-memory row does **not** carry the resulting timestamp. If callers need it, they must re-read via `getByID()`. Don't promise `createTime` in the return-type docblock.

## FK annotation conventions in `bs_*` classes

`BsTableStubAnnotationTest` infers the expected `@var` from the column name: a column named `<table>_id` maps to `int|bs_<table>|null` if `bs_table::isDbTable('<table>')` is true; otherwise it falls back to `int|null`.

When the column name doesn't match the target table (e.g. `e_invoice.sale_id` references `transaction`, not `sale`), the test will reject the FK-typed annotation. Add an explicit override:

```php
// tests/Unit/Data/BsTableStubAnnotationTest.php
public const TYPE_OVERRIDES = [
    bs_e_invoice::class => [
        'sale_id' => 'int|bs_transaction|null',
    ],
];
```

## `load_relations` requires an `"object"` field in the model

To pre-load a foreign relation in one query (avoiding N+1):

```php
// In data_model_X._getFieldsDef():
"custCustomerID" => new data_Base_Field("key", "SystemCustomer"),
"SystemCustomer" => new data_Base_Field("object", "SystemCustomer", "custCustomerID"),

// In the consuming query:
$query->load_relations = ['SystemCustomer'];
```

Without the `"object"` field, `load_relations` is a no-op.

## Boolean field assertions in tests

Casting `false` to `(string)` returns `''`, not `'0'`. In tests:

```php
// ❌ BAD — fails because (string)false === ''
$this->assertSame('0', (string) $row->autoSend);

// ✅ GOOD
$this->assertFalse((bool) $row->autoSend);
```

## Append-only repository protection

Blocking writes via `store()` / `delete()` on the `DatabaseRepository` subclass is **insufficient** — multiple paths bypass it:

| Method | Bypass mechanism | Override needed |
|---|---|---|
| `bs_table::saveFields(array)` | Writes via `_do_update` directly, skipping `save()` | Yes |
| `bs_table::saveField(string)` | Delegates to `saveFields` | Yes |
| `DatabaseRepository::bulkStore` / `bulkStoreFields` / `bulkInsert` / `bulkDelete` / `bulkUpdateRelationIDs` | Inherited from parent | Yes — override each to throw |
| `DatabaseRepository::bulkStoreUsingUniqueKey()` | Performs `INSERT ... ON DUPLICATE KEY UPDATE`; could silently mutate | Yes — override to throw |

Mirror the repository's append-only contract on the `bs_*` class:

```php
class bs_e_invoice_log extends stub_e_invoice_log
{
    public function save()       { /* allow INSERT only; throw on PK set */ }
    public function saveFields(array $fields) { throw new LogicException(...); }
    public function saveField(string $field)  { throw new LogicException(...); }
    public function delete(): bool            { throw new LogicException(...); }
}
```

## Upserts on a single row

The R-Series `Query` / `Criteria` abstraction targets SELECT and UPDATE; it has no upsert primitive. Doctrine DBAL's fluent `QueryBuilder::insert()` does not expose `ON DUPLICATE KEY UPDATE`. The parent `DatabaseRepository::bulkStoreUsingUniqueKey()` wraps the right SQL pattern, but is bulk-oriented and adds machinery for a single-row default INSERT.

The minimal correct expression is raw SQL via `executeStatement()`:

```php
$tableName = $this->_getIO()->getTableName();
$this->_getConnection(false)->executeStatement(
    "INSERT INTO `{$tableName}` (`cust_customer_id`) VALUES (?) "
    . "ON DUPLICATE KEY UPDATE `cust_customer_id` = `cust_customer_id`",
    [$custCustomerID]
);
$row = $this->findByCustCustomerID($custCustomerID);
```

This is isolation-independent (the `ON DUPLICATE KEY UPDATE` clause makes the INSERT a no-op when another transaction has already created the row) and survives nested REPEATABLE-READ wrappers.

## Naming write-intent methods correctly

Methods that perform a write (even when wrapped as "idempotent") should not use the `get` prefix — that misrepresents the read/write surface. Patrick's review on PR #26973 made this point explicit:

- ❌ `getOrCreateNotRegistered(int $custCustomerID)` — looks like a read
- ✅ `createNotRegistered(int $custCustomerID)` — explicit write intent
- ✅ `ensureNotRegisteredExists(int $custCustomerID)` — explicit invariant

The return value is a convenience, not the purpose.

## Don't redeclare inherited interface methods

`save()`, `getByID()`, and a few others are inherited from `RepositoryInterface`. Listing them again in `<Type>RepositoryInterface` makes them look like type-specific contracts and is misleading. Only declare methods the subclass actually adds or specialises.
