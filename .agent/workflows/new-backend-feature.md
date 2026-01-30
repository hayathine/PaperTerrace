---
description: Guide to implementing a new backend feature using FastAPI
---

# New Backend Feature Workflow

This workflow guides you through creating a new backend feature following the `fastapi-design` skill.

1. **Review Design Guidelines**
   Read the FastAPI design skill to understand the architecture.
   (Agent: Use `view_file` on `.agent/skills/fastapi-design/SKILL.md`)

2. **Define Pydantic Schemas**
   Create or update schemas in `src/schemas/`.
   - Define Input Schema (Request body)
   - Define Output Schema (Response body)
   - Ensure explicit typing.

3. **Implement Service Logic**
   Create or update a service in `src/services/` or implementing specific logic in `src/features/`.
   - Use `python-logging` skill for logging.
   - Handle exceptions gracefully.
   - Keep business logic separate from the router.

4. **Create API Router**
   Create a new router file in `src/routers/` or update an existing one.
   - Define `APIRouter`.
   - Use Dependency Injection (`Depends`) for DB sessions and services.
   - Annotate endpoints with appropriate tags and response models.

5. **Register Router**
   Ensure the new router is included in `src/main.py`.

   ```python
   # Example
   # from src.routers import new_feature
   # app.include_router(new_feature.router)
   ```

6. **Test the Endpoint**
   - Create a test case in `tests/`.
   - Verify the endpoint works as expected.
