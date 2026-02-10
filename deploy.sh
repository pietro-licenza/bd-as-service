#!/bin/bash
# Cloud Run Deployment Script for BD | AS Platform

set -e

# Configuration
PROJECT_ID="gen-lang-client-0481115304"
SERVICE_NAME="bd-as-platform"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"
REPO_NAME="bd-as-image-parser"  # Nome do repositório no Cloud Source Repositories

echo "🚀 Starting deployment of $SERVICE_NAME to Cloud Run..."
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check if gcloud is authenticated
echo "🔍 Checking gcloud authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Not authenticated with gcloud. Please run: gcloud auth login"
    exit 1
fi

# Set the project
echo "🔧 Setting gcloud project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Option to create Cloud Build trigger
read -p "🔄 Criar trigger do Cloud Build para deploy automático? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🏗️ Creating Cloud Build trigger..."

    # Create cloudbuild.yaml if it doesn't exist
    if [ ! -f "cloudbuild.yaml" ]; then
        cat > cloudbuild.yaml << EOF
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/\$PROJECT_ID/$SERVICE_NAME', '.']

  # Push the container image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/\$PROJECT_ID/$SERVICE_NAME']

  # Deploy container image to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - '$SERVICE_NAME'
      - '--image'
      - 'gcr.io/\$PROJECT_ID/$SERVICE_NAME'
      - '--region'
      - '$REGION'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--port'
      - '8080'
      - '--memory'
      - '1Gi'
      - '--cpu'
      - '1'
      - '--max-instances'
      - '10'
      - '--concurrency'
      - '80'
      - '--timeout'
      - '300'
      - '--set-env-vars'
      - 'GCP_PROJECT_ID=\$PROJECT_ID,GCP_USE_SECRET_MANAGER=true,DEBUG=false'
      - '--set-secrets'
      - 'GCP_SERVICE_ACCOUNT_SECRET_NAME=bd-image-parser-sa-key:latest'

options:
  logging: CLOUD_LOGGING_ONLY
EOF
        echo "✅ Created cloudbuild.yaml"
    fi

    # Create the trigger
    gcloud builds triggers create github \
      --name="$SERVICE_NAME-deploy" \
      --repo-name="$REPO_NAME" \
      --repo-owner="YOUR_GITHUB_USERNAME" \
      --branch-pattern="main" \
      --build-config="cloudbuild.yaml"

    echo "✅ Cloud Build trigger created!"
    echo "🔄 Now every push to main branch will trigger automatic deployment"
    exit 0
fi

# Build and push the Docker image
echo "🏗️ Building and pushing Docker image..."
gcloud builds submit --tag $IMAGE_NAME

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10 \
  --concurrency 80 \
  --timeout 300 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_USE_SECRET_MANAGER=true,DEBUG=false" \
  --set-secrets="GCP_SERVICE_ACCOUNT_SECRET_NAME=bd-image-parser-sa-key:latest"

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "🌐 Service URL:"
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"