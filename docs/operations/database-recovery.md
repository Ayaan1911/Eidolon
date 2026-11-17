# Database checkpoint and migration recovery

Traps and alerts live in Neon Postgres. The Mirror does not persist its scan results;
the browser dossier is separate and is cleared on reload.

## Verified checkpoint and rehearsal

The operator created and checked this branch chain on 16 November 2026:

| Branch | Parent | Purpose |
|---|---|---|
| `production` | existing root | Live application database |
| `eidolon-before-0002-2026-11-16` | `production` | Pre-migration checkpoint, expiration disabled |
| `eidolon-migration-check` | checkpoint branch | Isolated copy used for the rehearsal |

Both child branches included current schema and data. The operator ran
`backend/rehearse_migration.py` against the direct migration-check endpoint and reported:

```text
PASS: 0001 -> 0002 -> 0001 -> 0002.
Data preserved: 2 traps, 3 alerts.
Unique finding index verified. No production connection was used.
```

The helper compares every field in both tables after each migration operation, not
just row counts. It prints counts and outcomes, without printing rows, connection
strings, passwords, or data fingerprints. The final revision on the test copy is `0002`.
It takes a PostgreSQL table lock for the rehearsal and runs the whole cycle in one
transaction; a failure rolls that test transaction back.

After the production deployment, the operator confirmed `/health` and `/ready` at
`e8ae5c3`, authenticated alert history still visible after refresh, and logout returning
to demo mode. A later source-only CI fixture correction was merged in PR #9; that change
does not add another database migration.

This verifies recovery from the checkpoint into a child branch and migration behavior
on that copy. It does not verify an independent dump/restore, provider/account loss
recovery, or a recurring backup schedule. The checkpoint is a fixed point in time;
production writes made after its creation are not part of it.

## Before another migration

1. Identify the Neon project and branch actually used by the live Render service.
   Check these privately; do not paste or commit its connection string.
2. Pause application writes for the migration window. Keep the existing production
   branch and the signing secrets intact.
3. Create a named checkpoint branch with **Current data** and disable expiration.
   Record its parent and creation time, then create a separate test child from it.
4. Test the migration on the test child, compare the copied rows before/after, and
   verify the resulting Alembic revision and schema. Never rehearse a downgrade on
   production or on the preserved checkpoint.
5. Apply the reviewed release only after the copy passes. Verify the live commit,
   `/ready`, and existing history before resuming writes.

The current helper is deliberately specific to migration `0002` and the verified
`eidolon-migration-check` endpoint. It rejects other hosts, pooled endpoints,
connection options that could override the host, and connections without required TLS.
It does not accept a production URL from `.env` or `DATABASE_URL` as an input.
It also refuses noninteractive input or a terminal that cannot hide the password.

For the existing checkpoint rehearsal, run from an interactive PowerShell terminal:

```powershell
cd D:\Projects\Eidolon\backend
..\.venv\Scripts\python.exe rehearse_migration.py
```

Copy only the test child's direct connection URL into the hidden prompt, with
connection pooling off. Do not put it into shell history or chat. A fresh rehearsal
requires a test copy at `0001`; rerunning on the already migrated test branch stops.
If a test child is recreated, its endpoint changes: verify its branch/parent first
and review the helper's pinned target before using it. Do not change the target to
production. Future migrations require a rehearsal updated for their revisions.

## If a release or migration fails

1. Stop further deployment attempts and writes. Read the failure without exposing
   credentials or row contents. Do not delete rows or use `alembic stamp` to bypass it.
2. Check the actually deployed code and live schema. A code rollback does not restore
   database contents. Do not downgrade production as a shortcut to recovery.
3. Create a new recovery child from the preserved checkpoint. Leave both the checkpoint
   and the original production branch intact. Validate the copy's data and schema, and
   test the intended application/migration version against that isolated copy.
4. Before a production cutover, identify which writes since the checkpoint would be
   lost and explicitly decide how to preserve or reconcile them. Reverting to an old
   checkpoint does not merge newer production writes automatically.
5. If the operator chooses the verified recovery copy, change Render's database
   connection privately, deploy compatible code, and check `/ready` and retained
   history. Keep the old production branch available for reconciliation.

Recovery cutover was not performed in the verification above. No new production
trap triggers or notification deliveries were used as recovery tests.

Neon reference: [Manage branches](https://neon.com/docs/manage/branches).
