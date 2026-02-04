# Project Structure

## Root Level
- `src/` - Python backend source code
- `frontend/` - React TypeScript frontend
- `tests/` - Backend test suite
- `terraform/` - Infrastructure as code
- `migrations/` - Database migration files
- `plans/` - Project planning documents
- `.kiro/` - Kiro AI assistant configuration

## Backend Structure (`src/`)

### Core Architecture
- `main.py` - FastAPI application entry point
- `routers/` - API route handlers organized by feature
- `domain/` - Business logic and feature implementations
- `models/` - Data models and schemas
- `providers/` - External service integrations
- `auth/` - Authentication and authorization

### Domain-Driven Design
```
src/domain/
├── features/          # Feature-specific business logic
│   ├── chat/         # AI chat functionality
│   ├── summary/      # Document summarization
│   ├── figure_insight/ # Figure analysis
│   └── ...
├── services/         # Shared business services
└── prompts.py        # AI prompt templates
```

### Data Layer
```
src/models/
├── orm/              # SQLAlchemy ORM models
├── schemas/          # Pydantic schemas for API
└── db/              # Database-specific models
```

## Frontend Structure (`frontend/src/`)

### Component Organization
```
src/components/
├── Auth/            # Authentication components
├── Chat/            # Chat interface
├── PDF/             # PDF viewer and interaction
├── Notes/           # Note-taking functionality
├── Dictionary/      # Word lookup interface
├── Sidebar/         # Navigation and tools
└── UI/              # Shared UI components
```

### Application Structure
- `contexts/` - React context providers
- `lib/` - Utility libraries (Firebase, i18n)
- `db/` - IndexedDB integration with Dexie
- `locales/` - Internationalization files

## Configuration Files

### Backend
- `pyproject.toml` - Python dependencies and tool configuration
- `alembic.ini` - Database migration configuration
- `.env` - Environment variables

### Frontend
- `package.json` - Node.js dependencies and scripts
- `vite.config.js` - Build tool configuration
- `tsconfig.json` - TypeScript configuration
- `tailwind.config.js` - Styling configuration

### Development
- `Taskfile.yml` - Task automation (go-task)
- `Dockerfile` - Container configuration
- `.gitignore` - Version control exclusions

## Key Patterns

### Feature Organization
Each major feature follows this pattern:
- Router in `src/routers/`
- Business logic in `src/domain/features/`
- Data models in `src/models/`
- Frontend components in `frontend/src/components/`

### Service Layer
External integrations are abstracted through providers:
- `ai_provider.py` - AI service abstraction
- `storage_provider.py` - File storage
- `redis_provider.py` - Caching layer

### Error Handling
- Custom exception classes per feature
- Structured logging with `structlog`
- Comprehensive error responses in API