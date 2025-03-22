import os
import logging
from bot import client
from dotenv import load_dotenv

# .env dosyasından çevre değişkenlerini yükle
load_dotenv()

# Log ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
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

if __name__ == '__main__':
    main() 