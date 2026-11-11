#!/usr/bin/env bash

set -Eeuo pipefail

cd /home/ubuntu/devpilot

BACKEND_CHANGED="${1:-false}"
FRONTEND_CHANGED="${2:-false}"

STATUS_FILE="/home/ubuntu/devpilot/deploy-status"

echo "running" > "$STATUS_FILE"

handle_failure() {
    echo "failed" > "$STATUS_FILE"
    echo "Deployment failed. Check deploy.log for details."
}

trap handle_failure ERR

echo "Starting DevPilot deployment..."

# Log in to Amazon ECR
aws ecr get-login-password --region ap-south-1 \
    | sudo docker login \
        --username AWS \
        --password-stdin \
        149536463976.dkr.ecr.ap-south-1.amazonaws.com

# Deploy backend only if backend files changed
if [ "$BACKEND_CHANGED" = "true" ]; then
    echo "Pulling backend image..."

    sudo docker compose --env-file .env \
        -f docker-compose.yml pull backend

    echo "Updating backend..."

    sudo docker compose --env-file .env \
        -f docker-compose.yml up -d --no-deps backend
fi

# Deploy frontend only if frontend files changed
if [ "$FRONTEND_CHANGED" = "true" ]; then
    echo "Pulling frontend image..."

    sudo docker compose --env-file .env \
        -f docker-compose.yml pull frontend

    echo "Updating frontend..."

    sudo docker compose --env-file .env \
        -f docker-compose.yml up -d --no-deps frontend
fi

echo "Checking running containers..."

sudo docker compose --env-file .env \
    -f docker-compose.yml ps

# Remove unused images only after successful deployment
echo "Cleaning unused Docker images..."

sudo docker image prune -af

echo "Deployment completed successfully."

echo "success" > "$STATUS_FILE"
