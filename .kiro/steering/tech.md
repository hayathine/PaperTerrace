# Technology Stack

## Backend
- **Framework**: FastAPI (Python 3.12+)
- **AI/ML**: Google GenAI (Gemini models), Spacy NLP, CTranslate2
- **Database**: SQLite (local), PostgreSQL (cloud), Redis (caching)
- **ORM**: SQLAlchemy with Alembic migrations
- **Authentication**: Firebase Admin SDK
- **Cloud Services**: Google Cloud (Storage, Tasks, SQL, Run)

## Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS with Typography plugin
- **State Management**: React Context, Dexie (IndexedDB)
- **Internationalization**: i18next
- **Testing**: Vitest, Testing Library

## Development Tools
- **Package Management**: uv (Python), npm (Node.js)
- **Task Runner**: go-task (Taskfile.yml)
- **Linting**: Ruff (Python), ESLint (TypeScript)
- **Type Checking**: Pyright (Python), TypeScript
- **Testing**: pytest (Python), Vitest (Frontend)

## Infrastructure
- **Containerization**: Docker
- **Infrastructure as Code**: Terraform
- **Deployment**: Google Cloud Run
- **CI/CD**: Google Cloud Build

## Common Commands

### Development
```bash
# Start backend server
task run
# or manually: uv run uvicorn src.main:app --reload

# Start frontend dev server
task dev
# or: cd frontend && npm run dev

# Run all tests
task test

# Run linting
task lint
```

### Database
```bash
# Run migrations
uv run alembic upgrade head

# Create new migration
uv run alembic revision --autogenerate -m "description"
```

### Deployment
```bash
# Deploy to production
task deploy

# Deploy to staging
task staging:deploy

# Build frontend
task build
```

## Environment Variables
Key environment variables required:
- `GEMINI_API_KEY`: Google AI API key
- `OCR_MODEL`: AI model for OCR (default: gemini-1.5-flash)
- `DB_PATH`: Database path for local development
- `AI_PROVIDER`: gemini or vertex
- Firebase configuration variables for authentication