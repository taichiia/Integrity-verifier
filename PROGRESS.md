# PROGRESS

## Baseline

- Commit: 4142989. Centralized themes, used temporary packaging directories, excluded the verifier from self-verification, removed unsupported QSS box-shadow, and added tests (30 passing).

## Round 1

- Leftover: none.
- Candidates: actual-hash column with report export, verifier CLI mode, elapsed-time statistics.
- Selected: actual-hash column with report export (value 5 / cost 2 / risk 2).
- Completed: verifier results show the actual hash column; report export moved to verifier/report.py with actual hashes and summary; STATUS_LABELS is the single source.
- Tests: 36 passing.
- Next: verifier CLI mode.

## Round 2

- Leftover: none.
- Candidates: verifier CLI mode, elapsed-time statistics, QSettings theme memory.
- Selected: verifier CLI mode (value 4 / cost 3 / risk 2).
- Completed: python -m verifier.cli --target <dir> with JSON output and stable exit codes; VerifyWorker moved to shared/verify_worker.py with exclude_paths; embedded config loading extracted to verifier/embedded.py; README CLI section.
- Tests: 46 passing, including subprocess end-to-end.
- Next: verifier elapsed and speed statistics.

## Round 3

- Leftover: none.
- Candidates: verifier elapsed and speed statistics, QSettings geometry/theme memory, target-folder drag-and-drop.
- Selected: elapsed and speed statistics (value 3 / cost 1 / risk 1).
- Completed: live files/sec while verifying, elapsed and rate after completion, reusable format_verify_stats(), and fixed uninitialized _all_results edge case.
- Tests: 50 passing.
- Next: QSettings geometry/theme memory.

## Round 4

- Leftover: the old Builder package still emitted unsupported box-shadow warnings because it predated the baseline fix.
- Candidates: CSV algorithm auto-detection, QSettings geometry/theme memory, target-folder drag-and-drop.
- Selected: CSV algorithm auto-detection (value 3 / cost 1 / risk 1).
- Completed: load_checksum_entries() detects CSV header algorithm and uses fallback for SFV; external-test uses the detected algorithm; Builder Tools menu now switches to Step 3 and starts the external-test flow; added a regression test proving the stylesheet has no box-shadow; removed stale verifier/build/ and .spec artifacts.
- Tests: 55 passing.
- Next: QSettings geometry/theme memory.

## Round 5

- Leftover: none.
- Candidates: QSettings geometry/theme memory, target-folder drag-and-drop, verifier context-menu full-path copy.
- Selected: QSettings geometry/theme memory (value 3 / cost 2 / risk 1).
- Completed: shared/preferences.py provides QSettings reads/writes; Builder and Verifier restore theme and geometry at startup; theme changes save immediately; geometry saves on close; optional settings parameter added without changing default public behavior.
- Tests: 59 passing.
- Next: target-folder drag-and-drop for Verifier.

## Round 6

- Leftover: none.
- Candidates: target-folder drag-and-drop, verifier context-menu full-path copy, results in manifest order.
- Selected: target-folder drag-and-drop (value 3 / cost 2 / risk 1).
- Completed: the Verifier target path now accepts directory drops only, ignores file drops, emits a target-path signal, clears stale results and speed state, and shows a visible drop hint.
- Tests: 62 passing, including directory-only drag acceptance, drop path setting, and result-state clearing.
- Next: verifier context-menu full-path copy.

## Round 7

- Leftover: none.
- Candidates: verifier context-menu full-path copy, results in manifest order, multi-checklist support.
- Selected: verifier context-menu full-path copy (value 3 / cost 1 / risk 1).
- Completed: result rows now have a Copy Full Path context action; it combines the selected relative path with the configured target directory and writes it to the clipboard.
- Tests: 63 passing, including full-path composition from target directory.
- Next: results in manifest order.

## Round 8

- Leftover: none.
- Candidates: results in manifest order, multi-checklist support, JSON report export.
- Selected: results in manifest order (value 3 / cost 2 / risk 1).
- Completed: Verifier records the embedded manifest order and sorts completed results by that order; extra files remain after manifest entries; target-path drops reset the order state.
- Tests: 65 passing, including manifest-order sorting and completion-order-to-display sorting.
- Next: multi-checklist support in Verifier.

## Round 9

- Leftover: none.
- Candidates: multi-checklist support, JSON report export, window title verify status.
- Selected: multi-checklist support (value 4 / cost 2 / risk 2).
- Completed: Builder now passes named verifier checklists and the active checklist; PackWorker embeds the active checklist's entries plus all named lists; Verifier populates its checklist combo, switches entries and active state, clears stale results, and locks the combo during verification.
- Tests: 67 passing, including active-checklist embedding and Verifier checklist switching.
- Next: JSON report export.

## Round 10

- Leftover: none.
- Candidates: JSON report export, repository shortcut in Help/About, Builder Step 2 manifest state repair.
- Selected: JSON report export (value 4 / cost 1 / risk 2), with the repository shortcut and Step 2 UX repair.
- Completed: Verifier can export a machine-readable JSON report with target path, per-result fields, status labels, and summary counts; Builder Help/About now has a repository shortcut; Builder Step 2 now shows the full PEND/ERR manifest immediately after starting and updates entries by normalized path, preventing a stuck PEND state; ProgressPanel font constant import repaired.
- User simulation: Builder Step 2 was exercised through scan, selection, step navigation, and Start; successful files become OK and a file missing during hashing becomes ERR. Verifier JSON export, export cancellation, and the About repository shortcut were also exercised.
- Tests: 75 passing, including real UI-flow tests for Step 2 and UI-level tests for JSON export and About.
- Next: Round 11 code review and safety pass.

## Round 11

- Leftover: none.
- Candidates: result-model reset aliasing, shortcut registration, table-model reset aliasing.
- Selected: result-model reset aliasing and keyboard registration (value 4 / cost 1 / risk 1).
- Completed: Verifier and Builder table models now replace their internal lists on clear instead of mutating shared caller-owned lists; Builder registers all three step shortcuts instead of only Ctrl+3.
- Tests: 78 passing, including aliasing regressions and step-shortcut registration.
- Next: Round 12 performance pass.

## Round 12

- Leftover: none.
- Candidates: indexed manifest updates, ScanWorker batching, HashWorker batching.
- Selected: indexed manifest updates (value 4 / cost 2 / risk 1).
- Completed: Builder Step 2 now maps entries to manifest rows and updates one finished line directly instead of rebuilding and rescanning the full manifest for every file.
- Tests: 79 passing, including a 100-entry indexed manifest update and row-level verification.
- Next: Round 13 UI validation pass.
