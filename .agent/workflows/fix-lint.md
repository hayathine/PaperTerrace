---
description: Run code quality checks and auto-fixes using Ruff
---

# Fix Code Quality Workflow

This workflow helps you maintain code quality by running linter checks and formatters.

1. **Check for lint errors**
   Check for any linting errors in the codebase.

   ```bash
   uv run ruff check .
   ```

2. **Auto-fix lint errors**
   // turbo
   Attempt to automatically fix simple lint errors.

   ```bash
   uv run ruff check --fix .
   ```

3. **Format code**
   // turbo
   Format the code to adhere to the project's style guide.

   ```bash
   uv run ruff format .
   ```

4. **Verify changes**
   Run the check again to ensure all issues are resolved.

   ```bash
   uv run ruff check .
   ```

5. **Review changes**
   If there are still errors remaining after auto-fix, manually review the output and fix them according to the `ruff` skill guidelines.
