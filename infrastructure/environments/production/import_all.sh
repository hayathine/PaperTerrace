# This script was used for one-time Terraform state import.
# It is no longer needed.
#!/bin/bash
# Import all existing GCP resources into Terraform state
set -e

PROJECT_ID="gen-lang-client-0800253336"
PROJECT_NUM="602776143589"
REGION="asia-northeast1"

# Common vars
VARS="-var=project_id=${PROJECT_ID} -var=region=${REGION} -var=gemini_api_key=${GEMINI_API_KEY} -var=db_password=${DB_PASSWORD} -var=image_url=${REGION}-docker.pkg.dev/${PROJECT_ID}/paperterrace/app:latest"

import_resource() {
  local addr="$1"
  local id="$2"
  echo "📥 Importing: $addr"
  if terraform state show "$addr" &>/dev/null; then
    echo "  ⏭️  Already in state, skipping"
  else
    terraform import $VARS "$addr" "$id" && echo "  ✅ Success" || echo "  ⚠️  Failed (may need manual fix)"
  fi
}

echo "=== Networking Module ==="
import_resource "module.networking.google_compute_network.main" "projects/${PROJECT_ID}/global/networks/paperterrace-vpc"
import_resource "module.networking.google_compute_subnetwork.main" "projects/${PROJECT_ID}/regions/${REGION}/subnetworks/paperterrace-subnet"
import_resource "module.networking.google_compute_global_address.private_ip" "projects/${PROJECT_ID}/global/addresses/paperterrace-private-ip"
import_resource "module.networking.google_service_networking_connection.private_vpc_connection" "${PROJECT_ID}/paperterrace-vpc:servicenetworking.googleapis.com"
import_resource "module.networking.google_compute_firewall.allow_internal" "projects/${PROJECT_ID}/global/firewalls/paperterrace-allow-internal"

echo ""
echo "=== IAM Module ==="
import_resource "module.iam.google_service_account.app_sa" "projects/${PROJECT_ID}/serviceAccounts/paperterrace-sa@${PROJECT_ID}.iam.gserviceaccount.com"
import_resource "module.iam.google_project_iam_member.cloud_sql_client" "${PROJECT_ID}/roles/cloudsql.client/serviceAccount:paperterrace-sa@${PROJECT_ID}.iam.gserviceaccount.com"
import_resource "module.iam.google_project_iam_member.log_writer" "${PROJECT_ID}/roles/logging.logWriter/serviceAccount:paperterrace-sa@${PROJECT_ID}.iam.gserviceaccount.com"
import_resource "module.iam.google_project_iam_member.ai_platform_user" "${PROJECT_ID}/roles/aiplatform.user/serviceAccount:paperterrace-sa@${PROJECT_ID}.iam.gserviceaccount.com"
import_resource "module.iam.google_project_iam_member.token_creator" "${PROJECT_ID}/roles/iam.serviceAccountTokenCreator/serviceAccount:paperterrace-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo "=== Artifact Registry Module ==="
import_resource "module.artifact_registry.google_artifact_registry_repository.main" "projects/${PROJECT_ID}/locations/${REGION}/repositories/paperterrace"

echo ""
echo "=== Secrets Module ==="
import_resource "module.secrets.google_secret_manager_secret.gemini_api_key" "projects/${PROJECT_NUM}/secrets/gemini-api-key"
import_resource "module.secrets.google_secret_manager_secret.db_password" "projects/${PROJECT_NUM}/secrets/db-password"

# Secret versions - get latest version numbers
echo "  Importing secret versions..."
GEMINI_VER=$(gcloud secrets versions list gemini-api-key --format="value(name)" --limit=1 --sort-by="~createTime" 2>/dev/null || echo "")
DB_VER=$(gcloud secrets versions list db-password --format="value(name)" --limit=1 --sort-by="~createTime" 2>/dev/null || echo "")

if [ -n "$GEMINI_VER" ]; then
  import_resource "module.secrets.google_secret_manager_secret_version.gemini_api_key" "projects/${PROJECT_NUM}/secrets/gemini-api-key/versions/${GEMINI_VER}"
fi
if [ -n "$DB_VER" ]; then
  import_resource "module.secrets.google_secret_manager_secret_version.db_password" "projects/${PROJECT_NUM}/secrets/db-password/versions/${DB_VER}"
fi

# Secret IAM members
SA_EMAIL="paperterrace-sa@${PROJECT_ID}.iam.gserviceaccount.com"
import_resource "module.secrets.google_secret_manager_secret_iam_member.gemini_api_key_accessor" "projects/${PROJECT_ID}/secrets/gemini-api-key/roles/secretmanager.secretAccessor/serviceAccount:${SA_EMAIL}"
import_resource "module.secrets.google_secret_manager_secret_iam_member.db_password_accessor" "projects/${PROJECT_ID}/secrets/db-password/roles/secretmanager.secretAccessor/serviceAccount:${SA_EMAIL}"

echo ""
echo "=== Storage Module ==="
import_resource "module.storage.google_storage_bucket.papers" "paperterrace-papers"
import_resource "module.storage.google_storage_bucket_iam_member.cloud_run_admin" "paperterrace-papers/roles/storage.objectAdmin/serviceAccount:${SA_EMAIL}"

# Check if public read exists
PUBLIC_READ=$(gsutil iam get gs://paperterrace-papers 2>/dev/null | grep -c "allUsers" || echo "0")
if [ "$PUBLIC_READ" != "0" ]; then
  import_resource "module.storage.google_storage_bucket_iam_member.public_read" "paperterrace-papers/roles/storage.objectViewer/allUsers"
fi

echo ""
echo "=== Cloud SQL Module ==="
import_resource "module.cloud_sql.google_sql_database_instance.main" "projects/${PROJECT_ID}/instances/paperterrace-db"
import_resource "module.cloud_sql.google_sql_database.main" "projects/${PROJECT_ID}/instances/paperterrace-db/databases/paperterrace"
import_resource "module.cloud_sql.google_sql_user.main" "${PROJECT_ID}/paperterrace-db/paperterrace"

echo ""
echo "=== Cloud Run Module ==="
import_resource "module.cloud_run.google_cloud_run_v2_service.main" "projects/${PROJECT_ID}/locations/${REGION}/services/paperterrace"
import_resource "module.cloud_run.google_cloud_run_v2_service_iam_member.public" "projects/${PROJECT_ID}/locations/${REGION}/services/paperterrace/roles/run.invoker/allUsers"

echo ""
echo "=== API Services ==="
for api in run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com vpcaccess.googleapis.com servicenetworking.googleapis.com iam.googleapis.com iamcredentials.googleapis.com; do
  import_resource "google_project_service.apis[\"${api}\"]" "${PROJECT_ID}/${api}"
done

echo ""
echo "🎉 Import complete! Run 'terraform plan' to verify."
