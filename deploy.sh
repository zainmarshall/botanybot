#!/usr/bin/env bash
# Deploy botanybot on the Raspberry Pi.
#
# Usage:
#   ./deploy.sh              # pull main repo + restart bot (re-fetches images from botanybot-images)
#   ./deploy.sh watch        # listen for GitHub webhook on port 9000, auto-deploys on push
#   ./deploy.sh restart      # just restart the bot (forces sciolyid to re-clone images)

set -euo pipefail
cd "$(dirname "$0")"

deploy() {
    echo "$(date): Pulling botanybot..."
    git pull origin master

    echo "$(date): Rebuilding & restarting (bot will re-fetch botanybot-images on startup)..."
    docker compose build --pull
    docker compose up -d --force-recreate
    echo "$(date): Deploy complete."
}

restart_only() {
    echo "$(date): Restarting bot (will re-fetch latest images)..."
    docker compose up -d --force-recreate
    echo "$(date): Restart complete."
}

case "${1:-deploy}" in
    watch)
        PORT="${2:-9000}"
        echo "Listening for GitHub webhooks on port $PORT..."
        echo "Add this as a webhook in GitHub repo settings:"
        echo "  URL: http://<your-pi-ip>:$PORT"
        echo "  Content type: application/json"
        echo "  Events: Just the push event"
        echo ""
        while true; do
            echo -e "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok" | nc -l "$PORT" > /dev/null 2>&1
            echo "$(date): Webhook received, deploying..."
            deploy 2>&1 | tee -a /tmp/botanybot-deploy.log
        done
        ;;
    restart)
        restart_only
        ;;
    *)
        deploy
        ;;
esac
