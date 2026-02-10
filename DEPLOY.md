# Cloud Run Deployment Guide

## Prerequisites
1. Google Cloud SDK installed and authenticated
2. Docker installed
3. GCP project configured

## Environment Setup
1. Copy `.env.example` to `.env` and fill in your values
2. Create secrets in Google Secret Manager:
   ```bash
   gcloud secrets create bd-image-parser-sa-key --data-file=bd_image_parser_service_account.json
   ```

## Deployment Options

### 🚀 Option 1: One-time Manual Deploy
```bash
./deploy.sh
```
This will build and deploy immediately.

### 🔄 Option 2: Automated CI/CD with Cloud Build Trigger
```bash
./deploy.sh
# When prompted, answer 'y' to create Cloud Build trigger
```

This creates:
- **Cloud Build trigger** that deploys on every push to main branch
- **cloudbuild.yaml** with the build and deploy steps
- **Automatic deployments** when you push code changes

## Manual Deploy Steps
```bash
# Build the Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/bd-as-platform

# Deploy to Cloud Run
gcloud run deploy bd-as-platform \
  --image gcr.io/YOUR_PROJECT_ID/bd-as-platform \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=YOUR_PROJECT_ID" \
  --set-secrets="GOOGLE_CLOUD_PROJECT=bd-image-parser-sa-key:latest"
```

## Quick Deploy Script
```bash
#!/bin/bash
PROJECT_ID="gen-lang-client-0481115304"
SERVICE_NAME="bd-as-platform"
REGION="us-central1"

# Build and push image
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_USE_SECRET_MANAGER=true" \
  --set-secrets="GCP_SERVICE_ACCOUNT_SECRET_NAME=bd-image-parser-sa-key:latest"
```