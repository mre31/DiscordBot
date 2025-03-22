from flask import Flask, render_template, request, jsonify
import threading
import os
import logging
from bot import client
from dotenv import load_dotenv

# .env dosyasından çevre değişkenlerini yükle
load_dotenv()

# Flask uygulamasını yapılandır
app = Flask(__name__)

# Log ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot thread değişkeni
bot_thread = None

# Ana sayfa
@app.route('/')
def home():
    # Bot'un başlatılıp başlatılmadığını kontrol et ve gerekirse başlat
    start_bot()
    return 'Discord bot çalışıyor! Bu sayfa Render üzerinde barındırılıyor.'

# Health check endpoint
@app.route('/health')
def health():
    return jsonify({"status": "alive", "message": "Bot çalışıyor!"})

# Bot bilgilerini görüntüleme
@app.route('/stats')
def stats():
    stats_data = {
        "guilds": len(client.guilds) if hasattr(client, 'guilds') else 0,
        "uptime": "Çalışıyor",
        "status": "Online"
    }
    return jsonify(stats_data)

# Bot'u ayrı bir thread'de başlat
def run_discord_bot():
    try:
        # Önce Render ortam değişkenini kontrol et, yoksa .env dosyasından al
        token = os.environ.get('DISCORD_TOKEN') or os.getenv('DISCORD_TOKEN')
        if not token:
            logger.error("DISCORD_TOKEN bulunamadı! Render ortam değişkenlerini veya .env dosyasını kontrol edin.")
            return
        
        logger.info("Discord botu başlatılıyor...")
        client.run(token)
    except Exception as e:
        logger.error(f"Bot başlatılırken hata oluştu: {str(e)}")

# Bot'u başlatmak için fonksiyon
def start_bot():
    global bot_thread
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=run_discord_bot)
        bot_thread.daemon = True
        bot_thread.start()
        logger.info("Bot thread başlatıldı")

# Uygulama başladığında bot'u başlat
with app.app_context():
    start_bot()

if __name__ == '__main__':
    # Flask uygulamasını başlat
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port) 