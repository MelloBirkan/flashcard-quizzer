# AI-Assisted Development Project Report

> **Draft note:** Drafted by Claude Code from the session record. Rewrite it in your own words, especially the Reflection and Learning sections, and fill in your name before you submit.

**Student Name:** [Your Name]
**Project Title:** Flashcard Quizzer CLI
**Date:** 2026-11-23

## Executive Summary

I built the Flashcard Quizzer, a command-line tool that loads flashcards from JSON and quizzes the user in sequential, random or adaptive order, with green/red feedback and an end-of-session summary. On top of the brief it keeps a lifetime history per deck (`--stats`), exports sessions to CSV or JSON, and can limit the number of questions.

I didn't write the code by hand. I directed Claude Code: I gave it the full brief, answered its clarifying questions, approved a phased plan, and had it test and review every phase. The result is 1,538 lines of application code and 173 tests with 100% coverage. black, isort, flake8, mypy and bandit all pass.

## Project Overview

### Problem Statement
New hires need to memorise many acronyms. A lightweight terminal tool that drills them, and focuses on the ones they keep missing, is quicker to use than a spreadsheet and easy to extend.

### Solution Approach
- **Layers:** `data_loader` (validation), `quiz_engine` (logic, no I/O), `ui` (all input and output) and `main` (wiring and exit codes), plus `history`, `exporters`, `stats` and small `utils` modules.
- **Patterns:** Strategy for quiz modes; Factory for creating modes and exporters.
- **Stack:** Python 3.9 standard library only; pytest, black, isort, flake8, mypy and bandit for quality.

### Final Features
- [x] Loads both deck formats, with one-line errors and no tracebacks
- [x] Sequential, random and adaptive modes; case- and whitespace-insensitive matching
- [x] Summary table: total questions, accuracy, missed terms
- [x] `exit`, Ctrl+D and Ctrl+C stop cleanly with a partial summary
- [x] Lifetime history, `--stats` report, history-aware adaptive mode
- [x] CSV/JSON export with formula-injection protection; `--limit`; `--seed`; `--no-color`

## AI Collaboration Experience

### AI Tools Used
- [x] Claude (Claude Code, Opus 5.5)

### Collaboration Workflow
1. **Plan first.** In read-only plan mode, Claude explored the starter and asked four questions before writing anything.
2. **Small phases.** Data layer, engine, CLI, quality pass and docs, each one a commit.
3. **Validate everything.** After each phase, the tests and every tool ran, and the failures were read before anything changed.
4. **Structured review.** A final pass against the course checklist looked for problems the tests didn't cover.

### Most Valuable AI Interactions

#### Example 1: Clarifying `--stats`
**Context:** The brief names a `--stats` flag but never defines it.
**AI Prompt:** The full brief, with a request to plan before coding.
**AI Response:** Claude asked what `--stats` should do and offered two designs.
**Your Changes:** I chose lifetime history, which also gave adaptive mode its memory of previous sessions.
**Outcome:** One decision shaped three features consistently.

#### Example 2: The directory-renaming bug
**Context:** Corrupt history files should be backed up, not crash the quiz.
**AI Prompt:** "Corrupt history file → warning and fresh start, not a crash."
**AI Response:** The code backed up anything at the history path, including a directory, then replaced it with a file.
**Your Changes:** A test pointing `--history-file` at a folder exposed it, and the backup now only renames regular files.
**Outcome:** A data-loss bug caught before anyone hit it.

#### Example 3: Checklist review after green tests
**Context:** 167 tests passed with 100% coverage.
**AI Prompt:** Review the code against `ai_guidance/code_review_checklist.md` and fix the findings.
**AI Response:** Three issues: a card answered "exit" ended the quiz, decks could inject terminal escape codes, and `--stats` showed deleted cards.
**Your Changes:** All three were fixed, and the new tests were shown to fail on the old code.
**Outcome:** 173 tests, and evidence that coverage is not the same as correctness.

### Challenges with AI Collaboration
- **Plausible but unverified details.** Docstring examples were never executed until a doctest runner was added.
- **Tests can be wrong too.** Eight of ten integration failures were test mistakes: hard-coded table padding, and an answer script that ignored adaptive repeats.
- **Environment assumptions.** The brief assumes a `python` command. This Mac only had `python3` 3.9, which ruled out newer syntax.

## Software Engineering Practices

### Code Quality Measures
- [x] Code formatting (Black, isort)
- [x] Linting (flake8, mypy)
- [x] Type hints, enforced by mypy's `disallow_untyped_defs`, tests included
- [x] Documentation (Google-style docstrings with tested examples)
- [x] Error handling (custom exceptions with user-safe messages)

### Testing Strategy
- Unit tests for each module, and integration tests that drive `main()` with scripted answers and fake terminals.
- The required tests, including `test_full_session`, which checks Total 3 and 66.7% both in the printed table and in the exported JSON.
- Coverage is 100% (line and branch) and fails below 80%.
- Not strict test-driven development, but tests were written in the same phase as the code, and the new tests were shown to fail without their fixes.

### Design Patterns Used
- **Strategy:** `QuizMode` with `SequentialMode`, `RandomMode` and `AdaptiveMode`. Choosing the next card is one task with three algorithms, so `QuizSession` uses whichever strategy it is given and the loop never branches on the mode. A test adds a new mode without changing the factory, which shows the brief's "add Spaced Repetition later" claim holds.
- **Factory:** `QuizModeFactory` maps `--mode` to a class. Its registry also feeds argparse's choices, so a new mode appears in `--help` on its own. `ExporterFactory` uses the same pattern to choose by file extension.

### Code Structure and Organization
The engine does no I/O and the UI does no grading. Streams are injected, so tests never need a real terminal. Refactoring went into the error paths: atomic history writes, one exception type per layer, and consistent exporter behaviour.

## Technical Challenges and Solutions

### Challenge 1: Making adaptive mode end
**Problem:** "Repeat wrong cards" can loop forever if the user never knows an answer.
**Solution:** A wrong card is re-queued two places ahead, at most twice. History also orders the deck by lifetime misses.
**AI Involvement:** Claude proposed the cap in the plan and wrote tests for the order and the cap.
**Lessons Learned:** State termination as a requirement.

### Challenge 2: Safe text from untrusted decks
**Problem:** Card text goes straight to the terminal.
**Solution:** The loader rejects control characters and gives a message naming the card.
**AI Involvement:** Found during the checklist review, not from the brief.
**Lessons Learned:** Security questions find problems that requirements don't mention.

## Code Quality Analysis

### Metrics
- Lines of code: 1,538 application, 1,522 tests
- Test coverage: 100%
- Number of functions/classes: 74 functions and methods, 20 classes
- Linting score: 0 issues from flake8, mypy, black, isort and bandit

### Self-Assessment
- **Code Readability:** 4 - Small modules and plain names, though some tests are long.
- **Code Maintainability:** 5 - New modes and formats plug in through factories.
- **Test Quality:** 4 - Thorough, but heavy on output strings.
- **Documentation:** 4 - Detailed, though I still need to rewrite the drafts in my own voice.

## Learning Outcomes

### Technical Skills Developed
Abstract base classes, registry-based factories, argparse custom types, atomic file writes, pytest fixtures and parametrisation, doctests, and coverage with branch measurement.

### AI Collaboration Skills
Precise requests listing each edge case produced matching tests. Asking for a plan surfaced ambiguity early. The AI's confidence says nothing about correctness: a failing test has to be read before anything is "fixed".

### Software Engineering Insights
Patterns earned their place here because the variation was real: three algorithms and two formats. Separating I/O from logic made the whole app testable.

## Reflection

### What Worked Well
Planning before code, committing each phase, and making the AI prove its claims with tool output.

### What Could Be Improved
I chose a one-pass build. Pausing after each phase to review the code myself would have given me more ownership of each design choice.

### Future Enhancements
A spaced-repetition mode (the factory is ready for it), alternative accepted answers per card, a `--reset-stats` flag and packaging as an installable command.

## Conclusion

AI-assisted development worked best when I acted as specifier and reviewer: I defined behaviour exactly, asked for evidence, and treated every failure as information. I'll keep planning first, committing in small steps and reviewing against a checklist.

## Appendices

### Appendix A: AI Interaction Log
See `docs/ai_edit_log.md`, especially the entries on the integration failures and the checklist review.

### Appendix B: Code Statistics
See `docs/coverage_report.txt` for per-module coverage and `git log` for the phase history.

### Appendix C: Additional Resources
`ai_guidance/code_review_checklist.md`, `docs/design_patterns.md` and https://no-color.org.
