# AI Edit Log

> **Draft note:** Claude Code drafted these entries from the session transcript and git history on 2026-11-23. Every failure, finding and fix below really happened and can be traced in `git log`. Rewrite the entries in your own words and add anything you change after your own review before you submit.

This log records how the Flashcard Quizzer was built with an AI coding agent: what was asked, what the agent produced, what went wrong, and what changed as a result.

**AI tool used throughout:** Claude Code (Claude Opus 5.5) in the Claude desktop app, working in the project folder with permission to run the test and lint tools.

**Workflow:** I gave Claude the full project brief (mission, instructions and rubric) and asked for a plan before any code. After answering its clarifying questions and approving the plan, I chose a "one pass" build: Claude built the app phase by phase, ran the tests and every quality tool after each phase, reviewed its own code against `ai_guidance/code_review_checklist.md`, and fixed what it found. Each phase is a separate git commit.

---

## 2026-11-23 - Turning the brief into a plan (and finding the gaps)

**Context:** Before generating any code I wanted the requirements broken into small phases, with any ambiguity in the brief settled first.

**AI Tool Used:** Claude Code, plan mode (read-only)

**Prompt/Request:** I pasted the whole brief: the mission, the "Building the Flashcard Quizzer" instructions with the phases, required tests and Definition of Done, and the rubric. The plan mode setup asked Claude to explore the starter and propose a plan before editing anything.

**AI Response:** Claude read every starter file and checked the environment. It found that the machine has only Python 3.9.6 (`/usr/bin/python3`) and no `python` command, although the brief's commands all use `python`. It also found that none of the quality tools were installed. Instead of guessing, it asked me four questions:
1. The brief lists a `--stats` flag but never says what it does, while the end-of-quiz summary is required anyway. What should `--stats` do?
2. Which extra features should be added for the rubric?
3. Who drafts the log and report?
4. Should it stop for review after each phase, or build in one pass?

**Changes Made:** My answers shaped the plan:
- `--stats` became a **lifetime history** report, and adaptive mode uses the same history to ask previously missed cards first.
- Extras: **CSV/JSON export** (through a second Factory) and **`--limit N`**.
- Claude would draft all docs for me to rewrite, and build in one pass with a self-review.

Claude added its own defaults to the plan, which I accepted: a `venv/` (as the starter README advises on a personal machine), Python 3.9-compatible syntax, a stdlib-only app, and a trimmed `requirements.txt`.

**Reasoning:** An undefined flag is exactly the kind of gap an AI fills with a confident guess. Settling it up front meant the design, tests and docs all agreed. The trimmed requirements list removes seven packages the app never uses (sphinx, sphinx-rtd-theme, pre-commit, safety, requests, click, pydantic), which makes installation faster for anyone grading the project.

**Outcome:** An approved plan with six phases, a module layout, the behaviour of every flag, and a test list that includes the six required test names.

**Lessons Learned:**
- Asking for a plan first surfaced a real ambiguity (`--stats`) and an environment problem (no `python` command) before any code depended on them.
- A good clarifying question comes with options and a recommendation, which made each decision quick.

---

## 2026-11-23 - Data layer: loader, validation and the first tooling surprise

**Context:** Phase 1 of the plan: load decks in both JSON formats and reject bad decks with a friendly message instead of a traceback.

**AI Tool Used:** Claude Code

**Prompt/Request:** From the approved plan: "Loader accepts `[{...}]` or `{"cards": [...]}`. Friendly `FlashcardLoadError` (one line, names file and 1-based card number) for: missing file, path is a directory, unreadable, file over 5 MB, non-UTF-8, malformed JSON (with line/column), wrong top-level type, `cards` not a list, empty deck, card not an object, missing/empty/non-string `front` or `back`."

**AI Response:** Claude generated `models.py` (a frozen `Flashcard` dataclass), `utils/file_handler.py` (`read_json` with the size limit, plus `write_json_atomic`), `data_loader.py`, a third deck (`data/git_commands.json`), two broken fixture decks and 39 tests. All 39 passed on the first run, and flake8 and mypy were clean. **isort failed**, though, and not on the new code: it flagged the starter's `.claude/commands/*` scripts. These are Python files without a `.py` extension, which isort finds through their shebang line.

**Changes Made:**
- Added `extend_skip = [".claude"]` to the isort config, with a comment explaining why. These scripts are course tooling, not app code.
- A test simulates the "unreadable file" case by patching `Path.read_text` to raise `PermissionError`, rather than using `chmod`, so it behaves the same on every file system.

**Reasoning:** The rubric requires every linting tool to pass. Silencing a whole tool would hide real problems, so only the folder that isn't app code is excluded, and the reason is written next to the setting.

**Outcome:** Commit `4a21000`. The required tests `test_load_valid_flashcards_array`, `test_load_invalid_json` and `test_load_missing_required_field` pass.

**Lessons Learned:**
- Run every tool from the first phase. The isort problem came from starter files, not AI code, and would have been confusing to find at the end.
- Listing each error case in the request produced one test per case, which made coverage easy.

---

## 2026-11-23 - Quiz engine: Strategy, Factory and docstring examples that were never run

**Context:** Phase 2: implement `QuizMode` as an abstract base class, with three strategies and a Factory that picks one from the `--mode` string.

**AI Tool Used:** Claude Code

**Prompt/Request:** From the plan: "`QuizMode` ABC with abstract `next_card()` and overridable `record_answer(card, correct)`. One constructor signature so the Factory can build any mode. Adaptive: initial order sorted by lifetime misses; a wrong answer re-queues the card 2 positions ahead; each card repeats at most 2 extra times (guarantees termination). Cards tracked by position so duplicate cards don't collide."

**AI Response:** Claude wrote `quiz_engine.py` (the strategies, a `QuizModeFactory` whose `register` decorator builds a registry, and `QuizSession` as the Strategy context), `stats.py` and 50 more tests. They include a test that registers a brand-new "reverse" mode without touching the factory, which proves the extensibility claim. All tests passed, but **black wanted to reformat 2 files, and flake8 reported 4 lines over 88 characters**. Two of those lines were inside docstring examples, which black never wraps.

**Changes Made:**
- Ran black, then rewrote the two long docstring examples by hand.
- Added `tests/test_docstrings.py`, which runs every docstring example as a doctest. Nothing had been checking that the examples were true, so they could have drifted silently from the code.
- Kept the repeat cap in adaptive mode. "Repeat until correct" sounds friendlier, but a user who doesn't know an answer would then be stuck in an endless quiz.

**Reasoning:** Documentation that is never executed is a common source of AI errors that look plausible. Running the examples makes them part of the test suite.

**Outcome:** Commit `a90e8f4`, with 89 tests passing. `test_quiz_mode_factory` and `test_adaptive_mode_behavior` pass. For the adaptive test, a missed card in a 4-card deck comes back after exactly two other cards (`A, B, C, A, D`).

**Lessons Learned:**
- Formatting tools fix code but not docstrings, so long examples need a manual fix.
- Termination is a requirement worth stating explicitly for any "repeat" behaviour.

---

## 2026-11-23 - CLI integration tests: 10 failures, 2 real bugs

**Context:** Phase 3: argparse CLI, coloured console UI, lifetime history, exporters and `main.py`, plus integration tests that play whole quizzes through `main()` with scripted answers.

**AI Tool Used:** Claude Code

**Prompt/Request:** From the plan: flags `-f`, `-m`, `--stats`, `--limit`, `--export`, `--history-file`, `--seed`, `--no-color`; "Typing `exit`/`quit`, Ctrl+D or Ctrl+C ends the quiz cleanly: partial summary, history saved, exit 0"; "Corrupt history file → warning and fresh start, not a crash"; "Export failure → friendly error after the summary, exit 1".

**AI Response:** Claude generated the CLI layer and a smoke run worked. While planning the tests it noted two places it suspected, and wrote tests aimed at them. The first integration run then gave **10 failures out of 34**:
- **Bug 1:** if `--history-file` pointed at a directory, the loader warned correctly, but `save()` then *renamed the user's directory to `somefolder.bak` and wrote a file in its place*. The "back up the corrupt file" logic checked `path.exists()` when it should have checked `path.is_file()`.
- **Bug 2:** JSON export created missing parent folders (through `write_json_atomic`), but CSV export failed on them. Two exporters behind one factory behaved differently.
- **Test mistakes (8 failures):** seven assertions hard-coded the summary table's padding, such as `"| Total Questions |     1 |"`. The padding changes with the widest value, and `100.0%` widened the column. One adaptive test also supplied a wrong final answer, so the card correctly came back a third time.

**Changes Made:**
- `HistoryStore.save()` now renames only regular files. A directory is left untouched, the write fails with `OSError`, and `main` shows "Could not save history".
- `CsvExporter` creates missing parent folders, like the JSON exporter.
- Added a `summary_value()` helper that reads values from the table with a regex, and corrected the adaptive test's answers.

**Reasoning:** Bug 1 could destroy user data, which is the worst kind of error-handling bug, because the code was trying to be careful. The test fixes were about testing behaviour, not formatting, so the tests can't break on a harmless layout change.

**Outcome:** Commit `f8bab2a`. All 123 tests passed, and adding unit tests for history sanitising, colour detection and table errors brought the suite to 167 tests with 100% line and branch coverage. `test_full_session` answers three questions (right, wrong, right) and checks Total 3, accuracy 66.7% and the missed term, both in the printed table and in the exported JSON.

**Lessons Learned:**
- Defensive code needs tests for its unusual inputs. The bug sat inside the "handle a corrupt file safely" path itself.
- A failing test is not always a code bug: 8 of these 10 were mistakes in the tests themselves. Each failure needs reading before anything is "fixed".
- Scripted answers for adaptive mode have to account for repeats. An early smoke run got out of step for the same reason.

---

## 2026-11-23 - Quality pass: formatter, linter, type checker and security lint

**Context:** Phase 4 of the plan: every tool in the Definition of Done must pass on the whole codebase.

**AI Tool Used:** Claude Code

**Prompt/Request:** From the plan: "Quality pass: black, isort, flake8, mypy, bandit, coverage".

**AI Response:** The first full run found: **black** would reformat 5 files; **flake8** reported 12 lines over 88 characters; **mypy** found a real typing error in `ui.py`, where the summary rows mixed `str` and `int` cells and were inferred as `list[object]`, which doesn't match `format_table`'s `Sequence[Sequence[object]]`. **bandit** was clean. Then a shell loop Claude wrote to re-run the tools reported black, isort, flake8 and mypy as FAIL. The cause was the loop itself: zsh doesn't split a variable into words, so the tools never ran.

**Changes Made:**
- Applied black, which also cleared the flake8 errors, and annotated the rows as `list[list[object]]`.
- Re-ran bandit with `--ignore-nosec` to check whether the two `# nosec B311` comments were needed. Both suppress a real warning about using `random` to shuffle cards, so they stayed, each with a comment explaining that shuffling flashcards is not a security use of randomness.
- Ignored the loop's false FAILs and ran each tool on its own command line to get real results.

**Reasoning:** A suppression comment should be justified and proven necessary, or it hides future problems. A check that reports failure without running the tool is worse than no check.

**Outcome:** black, isort, flake8, mypy (with `disallow_untyped_defs`, so every function is typed, tests included) and bandit all pass.

**Lessons Learned:**
- mypy found a type mismatch that no test would catch, because the code worked at runtime.
- Check the checker: a surprising result from a script deserves a second look before acting on it.

---

## 2026-11-23 - Self-review against the code review checklist: 3 findings

**Context:** With all tests and tools passing, Claude reviewed its own code with `ai_guidance/code_review_checklist.md`, especially "unvalidated input", "edge cases" and "what could go wrong with this code?".

**AI Tool Used:** Claude Code

**Prompt/Request:** From the plan: "self-review with the checklist; fix findings."

**AI Response:** Three issues that the 167 passing tests didn't cover:
1. **A card whose answer is `exit` or `quit` couldn't be answered.** The exit check ran before grading, so a correct answer ended the quiz.
2. **Terminal escape injection.** Cards are printed straight to the terminal, so a deck from an untrusted source could include control characters such as `\x1b]0;…\x07` and rewrite the user's terminal (this one comes from the checklist's security section).
3. **Stale `--stats` rows.** History is keyed by card front, so cards removed from a deck still appeared in its lifetime report.

**Changes Made:**
- `ConsoleUI.ask` treats `exit`/`quit` as a stop command only when it isn't the correct answer.
- The loader rejects `front`/`back` text that contains control characters (Unicode category `Cc`: tabs, line breaks, escape codes), with a message that names the card.
- `--stats` lists only cards that are still in the deck.
- Added 6 tests. To prove they test the fixes, Claude stashed the three fixed source files and re-ran the tests on the old code: 5 of the new tests failed, as they should. The sixth, non-ASCII text such as `Straße`, is a guard that passes either way. With the fixes restored, all 173 passed.

**Reasoning:** Passing tests only prove the cases someone thought of. A structured review asks the questions the tests didn't. Checking that new tests fail without the fix shows they test the fix rather than pass by accident.

**Outcome:** Commit `bcb777d`: 173 tests, 100% coverage, all tools clean.

**Lessons Learned:**
- The checklist's security questions found an issue (escape codes in data) that no requirement mentioned.
- Making a test fail on purpose is a cheap way to trust it.

---

## 2026-11-23 - Documentation from real output

**Context:** Rewrite the README, write this log and draft the report.

**AI Tool Used:** Claude Code

**Prompt/Request:** From the plan: README with features, setup, usage for every flag, deck format, architecture diagram and quality commands; the log from what actually happened; a 1,000-1,500 word report; a text coverage report because `htmlcov/` is gitignored.

**AI Response:** Claude ran the app to capture a real session and a real error message for the README, counted lines, classes and tests from the code, and saved the real coverage output to `docs/coverage_report.txt`. It wrote Mermaid class and flow diagrams and checked the report's length with `wc -w`.

**Changes Made:** The README example session was adjusted only to show the typed answers, which a terminal displays but piped input does not.

**Reasoning:** Documentation built from real runs can't promise features or numbers the code doesn't deliver.

**Outcome:** README, this log, `docs/report.md` and `docs/coverage_report.txt`.

**Lessons Learned:** Asking for the evidence (command output, counts) instead of a description keeps AI-written docs accurate.

---

## Summary Statistics

- **Total AI interactions:** 7 logged interactions over one session: 1 planning prompt with 4 clarifying questions, then 6 build/review phases, each committed separately
- **Lines of AI-generated code used:** about 3,060 (1,538 application lines and 1,522 test lines). All code was generated by the AI; per the brief, problems were fixed by re-prompting or review, not by hand-editing
- **Lines of AI-generated code modified:** 125 lines added and 26 removed in the quality and review commit (`bcb777d`), plus the two bug fixes and test corrections in the CLI commit (`f8bab2a`)
- **Most helpful AI interaction:** the clarifying questions before any code, especially defining `--stats`
- **Most challenging AI interaction:** the 10 integration failures, which had to be sorted into 2 real bugs and 8 test mistakes
- **Biggest lesson learned:** green tests are not the finish line. The checklist review still found 3 real issues after 167 tests passed.
