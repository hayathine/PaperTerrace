#!/bin/bash
set -e

# Load .env
source secrets/.env

PROJECT_ID="gen-lang-client-0800253336"
SERVICE_ACCOUNT="602776143589-compute@developer.gserviceaccount.com"

# Secret Name -> Env Var Value Mapping
# Note: Using associative arrays (requires bash 4+) or simple multiple arrays
SECRETS=(
  "GEMINI_API_KEY=$GEMINI_API_KEY"
  "FIREBASE_API_KEY=$FIREBASE_API_KEY"
  "FIREBASE_AUTH_DOMAIN=$FIREBASE_AUTH_DOMAIN"
  "FIREBASE_PROJECT_ID=$FIREBASE_PROJECT_ID"
  "FIREBASE_STORAGE_BUCKET=$FIREBASE_STORAGE_BUCKET"
  "FIREBASE_MESSAGING_SENDER_ID=$FIREBASE_MESSAGING_SENDER_ID"
  "FIREBASE_APP_ID=$FIREBASE_APP_ID"
  "FIREBASE_MEASUREMENT_ID=$FIREBASE_MEASUREMENT_ID"
  "DB_PASSWORD=$DB_PASSWORD"
)

echo "Starting Secret Manager migration..."

for secret in "${SECRETS[@]}"; do
  KEY="${secret%%=*}"
  VALUE="${secret#*=}"
  
  if [ -z "$VALUE" ]; then
    echo "⚠️ Skipping $KEY (empty value)"
    continue
  fi

  echo "Processing $KEY..."

  # Create secret if not exists
  if ! gcloud secrets describe "$KEY" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create "$KEY" --replication-policy="automatic" --project="$PROJECT_ID" --quiet
    echo "  Created secret: $KEY"
  else
    echo "  Secret $KEY already exists."
  fi

  # Add version
  echo -n "$VALUE" | gcloud secrets versions add "$KEY" --data-file=- --project="$PROJECT_ID" --quiet
  echo "  Added new version."

  # Grant access to service account
  gcloud secrets add-iam-policy-binding "$KEY" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" --quiet >/dev/null
  echo "  Granted access to $SERVICE_ACCOUNT."
done

echo "✅ All secrets migrated successfully!"
