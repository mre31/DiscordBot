#!/usr/bin/env bash
# Render build script

# Bağımlılıkları yükle
pip install -r requirements.txt

# FFmpeg kurulumu
apt-get update && apt-get install -y ffmpeg

# SSL sertifika sorunu için gerekli paketleri yükle
apt-get install -y ca-certificates openssl

# yt-dlp'yi en son sürüme güncelle
pip install --upgrade yt-dlp

echo "Derleme tamamlandı." 