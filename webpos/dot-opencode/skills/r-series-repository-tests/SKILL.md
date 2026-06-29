---
name: r-series-repository-tests
description: Write standard tests for R-Series repositories — transactional DatabaseRepository tests, unit CachingRepository tests with MemoryCacheStore, and transactional bs_ class tests for custom behaviour like append-only. Use when adding test coverage for new data-layer classes.
---

# R-Series Repository Tests

Standard patterns for repository test coverage. Three file types, three locations, three base classes.

## Three test types

| What you're testing | Location | Base class | Cleanup |
|---|---|---|---|
| `DatabaseRepository` subclass | `tests/Transactional/Domain/<Area>/<Name>DatabaseRepositoryTest.php` | `tests\transactional\TransactionalTestCase` | Auto-rollback per test |
| `CachingRepository` subclass (unit) | `tests/Unit/Domain/<Area>/<Name>CachingRepositoryTest.php` | `LS\Tests\Unit\UnitTestCase` | n/a (mocked) |
| `bs_*` class with custom behaviour (e.g. append-only overrides) | `includes/tests/transactional/database/bs<Name>Test.php` | `tests\transactional\TransactionalTestCase` | Auto-rollback per test |

Do **not** use `MOSTestCase` for `bs_*` tests that mutate data — it isn't transactional, so changes leak across tests.

## Transactional `DatabaseRepository` test pattern

```php
namespace LS\Tests\Transactional\Domain\<Area>;

require_once('data/Collection.class.php');
require_once('data/model/<Name>.class.php');

use data\connection\CurrentConnectionsProvider;
use services\Service;
use tests\transactional\TransactionalTestCase;

class <Name>DatabaseRepositoryTest extends TransactionalTestCase
{
    private function repo(): <Name>DatabaseRepository
    {
        return new <Name>DatabaseRepository(
            Service::get(CurrentConnectionsProvider::class)
        );
    }

    public function testImplementsInterface(): void
    {
        $this->assertInstanceOf(<Name>RepositoryInterface::class, $this->repo());
    }

    public function testFindByXReturnsRowWhenPresent(): void
    {
        // Seed with new data_model_X() + repo()->store($row), or use a helper.
        // Use __LINE__ for unique IDs to avoid collisions across tests in
        // the shared test DB.
        ...
    }
}
```

## Unit `CachingRepository` test pattern

Use a **real** `MemoryCacheStore` (don't mock the cache too — testing through the abstraction makes the test fragile). Mock only the backing repository.

```php
namespace LS\Tests\Unit\Domain\<Area>;

use LS\Retail\Framework\Caching\MemoryCacheStore;
use LS\Tests\Unit\UnitTestCase;

class <Name>CachingRepositoryTest extends UnitTestCase
{
    private function makeCachingRepo(
        <Name>RepositoryInterface $backing,
        ?MemoryCacheStore $cache = null,
    ): <Name>CachingRepository {
        $backing->method('getModelType')->willReturn('<ModelName>');
        return new <Name>CachingRepository($backing, $cache ?? new MemoryCacheStore(0));
    }

    public function testFindByXCachesPositiveLookup(): void
    {
        $backing = $this->createMock(<Name>RepositoryInterface::class);
        $backing->expects($this->once())          // hit once across two calls
            ->method('findByX')
            ->willReturn($row);

        $repo = $this->makeCachingRepo($backing);
        $repo->findByX(100);
        $repo->findByX(100);                       // served from cache
    }
}
```

Common cases worth testing:

- Positive lookup caches (backing repo called once across N reads)
- Null result is **not** cached (refute cache-poisoning concerns)
- Write methods invalidate the cache
- Methods that bypass the cache (e.g. paginated iterators) hit the backing repo on every call

## Transactional `bs_*` test pattern (append-only)

```php
namespace tests\transactional\database;

require_once('database/bs_<table>.class.php');

use bs_<table>;
use tests\transactional\TransactionalTestCase;

class bs<Name>Test extends TransactionalTestCase
{
    public function testInsertAllowedWhenNoPrimaryKey(): void
    {
        $row = new bs_<table>();
        $row-><required_col> = __LINE__;
        $row->save();
        $this->assertGreaterThan(0, $row-><pk>);
    }

    public function testSaveFieldsThrowsAlways(): void
    {
        $row = new bs_<table>();
        $row-><required_col> = __LINE__;
        $row->save();
        $row-><col> = 'mutated';

        $this->expectException(LogicException::class);
        $this->expectExceptionMessage('append-only');
        $row->saveFields(['<col>']);
    }

    // ... testSaveFieldThrows, testDeleteThrows, testSaveThrowsOnUpdate
}
```

## `dataProvider` for parametrised forbidden-method tests

PHPUnit 10 attribute syntax. One test method + N data rows beats N near-identical tests:

```php
public static function appendOnlyMethodsProvider(): array
{
    $existing = new data_model_<Name>();
    $existing->setPrimaryId(1);
    $collection = new data_Collection('<Name>', [$existing]);

    return [
        'store' => [fn ($repo) => $repo->store($existing)],
        'delete' => [fn ($repo) => $repo->delete($existing)],
        'bulkStore' => [fn ($repo) => $repo->bulkStore($collection)],
        // ... bulkStoreFields, bulkInsert, bulkDelete, bulkUpdateRelationIDs,
        //     bulkStoreUsingUniqueKey
    ];
}

#[\PHPUnit\Framework\Attributes\DataProvider('appendOnlyMethodsProvider')]
public function testAppendOnlyMethodsThrow(Closure $invoke): void
{
    $this->expectException(LogicException::class);
    $this->expectExceptionMessage('append-only');
    $invoke($this->repo());
}
```

## Scope discipline — don't extravagate

Bochuan's reviewer note was explicit: tests should be **standard and relevant**, not exhaustive. For a typical repository:

- ✅ Happy path for each public method
- ✅ Critical edge cases (input validation, append-only enforcement, cache invalidation)
- ✅ One `dataProvider` test covering all forbidden-method paths
- ❌ Tests for inherited framework methods (`getByID`, `runQuery`) — that's framework coverage
- ❌ Trivial getter/setter tests
- ❌ Multiple permutations of the same happy path

Roughly: 1 test per public method + 1-3 tests for critical invariants.

## PHPUnit hygiene (applies to every test)

Independent of the repository-test layer, the project's baseline rules:

- **`assertSame` over `assertEquals`** — strict comparison by default. `assertEquals` only when you specifically want loose comparison (rare in this codebase).
- **`assertEqualsWithDelta($expected, $actual, 0.001)` for floats** — never compare floats with `assertSame`.
- **`ErrorCheckingTestCase`** exists as a base class for unit tests that need to assert on triggered errors / warnings; reach for it instead of `@expectedDeprecation`-style hacks.
- **`booleanProvider`** lives on the root `TestCase` — `[true]` / `[false]` rows for parameterizing both branches of a flag-gated method (most common in feature-toggle tests; see `r-series-feature-toggles`).

## Running tests locally

```bash
# Single test file
docker exec -w /web/cloud webpos-retail-app-1 \
  php -d memory_limit=512M vendor/bin/phpunit \
  /web/cloud/tests/Transactional/Domain/<Area>/<Name>DatabaseRepositoryTest.php

# Annotation regression sweep (always run before pushing data-layer changes)
docker exec -w /web/cloud webpos-retail-app-1 \
  php -d memory_limit=1024M vendor/bin/phpunit -c tests/phpunit.xml --testsuite=src_unit --no-coverage \
  --filter='BsTableStubAnnotation|DataModelAnnotation'
```

## Bug-catching value

Real production bugs caught by writing tests for the e-invoicing PRs:

- **PR #26974**: `bs_e_invoice` missing `$nullable_fields` — UNIQUE constraint violation on second null-GUID save.
- **PR #26975**: `bs_e_invoice_log` missing `$nullable_fields['details']` — MySQL rejected `''` for the JSON column on every null-details `recordEvent()`.

Both were latent until the tests exercised the null path. Writing one happy-path-with-nulls test per nullable column would have caught them without the bug class reaching production.
