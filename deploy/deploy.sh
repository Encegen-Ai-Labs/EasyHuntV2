#!/bin/sh
# Runs ON THE SERVER (the deploy workflow copies it over and calls it).
#   IMAGE=ghcr.io/<owner>/easyhunt-backend sh deploy.sh <git-commit-tag>
#
# 1. remember which version is running now,
# 2. pull the new images and restart the api and worker on them,
# 3. wait for /health/ready (database and queue reachable),
# 4. if it never becomes ready, put the previous version back and exit with an error.
#
# Rollback by hand at any time:  sh deploy.sh "$(cat .last_good_tag)"   (or any older commit tag)
set -eu

TAG="${1:?usage: IMAGE=<registry/image> sh deploy.sh <tag>}"
: "${IMAGE:?IMAGE must be set}"
cd "$(dirname "$0")"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
PREVIOUS="$(cat .last_good_tag 2>/dev/null || true)"
READY_URL="${READY_URL:-http://127.0.0.1:8000/health/ready}"
ATTEMPTS="${ATTEMPTS:-40}"   # x 3 seconds = 2 minutes

start() {
  IMAGE="$IMAGE" IMAGE_TAG="$1" $COMPOSE pull api worker
  IMAGE="$IMAGE" IMAGE_TAG="$1" $COMPOSE up -d --no-build --remove-orphans
}

wait_until_ready() {
  n=0
  while [ "$n" -lt "$ATTEMPTS" ]; do
    if curl -fsS "$READY_URL" >/dev/null 2>&1; then
      return 0
    fi
    n=$((n + 1))
    sleep 3
  done
  return 1
}

echo "Deploying $TAG (previous: ${PREVIOUS:-none})"
start "$TAG"

if wait_until_ready; then
  echo "$TAG" > .last_good_tag
  echo "Deployed $TAG and it is ready."
  exit 0
fi

echo "ERROR: $TAG did not become ready." >&2
$COMPOSE logs --tail=60 api >&2 || true
if [ -n "$PREVIOUS" ]; then
  echo "Rolling back to $PREVIOUS" >&2
  start "$PREVIOUS"
  wait_until_ready && echo "Rolled back to $PREVIOUS and it is ready." >&2 || echo "Rollback is not ready either: look at the server now." >&2
else
  echo "No previous version recorded, nothing to roll back to." >&2
fi
exit 1
