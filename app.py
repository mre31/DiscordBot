from flask import Flask, render_template, request, jsonify
import os
import logging
import subprocess
import time
import signal
import atexit
from dotenv import load_dotenv

# .env dosyasından çevre değişkenlerini yükle
load_dotenv()

# Flask uygulamasını yapılandır
app = Flask(__name__)

# Log ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot process
bot_process = None

# Bot durumu
bot_status = {
    "running": False,
    "start_time": None,
    "pid": None
}

def start_bot_process():
    """Discord botunu ayrı bir süreçte başlatır"""
    global bot_process, bot_status
    
    if bot_process is None or bot_process.poll() is not None:
        try:
            # worker.py'yi ayrı bir süreçte başlat
            bot_process = subprocess.Popen(["python", "worker.py"])
            bot_status["running"] = True
            bot_status["start_time"] = time.time()
            bot_status["pid"] = bot_process.pid
            logger.info(f"Discord bot başlatıldı (PID: {bot_process.pid})")
        except Exception as e:
            logger.error(f"Bot başlatılırken hata oluştu: {str(e)}")
            bot_status["running"] = False
    
    return bot_status["running"]

def stop_bot_process():
    """Discord bot sürecini durdurur"""
    global bot_process, bot_status
    
    if bot_process and bot_process.poll() is None:
        try:
            bot_process.terminate()
            time.sleep(2)
            if bot_process.poll() is None:
                bot_process.kill()
            
            bot_status["running"] = False
            bot_status["pid"] = None
            logger.info("Discord bot durduruldu")
        except Exception as e:
            logger.error(f"Bot durdurulurken hata oluştu: {str(e)}")

# Uygulama kapanırken bot sürecini temizle
atexit.register(stop_bot_process)

# Ana sayfa
@app.route('/')
def home():
    status = "çalışıyor" if bot_status.get("running", False) else "başlatılıyor"
    return f'Discord bot {status}! Bu sayfa Render üzerinde barındırılıyor.'

# Health check endpoint
@app.route('/health')
def health():
    return jsonify({
        "status": "alive", 
        "message": "Bot çalışıyor!" if bot_status.get("running", False) else "Bot başlatılıyor veya çalışmıyor.",
        "bot_status": bot_status
    })

# Bot kontrolü
@app.route('/bot/status')
def bot_status_route():
    # Bot sürecinin durumunu kontrol et
    if bot_process and bot_process.poll() is None:
        bot_status["running"] = True
    else:
        bot_status["running"] = False
    
    return jsonify(bot_status)

@app.route('/bot/start')
def start_bot_route():
    if start_bot_process():
        return jsonify({"success": True, "message": "Bot başlatıldı"})
    else:
        return jsonify({"success": False, "message": "Bot başlatılamadı"})

@app.route('/bot/stop')
def stop_bot_route():
    stop_bot_process()
    return jsonify({"success": True, "message": "Bot durduruldu"})

@app.route('/bot/restart')
def restart_bot_route():
    stop_bot_process()
    time.sleep(2)
    if start_bot_process():
        return jsonify({"success": True, "message": "Bot yeniden başlatıldı"})
    else:
        return jsonify({"success": False, "message": "Bot yeniden başlatılamadı"})

# Uygulama başladığında bot'u başlat
# Flask 2.x'te before_first_request kaldırıldı, bunun yerine Flask'ın context işleyicilerini kullanacağız
@app.before_request
def start_before_request():
    # Global bir değişkenle ilk istek geldiğinde çalıştırmayı kontrol ediyoruz
    global first_request_processed
    if not getattr(app, 'first_request_processed', False):
        start_bot_process()
        app.first_request_processed = True

# Uygulama başladığında bot'u otomatik başlat (varsa)
if os.environ.get('AUTO_START_BOT', 'True').lower() == 'true':
    start_bot_process()

if __name__ == '__main__':
    # Flask uygulamasını başlat
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port) 