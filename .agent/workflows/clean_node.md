---
description: Comprehensive workflow for code cleanup, linting, testing, and error reporting.
---

This workflow guides you through cleaning the codebase (unused elements), enforcing code quality (lint/ruff), generating missing tests, and running functionality checks.

# 1. Preparation

1. Create the output directory for test reports.
   ```bash
   mkdir -p plans/tests
   ```

# 2. Cleanup: Unused Elements

1. **Unused Imports & Variables (Auto-fix)**:
   - Use `ruff` to automatically remove unused imports (F401) and variables (F841).
   ```bash
   ruff check --select F401,F841 --fix .
   ```
2. **Unused Files & Directories (Manual/Agentic)**:
   - Search for files that are not imported or referenced.
   - **Action**: List potential candidates for deletion. **Ask the USER for confirmation** before deleting entire files or directories.
3. **Commented-out Code**:
   - Search for large blocks of commented-out code (not docstrings).
   - **Action**: Delete blocks of commented-out code that serve no documentation purpose.
   - _Regex Tip_: Look for lines starting with `#` that resemble code (e.g., `# def `, `# import `, `# class `).

# 3. Code Quality & Formatting

1. **Ruff Linting & Formatting**:
   - Run the full linter and formatter.
   ```bash
   ruff check --fix .
   ruff format .
   ```

# 4. Test Creation

1. **Analyze Coverage**:
   - Identify key source files that lack corresponding test files in `tests/` or `backend/tests/`.
2. **Generate Tests**:
   - For files missing test coverage, create new test files (e.g., `test_filename.py`) using `pytest` standards.
   - Ensure tests cover happy paths and edge cases.

# 5. Execution: Run Tests

1. **Run Pytest**:
   - Execute tests and capture output. If tests fail, do _not_ stop; proceed to report generation.
   ```bash
   pytest --maxfail=100 -v | tee plans/tests/latest_run.log || true
   ```

# 6. Error Reporting

1. **Analyze Failures**:
   - Read `plans/tests/latest_run.log`.
   - If there are failures, extract the specific error messages and stack traces.
2. **Save Report**:
   - Create a markdown file in `plans/tests/` (e.g., `failed_tests_report_YYYYMMDD.md`).
   - Content should include:
     - Summary of passed/failed tests.
     - Detailed log of each failure.
     - Proposed fixes for the failures (if obvious).
