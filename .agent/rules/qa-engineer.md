# QA Engineer (Bug Fix & Tester) Rules

Follow these rules when testing or fixing bugs.

## Quality Assurance Policy

**"Don't let the chair break while the user is relaxing on the terrace."**

### 1. Test Strategy

- **Unit Tests**: Write tests in `tests/` using Pytest. Focus on async APIs and complex logic.
- **Lint Free**: Keep Ruff and MyPy errors at zero. Treat warnings as debt.

### 2. Bug Fix Process

- **reproduce First**: Establish a reproduction procedure before fixing.
- **Understand Intent**: Read the code to understand _why_ it was written that way before changing it.
- **Regression Test**: Ensure existing flows (Upload, Summary, Save) are not broken.

### 3. User Perspective Verification

- **Edge Cases**: Verify behavior with large PDFs, potential encoding issues, and network interruptions. Ensure the app handles these gracefully without freezing.
