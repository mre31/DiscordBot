# Discord Müzik Botu - Render Dağıtımı

Bu Discord müzik botu, YouTube'dan müzik oynatma, çalma listeleri oluşturma ve çeşitli müzik komutlarını destekleyen bir bottur. Bot, Render platformunda 7/24 çalışacak şekilde yapılandırılmıştır.

## Özellikler

- YouTube'dan müzik oynatma
- Çalma listeleri oluşturma ve yönetme
- Karıştırma modu
- Ses kontrolü
- Ve daha fazlası...

## Dağıtım

### Render Üzerinde Dağıtım

1. Render hesabı oluşturun ve giriş yapın
2. "New +" düğmesine tıklayın ve "Web Service" seçin
3. GitHub hesabınızı bağlayın ve bu depoyu seçin
4. Otomatik olarak `render.yaml` yapılandırması tanınacaktır
5. Çevre değişkenlerini ayarlayın:
   - `DISCORD_TOKEN`: Discord Bot Token'ınızı buraya girin

6. "Create Web Service" düğmesine tıklayın

## Yerel Geliştirme

1. Depoyu klonlayın:
```
git clone <repo_url>
cd discord-bot
```

2. Sanal ortam oluşturun:
```
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. Bağımlılıkları yükleyin:
```
pip install -r requirements.txt
```

4. `.env` dosyası oluşturun ve Discord token bilgisini ekleyin:
```
DISCORD_TOKEN=<discord_token_buraya>
```

5. Uygulamayı çalıştırın:
```
python app.py
```

## Bot Komutları

- `/play <şarkı_adı_veya_url>`: Bir şarkı oynat
- `/skip`: Mevcut şarkıyı atla
- `/queue`: Mevcut kuyruğu görüntüle
- `/stop`: Oynatmayı durdur ve kuyrukları temizle
- `/pause`: Oynatmayı duraklat
- `/resume`: Duraklatılmış oynatmayı devam ettir 