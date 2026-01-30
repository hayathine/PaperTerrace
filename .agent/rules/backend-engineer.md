# Backend Engineer Rules

Follow these rules when writing backend code (Python, FastAPI).

## Implementation Guidelines

### 1. API Design

- **RESTful**: Follow standard REST principles.
- **Validation**: Use Pydantic models for strict request/response validation. Ensure OpenAPI (Swagger) documentation is accurate.

### 2. Logic & AI Integration

- **Prompts**: Manage all prompts in `src/prompts.py`. Never hardcode prompts in logic files.
- **Async**: Use `async/await` for all I/O bound operations (DB, API calls, File I/O) to maintain throughput.

### 3. Robustness

- **Error Handling**: Implement global exception handlers. Ensure the server never crashes due to an unhandled exception.
- **Logging**: Use `src/logger` (see `python-logging` skill). Log at appropriate levels (INFO, WARNING, ERROR).
