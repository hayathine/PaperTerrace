#!/bin/bash
set -e

# Configuration
PROJECT_ID="paperterracegen-lang-client-0800253336"
REGION="asia-northeast1"
REPO_NAME="paperterrace"
IMAGE_NAME="app"
ARTIFACT_REGISTRY_HOST="${REGION}-docker.pkg.dev"
IMAGE_TAG="latest"
IMAGE_URI="${ARTIFACT_REGISTRY_HOST}/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"
STATE_BUCKET="${PROJECT_ID}-terraform-state"

echo "========================================================"
echo " Starting Deployment for ${PROJECT_ID}"
echo "========================================================"

# 1. Check & Setup Authentication
echo "[1/6] Checking GCloud Authentication..."
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI is not installed."
    exit 1
fi

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Not authenticated. Starting login..."
    gcloud auth login
    gcloud auth application-default login
fi

gcloud config set project ${PROJECT_ID}

# 2. Setup Terraform Backend Bucket
echo "[2/6] Verifying Terraform State Bucket..."
if ! gcloud storage ls gs://${STATE_BUCKET} >/dev/null 2>&1; then
    echo "Creating state bucket gs://${STATE_BUCKET}..."
    gcloud storage buckets create gs://${STATE_BUCKET} --location=${REGION}
else
    echo "State bucket exists."
fi

# 3. Terraform Init & Base Infrastructure
echo "[3/6] Provisioning Base Infrastructure (Artifact Registry, etc)..."
cd terraform

# Ensure backend config matches bucket (optional check, assuming main.tf is correct)
terraform init

# Apply base modules first to create the Registry
# Using module.google_project_service.apis if resource name is different, checking main.tf...
# main.tf uses 'resource "google_project_service" "apis"', not a module.
# So depends_on in modules handles it, but we target modules directly.
terraform apply \
  -target=google_project_service.apis \
  -target=module.artifact_registry \
  -target=module.networking \
  -target=module.secrets \
  -target=module.cloud_sql \
  -target=module.storage \
  -auto-approve

cd ..

# 4. Build & Push Docker Image
echo "[4/6] Building and Pushing Container Image..."
echo "Target Image: ${IMAGE_URI}"

# Configure docker auth
gcloud auth configure-docker ${ARTIFACT_REGISTRY_HOST} --quiet

# Build (Force linux/amd64 for Cloud Run)
docker build --platform linux/amd64 -t ${IMAGE_URI} .

# Push
docker push ${IMAGE_URI}

# 5. Full Deployment (Cloud Run)
echo "[5/6] Deploying Cloud Run Service..."
cd terraform
terraform apply -auto-approve

# 6. Finish
SERVICE_URL=$(terraform output -raw service_url 2>/dev/null || echo "")
echo "========================================================"
echo " Deployment Complete!"
echo " Service URL: ${SERVICE_URL}"
echo "========================================================"
