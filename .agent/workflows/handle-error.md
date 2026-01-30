---
description: Workflow for diagnosing and fixing errors or bugs
---

# Handle Error / Bug Fix Workflow

This workflow guides you through the process of investigating and resolving errors, following the QA Engineer rules.

1. **Analyze the Error**
   - **Read Logs**: Use `read_terminal` (for active processes) or `view_file` (for `server.log` or similar).
   - **Identify the Source**: Is it a Frontend (browser console), Backend (FastAPI logs), or Infrastructure (Deployment/Terraform) issue?
   - **Read Stack Trace**: Locate exactly where the error originates.

2. **Establish Reproduction**
   - **Do not guess**. confirm you can reproduce the error.
   - **Logic Bugs**: Create a minimal reproduction script or a new test case in `tests/repro_issue_XXX.py`.
   - **API/Server Errors**: Use `curl` or a test script to hit the endpoint and trigger the error.
   - **Deployment Errors**: Verify local Docker build works (`docker build .`) before assuming it's a cloud issue.

3. **Plan the Fix**
   - Read the relevant code based on the stack trace.
   - Understand the _intent_ of the code before changing it.
   - Consult `.agent/rules/qa-engineer.md`.

4. **Implement Fix**
   - Apply the code changes.
   - Ensure you are not breaking other features (Regression Check).

5. **Verify**
   - Run the reproduction script/test case created in Step 2.
   - **Must pass**.
   - If applicable, run all backend tests (`pytest`).

6. **Cleanup**
   - Remove temporary reproduction scripts if they aren't converted to permanent tests.
   - Commit the fix.

7. **Explain**
   - step by step explain for user in japanese.
