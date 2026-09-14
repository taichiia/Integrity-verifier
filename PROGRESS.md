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
