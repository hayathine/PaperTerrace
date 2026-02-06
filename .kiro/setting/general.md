---
trigger: always_on
---

# General Project Rules

All agents and developers must verify these general rules before starting any task.
Don’t do a quick-and-dirty fix.
Don’t forget to make all necessary follow-up changes caused by this update.（

## 🎯 Project Goal & Target

- **Goal**: Support reading papers as casually as reading on a terrace ("テラスで読むくらい気軽に").
- **Target**: People who struggle with reading papers or want to organize information efficiently.
- **Core Concept**: "Intellectual & Relaxed"

## 🛠 Technology Stack

Ensure consistency with these technologies:

- **Infrastructure**: Google Cloud Platform (GCP)
- **IaC**: Terraform
- **Containerization**: Docker
- **Package Management**: uv (Python)
- **Backend**: Python (FastAPI), SQLAlchemy
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Database**: SQLite (Local), Cloud SQL (Production)
- **Cache**: Redis

## 📏 Common Coding Standards

### 1. Directory Structure

- `src/features/`: Feature-specific logic.
- `src/services/`: General application services.
- `src/routers/`: API endpoint definitions.
- `src/schemas/`: Pydantic data models.
- `src/utils/`: Pure utility functions.
- **Dependency Management**:
  - `pyproject.toml` locations: `./`, `./backend`, `./inference-service`.
  - **Common Libraries**: Managed in the root (`./`) `pyproject.toml`.

### 2. Naming Conventions

- **Python**: `snake_case` (vars/funcs, files), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants).
- **TypeScript**: `camelCase` (vars/funcs), `PascalCase` (components).
- **General**: Be descriptive (no `data`, `item`). Booleans start with `is_`/`has_`.

### 3. Comments

- **Why, not What**: Explain design intent.
- **Docstrings**: Mandatory for public Python functions/classes.
- **Language**: Japanese.
- **TODO**: Use `# TODO: [content]` for future tasks.

### 4. Explain

- When complete implementation or analyze , step by step explain for user in japanese.

\*\* 5. Secret

- Stop display secret infomation such as API and identity . When necesarry , proposal writing .gitignore.
