---
description: Guide to deploying the application to Staging and Production environments
---

# Deployment Workflow

This workflow guides you through the deployment process for PaperTerrace.

## 1. Staging Deployment

Before deploying to production, it is recommended to verify changes in the staging environment.

### 1.1 Build and Deploy to Staging

// turbo
Deploy the current branch to the staging environment. This skips Terraform infrastructure checks for speed.

```bash
task staging:deploy
```

### 1.2 Full Staging Deploy (with Infrastructure)

// turbo
Use this to deploy to staging including Terraform infrastructure updates.

```bash
task staging:deploy:full
```

### 1.3 Force Rebuild Staging

// turbo
Use this to force a rebuild of the Docker image (ignoring cache) and deploy to staging.

```bash
task staging:rebuild
```

### 1.4 Verify Staging

// turbo
Check the staging logs to verify the deployment.

```bash
task staging:logs
```

Get the staging URL:

```bash
task staging:url
```

## 2. Production Deployment

Deploy the application to the production environment.

### 2.1 Fast Deploy (Code Only)

// turbo
Use this for code-only updates. It skips slow infrastructure checks.

```bash
task deploy:fast
```

### 2.2 Full Deploy (Infrastructure + Code)

// turbo
Use this when infrastructure changes (Terraform) are involved or for a comprehensive deployment.

```bash
task deploy
```

## 3. Post-Deployment Verification

### 3.1 Check Production Logs

// turbo
Monitor production logs to ensure the service is running correctly.

```bash
task read:info
```

### 3.2 Check for Errors

// turbo
Check for any error logs in production.

```bash
task read:error
```
