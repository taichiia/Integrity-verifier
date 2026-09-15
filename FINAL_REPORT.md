# Final Report

## Scope

This report covers the full iterative improvement cycle for the Builder and Verifier desktop application. The completed flow contains 13 feature and hardening rounds after the baseline, followed by code review, performance, and UI validation rounds.

## Final State

- Round 13 feature commit: `8820e9c Round 13: result typography validation`.
- Final test suite: `python -m pytest tests -q`, 80 tests passing.
- No uncommitted working-tree changes are included in this report.
- The temporary packaging flow uses `TemporaryDirectory`, with separate `build` and `spec` work paths; it does not leave `build_temp` or top-level `.spec` artifacts in the repository.
- The packed verifier and pre-pack simulation exclude the Verifier executable from "extra" results.
- The application stylesheet does not emit unsupported `box-shadow` properties.
- `PROGRESS.md` is stable UTF-8 English content.
- Builder Help/About has a direct repository shortcut.

## Round Summary

1. **Baseline.** Centralized themes, moved packaging work to temporary directories, excluded the verifier from self-verification, removed unsupported QSS, and restored a test suite. Baseline had 30 passing tests.
2. **Round 1.** Added actual hashes to Verifier results and centralized report generation in `verifier/report.py`. Added CSV, TXT, and shared status-label support. Tests: 36 passing.
3. **Round 2.** Added `verifier.cli` with stable exit codes and JSON output, moved shared verification into `shared/verify_worker.py`, and extracted embedded-config loading. Tests: 46 passing, including subprocess end-to-end.
4. **Round 3.** Added live files/sec and elapsed/rate statistics to Verifier and fixed an uninitialized results edge case. Tests: 50 passing.
5. **Round 4.** Added CSV algorithm detection, wired external-test from the Builder Tools menu, added a stylesheet regression test, and cleaned stale build artifacts. Tests: 55 passing.
6. **Round 5.** Added QSettings-backed theme and window geometry persistence for both applications without changing existing public constructors. Tests: 59 passing.
7. **Round 6.** Added directory-only drag-and-drop to the Verifier target path and reset stale result state. Tests: 62 passing.
8. **Round 7.** Added Copy Full Path to result context menus. Tests: 63 passing.
9. **Round 8.** Added embedded-manifest ordering while keeping extra files after manifest entries. Tests: 65 passing.
10. **Round 9.** Added named verifier checklists and active-checklist embedding through the Builder and Verifier. Tests: 67 passing.
11. **Round 10.** Added machine-readable JSON report export, an About repository shortcut, and the Builder Step 2 PEND/ERR state repair. Real UI flow tests covered scan, selection, Start, manifest updates, missing files, JSON export, cancellation, and the repository shortcut. Tests: 75 passing.
12. **Round 11.** Fixed shared-list mutation on table-model clear and registered all Builder step shortcuts. Tests: 78 passing.
13. **Round 12.** Added indexed manifest updates so each finished file updates one row instead of rebuilding the whole manifest. Tests: 79 passing.
14. **Round 13.** Made Verifier path/hash columns use the shared mono font and corrected the export tooltip to name JSON. Tests: 80 passing.

## Key Decisions

- `STATUS_LABELS` is the single source for result labels so reports and UI do not drift.
- File hashing remains chunked, with mmap only for files larger than 1 GB.
- Worker threads handle hashing and scanning; UI threads only receive results and update state.
- Step 2 keeps an explicit pending/error manifest at start and updates by normalized paths, which prevents stale state and path-case mismatches.
- Table models replace their internal lists on clear rather than mutating lists owned by callers.
- Performance work focused on the largest visible hot path: per-file manifest updates in Step 2.
- UI work kept one shared Ant-inspired theme and used existing Qt components rather than adding heavy dependencies.

## Verification

- Final suite: 80 passing tests.
- Final compile check: `python -m compileall -q builder shared verifier tests`.
- Real user-path simulation: Builder Step 2 was driven through scan, selection, navigation, Start, successful manifest updates, and missing-file error state.
- Verifier simulation: JSON export and export cancellation were exercised through the UI, and the About repository action was exercised through its button.
- Existing tests cover CLI end-to-end, crypto, checksum files, project persistence, preferences, drag-and-drop, context actions, checklist embedding, report generation, and UI state transitions.

## Known Residual Risks

- The user-facing desktop UI has automated Qt tests rather than a full visual regression suite.
- Packaging was regression-tested in the baseline, but the final report does not include a new compiled-binary artifact.
- For very large target directories, the directory scan still emits individual file signals; Step 2 display updates are now indexed, but scanner signal batching remains a possible future optimization.

## Rollback

Each iteration was committed independently. To roll back a specific round, use the matching commit from `git log`:

```bash
git revert 8820e9c
git revert 96350b7
git revert c94bbdd
git revert 9edc01b
git revert 3c311b9
git revert 74c033d
git revert c5776bd
git revert 6a4485d
git revert 0a8b36d
git revert e4154a5
git revert 61afd26
git revert 855cfa7
git revert 188b018
```

Revert in reverse chronological order if rolling back multiple rounds. The baseline remains `4142989`.
