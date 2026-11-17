# Remaining release work

Updated November 17, 2026. This is the current backlog; [learning notes](docs/learning/eidolon-notes.md) retain the historical implementation record.

- [x] Merge the reviewed hardening changes and synchronize the laptop.
- [x] Repair the local Python environment and run backend/frontend verification.
- [x] Deploy security headers and production API-doc restrictions; verify live responses.
- [x] Verify admin refresh/logout, unauthorized alert rejection, upload limits and partial scan reporting. Remove the CI-fixture false positive at its source.
- [x] Rehearse migration recovery on a Neon child branch and document safeguards. This covers the tested branch checkpoint; independent off-site backup/account-loss recovery and scheduled backups remain outside that result.
- [x] Rewrite setup/demo documentation and document the current threat model. Publication and CI of these latest changes are pending.
- [ ] Verify current end-to-end notification delivery in an agreed test scope. A stored visit does not prove a push arrived.
- [ ] Add and validate Docker/Compose development packaging (historical roadmap Pass 6).
- [ ] Choose and implement the differentiator, or explicitly defer it with a documented release scope (historical roadmap Pass 10).
- [ ] Complete the final browser/mobile/keyboard accessibility walkthrough and record any fixes.

See the [README](README.md), [threat model](docs/security/threat-model.md) and [database recovery runbook](docs/operations/database-recovery.md). Implementation, CI success and production verification are separate claims; do not turn this list into a percentage without defining the release scope.
