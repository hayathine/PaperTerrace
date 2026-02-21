---
description: Manager's workflow for planning, delegation, and review
---

# Manager Planning & Supervision Workflow

This workflow defines the Manager's role in coordinating development tasks.

1. **Analyze Request & Strategy**
   - Understand the user's goal.
   - Determine which agents/roles are needed (Design, Frontend, Backend, QA).
   - Refer to `.agent/rules/general.md` for project alignment.

2. **Create Implementation Plan**
   - Create a new markdown file in the `plans/` directory.
   - Naming convention: `YYYYMMDD-[feature-name].md` (e.g., `20260130-text-mode.md`).
   - The plan MUST include:
     - **Objective**: What are we building and why?
     - **Specifications**: API changes, UI/UX changes, Data models.
     - **Tasks**: Breakdown of work for each role.
     - **Verification**: How to test (Unit tests, User checks).

3. **Coordinate & Delegate**
   - Call specific workflows for implementation:
     - Backend: Use `/new-backend-feature` or direct `/agent` instructions referencing the plan.
     - Frontend: Use `/new-frontend-component` or direct instructions referencing the plan.
   - Ensure parallel work is synchronized (e.g., agree on API response format first).

4. **Review & Quality Control**
   - **Frontend Review**: ASK for screenshots (`generate_image` or browser capture) of new UIs. Check against Design Rules.
   - **Code Review**: Ensure `fix-lint` workflow is run. Check naming conventions and comments.
   - **Deployment**: Monitor deployment status (e.g., `deploy.sh`). If it fails, troubleshoot immediately.
