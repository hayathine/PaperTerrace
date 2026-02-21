# Resource Configuration

This directory contains the central configuration for hardware resources (CPU, Memory) and scaling settings for the PaperTerrace services.

## Files

- `resources.json`: The single source of truth for service resources.

## How it's used

### 1. Terraform

Terraform reads this file using `jsondecode(file(...))` in `infrastructure/main.tf` and passes the values to the Cloud Run modules.

### 2. Taskfile

Taskfile.yml uses Python one-liners to extract variables from the JSON:

```yaml
BE_CPU:
  {
    sh: 'python3 -c ''import json; print(json.load(open("config/resources.json"))["backend"]["cpu"])''',
  }
```

### 3. Deployment Scripts

Shell scripts in `scripts/deployment/` have a `get_config` function to read the same values.

### 4. Cloud Build

The `inference-service/cloudbuild.yaml` has a bash step that reads the config file at runtime using Python.

## Modification

To change CPU or Memory for any service, simply modify `config/resources.json`. The changes will propagate to the next deployment via any of the tools above.
