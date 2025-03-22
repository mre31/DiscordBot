#!/usr/bin/env bash
# Render build script

# Bağımlılıkları yükle
pip install -r requirements.txt

# FFmpeg kurulumu
apt-get update && apt-get install -y ffmpeg

echo "Derleme tamamlandı." 