---
name: datacrud-to-dtocontrol-migration
description: Behavioral-parity migration playbook for moving an R-Series public-API controller from DataCrudControl to DTOControl. Use when refactoring a controller, planning a V1→V2 endpoint cutover, or reviewing a DTOControl migration PR. Covers the 5 traps that silently break parity (reload, relation loading, _hide_fields, relation filtering, delete-as-archive).
---

# DataCrudControl → DTOControl Migration

DataCrudControl does significant implicit work (post-save reload, relation loading, field hiding). DTOControl requires each behavior to be explicit. Plan as **behavioral parity**, not structural — the goal is byte-identical responses on every CRUD operation.

## Pre-flight (before any code)

1. **Snapshot V1 responses.** Save full JSON for CREATE, READ single, READ multiple (`?load_relations=...`), UPDATE, DELETE. This is your parity contract.
2. **Audit V1 controller properties:**
   - `$_load_relations` → readSingle default relations
   - `$_create_load_relations` → create response relations
   - `$_update_load_relations` → update response relations
   - `$_hide_fields` → fields hidden from output
   - `$_hide_fields_read_example` / `$_hide_fields_write_example` → example endpoints
3. **Audit V1 overrides** — custom logic in `create`, `update`, `delete`, `readSingle`.
4. **Audit the model** for DB-defaulted fields (`DEFAULT`, `AUTO_INCREMENT`, `CURRENT_TIMESTAMP`) — they won't be in the in-memory object after `store()`.

## Trap 1 — Post-persistence reload

DataCrudControl auto-reloads via `_reloadCommitData()`. DTOControl does not. After `store()`, your in-memory model lacks any DB-defaulted fields.

```php
$id = $this->_getRepository()->store($model);
$model = $this->_getRepository()->getByID($id);  // explicit reload
```

## Trap 2 — Relation loading semantics

DataCrudControl's `$_load_relations` **always loads**. DTOControl's `$_load_relations` only declares what's **allowed** — nothing is loaded by default. Override `readSingle` to match V1:

```php
public function readSingle($entityID, array $searchParams = []): ?controller_ViewInterface
{
    $data = $this->_getData($entityID, $searchParams);
    $data->loadRelations(['Relation.SubRelation']);
    $dto = $this->_getDTO($data);
    return $this->_getView($dto);
}
```

Leave `readMultiple` to the parent — it delegates to `LoadRelationsParser`.

## Trap 3 — `_hide_fields` → assembler guards

DTOControl has no `_hide_fields`. Empty relations serialize as `""` in XML, which is a parity break.

```php
// In the assembler — skip empty relations
if (!safeCount($model->Relation)) {
    return;
}
```

## Trap 4 — Relation filtering

DataCrudControl controllers filter dirty data (e.g. deleted linked records) before serialization. In DTOControl this belongs in the assembler.

```php
foreach ($model->Relations as $relation) {
    if (!isset($relation->LinkedEntity)) {
        continue;  // linked record was deleted
    }
    // ...
}
```

## Trap 5 — Delete = archive

If V1 archives instead of deleting, V2 must use the read schema (not the delete schema) and return the post-archive object:

```php
public function delete($entityID): ?controller_ViewInterface
{
    $model = $this->service->archive((int) $entityID);
    $dto = $assembler->createDTO($this->_getReadOutputSchema(), $model);
    return $this->_getView($dto);
}
```

## Verification

- Diff V2 responses against the V1 snapshots field-by-field for every CRUD operation.
- Test both with and without `?load_relations=`.
- Test with empty relations — confirm no `""` strings or null collections leak through.

## Reference

[LSR-36677 lessons doc](https://lightspeedhq.atlassian.net/wiki/spaces/~patrick.picher/pages/2537521162) (Patrick Picher).
