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
- **Value Proposition**: Reduces friction in reading academic content via AI OCR, instant translation, and interactive explanations.

## 🎨 Design & Aesthetics (Premium & Relaxed)

- **Tone**: "Intellectual & Relaxed". Use a **gentle "desu/masu" tone** for Japanese UI text.
- **Visuals**: Premium, modern aesthetics. Use smooth gradients, subtle micro-animations, glassmorphism, and dynamic hover effects.
- **Typography**: Use modern typography (e.g., Google Fonts like Inter, Outfit) instead of browser defaults.

## 🛠 Technology Stack

Ensure consistency with these technologies:

- **Infrastructure**: Distributed (Multi-node K8s / GCP hybrid)
- **Deployment**: Kubernetes (Kustomize), Docker
- **Package Management**: uv (Python)
- **Backend**: Python (FastAPI), SQLAlchemy
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Database**: SQLite (Local), Cloud SQL (Hybrid)
- **Cache**: Redis 7.2 (Standardized via `redis_provider`)

## 📏 Common Coding Standards

### 1. Directory Structure

- `backend/app/domain/features/`: Feature-specific logic.
- `backend/app/domain/services/`: General application services.
- `backend/app/routers/`: API endpoint definitions.
- `backend/app/schemas/`: Pydantic data models.
- `backend/app/utils/`: Pure utility functions.
- `inference-service/`: ML inference logic (Layout, Translation).
- `frontend/src/`: React frontend source.
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

## 💻 Common Commands (via Taskfile)

- **Run App**: `task run` (Backend), `task dev` (Frontend)
- **Test**: `task test`
- **Lint**: `task lint`
- **Deploy**: `task deploy` (Prod), `task staging:deploy` (Staging)
- **DB Migrations**: `uv run alembic upgrade head`
