#!/usr/bin/env bash
set -e

REPO_URL=$1

if [ -z "$REPO_URL" ]; then
  echo "Usage: ./scripts/push_to_github.sh https://github.com/YOUR_USERNAME/YOUR_REPO.git"
  exit 1
fi

echo "Initializing Git repository..."
git init
git add .
git commit -m "feat: initial commit of AI Voice Receptionist Enterprise (atomic slot-locking, Vapi/Retell configs, n8n workflows, GTM kit)"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"

echo "Pushing to $REPO_URL..."
git push -u origin main
echo "Successfully published to GitHub!"
