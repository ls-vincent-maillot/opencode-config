---
name: r-series-feature-toggles
description: Module and feature toggle patterns for R-Series webPOS — how to gate code by per-account modules, how to check them from PHP/Smarty/TypeScript, and how to test both states. Use when adding, removing, or testing a feature flag, or when reviewing a PR for missing/leaked toggle checks.
---

# R-Series Feature Toggles

R-Series uses an internal **Modules** system for per-account feature flags, gating code paths across PHP, Smarty templates, and TypeScript. Modules are internal-only (not customer-facing) and should have a limited lifetime — either fully roll out or remove.

Two complementary APIs coexist:

- **`helpers\Modules`** — legacy constant-based identifiers.
- **`FeatureToggles\Features`** — modern typed toggle framework with auto-generated methods from `ToggleName`.

## Checking a module

### Backend (PHP)

```php
\login_state::hasModule(\helpers\Modules::MODULE_NAME);                          // most common
\LS\Retail\Framework\FeatureToggles\Features::hasModuleName();                   // typed, auto-generated
\LS\Retail\Framework\FeatureToggles\Features::toggle(ToggleName::MODULE_NAME())->isOn();  // explicit
$login_state->hasModule(\helpers\Modules::MODULE_NAME);                          // instance form (rare)
$modules->hasModule($systemCustomer, 'module.name');                             // direct repo (rare, in services)
```

### Backend (Smarty)

```smarty
{if $login_state->hasModule(helpers\Modules::MODULE_NAME)}
{if isset($account_modules['module.name']) && $account_modules['module.name']}
{if $features::hasModuleName()}
{if $login_state|has_xxx_module}            {* custom modifier, module-specific *}
```

### Frontend (TS / JS)

```typescript
window.lsCloud.Modules.hasModule('module.name');     // legacy synchronous
import Modules from 'shared_modules/Modules';
Modules.hasModule('module.name');                     // synchronous wrapper

// React props from Smarty (synchronous):
// data-react-props='{"hasFeature": {if $login_state->hasModule(...)}true{else}false{/if}}'

// /admin/features API — async; forces the whole call path async. Use only when no Modules constant exists:
import { hasFeature } from 'root/api/admin/features';
if (await hasFeature('FeatureName')) { ... }
```

## Key files

| File | Purpose |
|---|---|
| `includes/helpers/Modules.class.php` | `public const MODULE_NAME = 'module.name';` |
| `src/Framework/FeatureToggles/Features.php` | `@method static bool hasModuleName()` accessors |
| `src/Framework/FeatureToggles/Config/DefaultProvider.php` | `$features->bind(ToggleName::MODULE_NAME(), ...)` |
| `src/Framework/FeatureToggles/ToggleName.php` | Enum entries per module |
| `assets/js/lsCloud/common.types.ts` | `ModuleName` union (synchronous modules) |
| `assets/js/api/admin/features.ts` | `Feature` union + async `hasFeature()` / `getFeatures()` |
| `includes/plugins/modifier.has_xxx_module.php` | Custom Smarty modifier (if one exists) |

## Cleanup (rolling out / abandoning a module)

1. Grep **all 5 PHP patterns + 4 Smarty patterns + 3+ TS patterns** above. A missed call site silently leaks the old behavior.
2. Keep one branch and delete the other:
   - Fully rolled out → keep the optimized path, delete the legacy fallback.
   - Stalled / abandoned → keep the legacy path, delete the new code.
3. Remove the module from every key file in the table above.
4. Update or remove affected tests.
5. After release: remove the module via RAD on STG, then PROD.

## Testing both states

Use `booleanProvider` + `FeaturesContext` to parameterize over `[true, false]`:

```php
#[DataProvider('booleanProvider')]
public function testBehavior(bool $enabled): void
{
    $this->bindContext(new FeaturesContext([
        ToggleName::MODULE_NAME => $enabled,
    ]));
    // assert behavior in both states
}
```

`booleanProvider` lives on the root `TestCase`. Use `setUp()` with a fixed `FeaturesContext` when the whole test class assumes one state.

## Review-time check

A flag-gated PR is incomplete unless the gate is checked at **every** call site — verify by grepping the module constant / toggle name and confirming each call site has the check (or is intentionally unconditional). One missing check at one call site silently leaks the new behavior even when the module is off.
