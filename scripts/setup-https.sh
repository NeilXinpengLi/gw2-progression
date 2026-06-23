#!/bin/bash
# HTTPS setup for production deployment
# Usage: bash scripts/setup-https.sh your-domain.com

set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 your-domain.com"
    exit 1
fi

echo "=== Setting up HTTPS for $DOMAIN ==="

# Install certbot
if ! command -v certbot &>/dev/null; then
    echo "Installing certbot..."
    apt-get update && apt-get install -y certbot python3-certbot-nginx
fi

# Obtain certificate (non-interactive)
echo "Obtaining SSL certificate..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" || {
    echo "certbot failed. Trying standalone mode..."
    systemctl stop nginx 2>/dev/null || docker stop gw2-progression-nginx-1 2>/dev/null || true
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN"
}

# Update nginx config with correct domain
echo "Updating nginx config..."
sed -i "s/gw2-progression.example.com/$DOMAIN/g" docker/nginx.conf

echo ""
echo "=== HTTPS setup complete ==="
echo "Certificate: /etc/letsencrypt/live/$DOMAIN/"
echo "Auto-renewal: certbot renew --dry-run"
echo ""
echo "Next: restart nginx"
