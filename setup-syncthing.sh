#!/usr/bin/env bash
# Sets up Syncthing mesh shared drive
set -e

echo "📦 Installing Syncthing..."
# Add official Syncthing repo + install
curl -s https://syncthing.net/release-key.txt | sudo apt-key add -
echo "deb https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list
sudo apt-get update -qq
sudo apt-get install -y syncthing

# Create mesh-drive directory
mkdir -p ~/mesh-drive
echo "✅ ~/mesh-drive created"

# Enable + start syncthing service
sudo systemctl enable syncthing@$USER
sudo systemctl start syncthing@$USER
echo "✅ Syncthing service started"

# Set up basic auth for nginx (prompts for password)
echo ""
echo "🔐 Set a password for /drive/ nginx basic auth:"
sudo htpasswd -c /etc/nginx/.syncthing_htpasswd mesh

echo ""
echo "✅ Syncthing setup complete!"
echo ""
echo "👉 Next steps:"
echo "  1. Add nginx-syncthing.conf block to your nginx server config"
echo "  2. Visit https://axismundi.fun/drive/ to access Syncthing GUI"
echo "  3. Get your Device ID from GUI > Actions > Show ID"
echo "  4. Share ~/mesh-drive folder with mesh members' Device IDs"
echo "  5. Members run: syncthing (first time generates their Device ID)"
echo ""
echo "📁 Shared folder: ~/mesh-drive"
echo "🌐 GUI: https://axismundi.fun/drive/ (after nginx config)"
