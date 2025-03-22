import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio
from collections import deque
from discord import ui
from discord.ui import Button, View
import re
import json
import os
import random
import time

# Bot ayarları
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

# YouTube DL ayarları
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0',
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'force_generic_extractor': False,
    'cachedir': False,
    'socket_timeout': 10,
    'max_downloads': 5
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.7):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        
        if 'entries' in data:
            data = data['entries'][0]
            
        filename = data['url']
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.song_queue = {}
        self.now_playing = {}
        self.favorites = self.load_favorites()
        self.playlists = self.load_playlists()
        self.shuffle_mode = self.load_shuffle_mode()  # Karıştırma modunu yükle
        self.voice_state_tasks = {}  # Ses kanalı kontrol görevlerini takip etmek için
        self.last_played = self.load_last_played()  # Son çalan şarkıları yükle

    def load_favorites(self):
        try:
            if os.path.exists('favorites.json'):
                with open('favorites.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}

    def save_favorites(self):
        with open('favorites.json', 'w', encoding='utf-8') as f:
            json.dump(self.favorites, f, ensure_ascii=False, indent=4)

    def get_user_favorites(self, user_id):
        return self.favorites.get(str(user_id), [])

    def load_playlists(self):
        try:
            if os.path.exists('playlists.json'):
                with open('playlists.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Eğer shuffle_settings anahtarı varsa, playlists'e atamadan önce kaldır
                    if 'shuffle_settings' in data:
                        data.pop('shuffle_settings', None)
                    return data
            return {}
        except Exception:
            return {}

    def save_playlists(self):
        # Mevcut playlists ve shuffle_mode'u birleştir
        data_to_save = self.playlists.copy()
        # shuffle_settings anahtarını ekle
        data_to_save['shuffle_settings'] = self.shuffle_mode
        
        with open('playlists.json', 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)

    def load_shuffle_mode(self):
        try:
            if os.path.exists('playlists.json'):
                with open('playlists.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # shuffle_settings anahtarı varsa döndür, yoksa boş sözlük döndür
                    return data.get('shuffle_settings', {})
            return {}
        except Exception:
            return {}

    def save_shuffle_mode(self):
        # Mevcut playlists ve shuffle_mode'u birleştir
        data_to_save = self.playlists.copy()
        # shuffle_settings anahtarını ekle
        data_to_save['shuffle_settings'] = self.shuffle_mode
        
        with open('playlists.json', 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)

    def get_playlists(self):
        return self.playlists

    def load_last_played(self):
        """Son çalan şarkıları yükle"""
        try:
            if os.path.exists('playlists.json'):
                with open('playlists.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('last_played', {})
            return {}
        except Exception:
            return {}

    def save_last_played(self):
        """Son çalan şarkıları kaydet"""
        try:
            data_to_save = {}
            if os.path.exists('playlists.json'):
                with open('playlists.json', 'r', encoding='utf-8') as f:
                    data_to_save = json.load(f)
            
            data_to_save['last_played'] = self.last_played
            
            with open('playlists.json', 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Son çalan şarkı kaydedilirken hata oluştu: {str(e)}")

    def update_last_played(self, guild_id: int, song_info: dict):
        """Son çalan şarkıyı güncelle"""
        guild_id_str = str(guild_id)
        self.last_played[guild_id_str] = song_info
        self.save_last_played()

    async def setup_hook(self):
        await self.tree.sync()
        # Periyodik olarak ses kanallarını kontrol et
        self.loop.create_task(self.check_voice_channels())

    def setup_queue(self, guild_id):
        if guild_id not in self.song_queue:
            self.song_queue[guild_id] = deque()
            self.now_playing[guild_id] = None
        
        # Shuffle modu her zaman dosyadan oku
        guild_id_str = str(guild_id)  # JSON anahtarları string olmalı
        # Eğer dosyada bu sunucu için bir ayar varsa, onu kullan
        if guild_id_str in self.shuffle_mode:
            # Zaten yüklendi, bir şey yapmaya gerek yok
            pass
        else:
            # Dosyada yoksa varsayılan olarak kapalı ayarla
            self.shuffle_mode[guild_id_str] = False
            # Ve dosyaya kaydet
            self.save_shuffle_mode()

    async def play_next(self, interaction: discord.Interaction):
        try:
            if interaction.guild_id in self.song_queue and len(self.song_queue[interaction.guild_id]) >= 1:
                voice_client = interaction.guild.voice_client
                
                if voice_client and voice_client.is_connected():
                    next_song = self.song_queue[interaction.guild_id].popleft()
                    self.now_playing[interaction.guild_id] = next_song
                    # Son çalan şarkıyı kaydet
                    self.update_last_played(interaction.guild_id, next_song)
                    
                    try:
                        player = await YTDLSource.from_url(next_song['url'], loop=self.loop, stream=True)
                        
                        def after_callback(error):
                            if error:
                                asyncio.run_coroutine_threadsafe(
                                    interaction.channel.send(f'An error occurred while playing: {error}'),
                                    self.loop
                                )
                            else:
                                asyncio.run_coroutine_threadsafe(
                                    self.play_next(interaction),
                                    self.loop
                                )
                        
                        voice_client.play(player, after=after_callback)
                        await interaction.channel.send(f'**Now playing:** {next_song["title"]}')
                    except Exception as e:
                        await interaction.channel.send(f'An error occurred while playing next song: {str(e)}')
                        # Hata durumunda bir sonraki şarkıya geç
                        await self.play_next(interaction)
                else:
                    # Ses bağlantısı kopmuşsa temizlik yap
                    self.song_queue[interaction.guild_id].clear()
                    self.now_playing[interaction.guild_id] = None
        except Exception as e:
            print(f"Error in play_next: {str(e)}")

    async def check_voice_channels(self):
        """Periyodik olarak tüm ses kanallarını kontrol eder ve boş olanlardan çıkar."""
        while not self.is_closed():
            await asyncio.sleep(10)  # Her 10 saniyede bir kontrol et
            for guild in self.guilds:
                if guild.voice_client and guild.voice_client.is_connected():
                    # Botun bulunduğu ses kanalını al
                    voice_channel = guild.voice_client.channel
                    # Kanalda bot dışında kimse var mı kontrol et
                    members = [m for m in voice_channel.members if not m.bot]
                    
                    if not members:  # Kanalda bot dışında kimse yoksa
                        guild_id = guild.id
                        # Eğer bu sunucu için zaten bir görev varsa, yeni oluşturma
                        if guild_id not in self.voice_state_tasks or self.voice_state_tasks[guild_id].done():
                            # 30 saniye sonra kanaldan çıkma görevi oluştur
                            task = self.loop.create_task(self.leave_empty_channel(guild))
                            self.voice_state_tasks[guild_id] = task
                    else:
                        # Kanalda birileri varsa, varsa bekleyen görevi iptal et
                        guild_id = guild.id
                        if guild_id in self.voice_state_tasks and not self.voice_state_tasks[guild_id].done():
                            self.voice_state_tasks[guild_id].cancel()
                            print(f"{guild.name} sunucusunda ses kanalında birileri var, çıkış görevi iptal edildi.")

    async def leave_empty_channel(self, guild):
        """Belirtilen süre sonra boş ses kanalından çıkar."""
        try:
            print(f"{guild.name} sunucusunda ses kanalı boş, 30 saniye sonra çıkılacak.")
            await asyncio.sleep(30)  # 30 saniye bekle
            
            # Tekrar kontrol et, hala boş mu?
            voice_channel = guild.voice_client.channel
            members = [m for m in voice_channel.members if not m.bot]
            
            if not members and guild.voice_client and guild.voice_client.is_connected():
                # Çalan şarkıyı durdur
                if guild.voice_client.is_playing():
                    guild.voice_client.stop()
                
                # Sırayı temizle
                guild_id = guild.id
                if guild_id in self.song_queue:
                    self.song_queue[guild_id].clear()
                
                # Now playing'i temizle
                if guild_id in self.now_playing:
                    self.now_playing[guild_id] = None
                
                # Ses kanalından ayrıl
                await guild.voice_client.disconnect()
                print(f"{guild.name} sunucusunda ses kanalı 30 saniye boyunca boş kaldı, kanaldan çıkıldı.")
        except Exception as e:
            print(f"Boş kanaldan çıkarken hata oluştu: {str(e)}")

    async def play_playlist(self, interaction, playlist_name):
        """Çalma listesini oynatmak için yardımcı metot"""
        try:
            if playlist_name not in self.playlists:
                await interaction.followup.send(f'Çalma listesi **{playlist_name}** bulunamadı!')
                return
            
            playlist = self.playlists[playlist_name]
            if not playlist:
                await interaction.followup.send(f'Çalma listesi **{playlist_name}** boş!')
                return
            
            if not interaction.guild.voice_client:
                if not interaction.user.voice:
                    await interaction.followup.send('Bir ses kanalında olmanız gerekiyor!')
                    return
                await interaction.user.voice.channel.connect()

            self.setup_queue(interaction.guild_id)
            
            # Shuffle modu dosyadan oku
            guild_id_str = str(interaction.guild_id)
            shuffle_enabled = self.shuffle_mode.get(guild_id_str, False)
            
            if shuffle_enabled:
                # Çalma listesinin bir kopyasını oluştur ve karıştır
                shuffled_playlist = list(playlist)
                random.shuffle(shuffled_playlist)
                playlist_to_play = shuffled_playlist
                shuffle_status = "açık"
            else:
                playlist_to_play = playlist
                shuffle_status = "kapalı"
            
            # İlk şarkıyı çal, diğerlerini sıraya ekle
            first_song = playlist_to_play[0]
            player = await YTDLSource.from_url(first_song['url'], loop=self.loop, stream=True)
            
            if not interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(interaction), self.loop))
                self.now_playing[interaction.guild_id] = first_song
                
                # Kalan şarkıları sıraya ekle
                for song in playlist_to_play[1:]:
                    self.song_queue[interaction.guild_id].append(song)
                
                await interaction.followup.send(
                    f'**Çalma listesi oynatılıyor: {playlist_name}**\n'
                    f'Şu an çalıyor: {first_song["title"]}\n'
                    f'Sıraya {len(playlist_to_play)-1} şarkı eklendi\n'
                    f'Karıştırma modu: **{shuffle_status}**'
                )
            else:
                # Tüm şarkıları sıraya ekle
                for song in playlist_to_play:
                    self.song_queue[interaction.guild_id].append(song)
                
                await interaction.followup.send(
                    f'**{playlist_name} çalma listesi sıraya eklendi**\n'
                    f'Sıraya {len(playlist_to_play)} şarkı eklendi\n'
                    f'Karıştırma modu: **{shuffle_status}**'
                )

        except Exception as e:
            await interaction.followup.send(f'Bir hata oluştu: {str(e)}')

class SongSelectView(View):
    def __init__(self, search_results, client, interaction):
        super().__init__(timeout=60)
        self.search_results = search_results[:5]  # İlk 5 sonuç
        self.client = client
        self.original_interaction = interaction

    async def handle_song_select(self, interaction: discord.Interaction):
        custom_id = int(interaction.data['custom_id'])
        selected_song = self.search_results[custom_id]
        
        try:
            if not interaction.guild.voice_client:
                if not interaction.user.voice:
                    await interaction.response.send_message('You need to be in a voice channel!')
                    return
                await interaction.user.voice.channel.connect()

            # Tüm butonları devre dışı bırak
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)

            player = await YTDLSource.from_url(selected_song['url'], loop=self.client.loop)
            song_info = {'url': selected_song['url'], 'title': selected_song['title']}

            if not interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.client.play_next(self.original_interaction), self.client.loop))
                self.client.now_playing[interaction.guild_id] = song_info
                await interaction.followup.send(f'**Now playing:** {selected_song["title"]}')
            else:
                self.client.song_queue[interaction.guild_id].append(song_info)
                await interaction.followup.send(f'**Added to queue:** {selected_song["title"]}')

        except Exception as e:
            await interaction.followup.send(f'An error occurred: {str(e)}')

        self.stop()

class PlayNextView(View):
    def __init__(self, search_results, client, interaction):
        super().__init__(timeout=60)
        self.search_results = search_results[:3]
        self.client = client
        self.original_interaction = interaction

    async def handle_song_select(self, interaction: discord.Interaction):
        custom_id = int(interaction.data['custom_id'])
        selected_song = self.search_results[custom_id]
        
        try:
            if not interaction.guild.voice_client:
                if not interaction.user.voice:
                    await interaction.response.send_message('You need to be in a voice channel!')
                    return
                await interaction.user.voice.channel.connect()

            # Tüm butonları devre dışı bırak
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)

            player = await YTDLSource.from_url(selected_song['url'], loop=self.client.loop)
            song_info = {'url': selected_song['url'], 'title': selected_song['title']}

            if not interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.client.play_next(self.original_interaction), self.client.loop))
                self.client.now_playing[interaction.guild_id] = song_info
                await interaction.followup.send(f'**Now playing:** {selected_song["title"]}')
            else:
                # Sıranın başına ekle
                queue = self.client.song_queue[interaction.guild_id]
                queue_list = list(queue)
                queue_list.insert(0, song_info)
                self.client.song_queue[interaction.guild_id] = deque(queue_list)
                await interaction.followup.send(f'**Will play next:** {selected_song["title"]}')

        except Exception as e:
            await interaction.followup.send(f'An error occurred: {str(e)}')

        self.stop()

class PlaylistSelectView(View):
    def __init__(self, playlists, client, interaction):
        super().__init__(timeout=60)
        self.playlists = playlists
        self.client = client
        self.original_interaction = interaction

    async def handle_playlist_select(self, interaction: discord.Interaction):
        custom_id = interaction.data['custom_id']
        selected_playlist = custom_id
        
        try:
            # Tüm butonları devre dışı bırak
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
            
            # Seçilen çalma listesini oynat
            await self.client.play_playlist(interaction, selected_playlist)
            
        except Exception as e:
            await interaction.followup.send(f'Bir hata oluştu: {str(e)}')
        
        self.stop()

client = MusicBot()

@client.event
async def on_ready():
    print(f'{client.user} olarak giriş yapıldı!')
    
    # Botun durumunu ayarla
    activity = discord.Activity(type=discord.ActivityType.watching, name="içimdeki hasreti")
    await client.change_presence(activity=activity)

@client.tree.command(name="play", description="Play a song, search on YouTube, or add to queue")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    try:
        client.setup_queue(interaction.guild_id)

        # URL kontrolü
        url_pattern = re.compile(
            r'^https?://'  # http:// veya https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ip
            r'(?::\d+)?'  # port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if url_pattern.match(query):
            if not interaction.guild.voice_client:
                if not interaction.user.voice:
                    await interaction.followup.send('You need to be in a voice channel!')
                    return
                await interaction.user.voice.channel.connect()

            player = await YTDLSource.from_url(query, loop=client.loop)
            song_info = {'url': query, 'title': player.title}

            if not interaction.guild.voice_client.is_playing():
                interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    client.play_next(interaction), client.loop))
                client.now_playing[interaction.guild_id] = song_info
                # Son çalan şarkıyı kaydet
                client.update_last_played(interaction.guild_id, song_info)
                await interaction.followup.send(f'**Now playing:** {player.title}')
        else:
            # Arama yap - düzeltilmiş
            # Yazıyor durumunu kaldırdık
            # Doğrudan tam işlenmiş sonuçları al
            search_query = f"ytsearch5:{query}"  # 5 sonuç ara
            data = await client.loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
            
            if not data or 'entries' not in data or not data['entries']:
                await interaction.followup.send('No results found!')
                return
            
            entries = []
            for entry in data['entries'][:5]:  # İlk 5 sonucu al
                entries.append({
                    'url': entry.get('webpage_url', f"https://www.youtube.com/watch?v={entry.get('id')}"),
                    'title': entry.get('title', 'Unknown Title')
                })
        
            view = SongSelectView(entries, client, interaction)
            
            # Her sonuç için buton ekle
            for i, entry in enumerate(entries):
                button = Button(
                    label=f"{i+1}. {entry['title'][:50]}...",
                    custom_id=str(i),
                    style=discord.ButtonStyle.primary,
                    row=0  # Hepsi aynı satırda
                )
                button.callback = view.handle_song_select
                view.add_item(button)

            await interaction.followup.send(
                "**Select a song to play:**\n" + 
                "\n".join([f"{i+1}. {entry['title']}" for i, entry in enumerate(entries)]),
                view=view
            )

    except Exception as e:
        await interaction.followup.send(f'An error occurred: {str(e)}')

@client.tree.command(name="queue", description="Show the current queue")
async def queue(interaction: discord.Interaction):
    if not client.song_queue.get(interaction.guild_id, None):
        await interaction.response.send_message('Sıra boş!')
        return

    queue_list = []
    if client.now_playing[interaction.guild_id]:
        queue_list.append(f"**Şu an çalıyor:** {client.now_playing[interaction.guild_id]['title']}")
    
    for i, song in enumerate(client.song_queue[interaction.guild_id], 1):
        queue_list.append(f"{i}. {song['title']}")

    if queue_list:
        await interaction.response.send_message('\n'.join(queue_list))
    else:
        await interaction.response.send_message('Sıra boş!')

@client.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message('Skipped the current song!')
    else:
        await interaction.response.send_message('Nothing is playing!')

@client.tree.command(name="clear", description="Clear the queue")
async def clear(interaction: discord.Interaction):
    if interaction.guild_id in client.song_queue:
        client.song_queue[interaction.guild_id].clear()
        await interaction.response.send_message('Queue cleared!')
    else:
        await interaction.response.send_message('No queue exists!')

@client.tree.command(name="join", description="Join your voice channel")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message('You need to be in a voice channel!')
        return
    
    await interaction.user.voice.channel.connect()
    await interaction.response.send_message('Joined the voice channel!')

@client.tree.command(name="leave", description="Leave the voice channel and clear everything")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        # Çalan şarkıyı durdur
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
        
        # Sırayı temizle
        if interaction.guild_id in client.song_queue:
            client.song_queue[interaction.guild_id].clear()
        
        # Now playing'i temizle
        if interaction.guild_id in client.now_playing:
            client.now_playing[interaction.guild_id] = None
        
        # Ses kanalından ayrıl
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message('Left the voice channel and cleared everything!')
    else:
        await interaction.response.send_message('Not in a voice channel!')

@client.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message('Paused the song!')
    else:
        await interaction.response.send_message('Nothing is playing!')

@client.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message('Resumed the song!')
    else:
        await interaction.response.send_message('Nothing is paused!')

@client.tree.command(name="addf", description="Add a song to your favorites")
async def addf(interaction: discord.Interaction, url: str, title: str):
    user_id = str(interaction.user.id)
    
    if user_id not in client.favorites:
        client.favorites[user_id] = []
    
    # Şarkıyı favorilere ekle
    song_info = {'url': url, 'title': title}
    client.favorites[user_id].append(song_info)
    client.save_favorites()
    
    await interaction.response.send_message(f'Added **{title}** to your favorites!')

@client.tree.command(name="listf", description="List your favorite songs")
async def listf(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    favorites = client.get_user_favorites(user_id)
    
    if not favorites:
        await interaction.response.send_message("You don't have any favorite songs!")
        return
    
    fav_list = ["**Your Favorite Songs:**"]
    for i, song in enumerate(favorites, 1):
        fav_list.append(f"{i}. {song['title']}")
    
    await interaction.response.send_message('\n'.join(fav_list))

@client.tree.command(name="removef", description="Remove a song from your favorites")
async def removef(interaction: discord.Interaction, number: int):
    user_id = str(interaction.user.id)
    favorites = client.get_user_favorites(user_id)
    
    if not favorites:
        await interaction.response.send_message("You don't have any favorite songs!")
        return
    
    if number < 1 or number > len(favorites):
        await interaction.response.send_message("Invalid song number!")
        return
    
    removed_song = favorites.pop(number - 1)
    client.favorites[user_id] = favorites
    client.save_favorites()
    
    await interaction.response.send_message(f'Removed **{removed_song["title"]}** from your favorites!')

@client.tree.command(name="playf", description="Play a song from your favorites")
async def playf(interaction: discord.Interaction, number: int):
    await interaction.response.defer()
    
    try:
        user_id = str(interaction.user.id)
        favorites = client.get_user_favorites(user_id)
        
        if not favorites:
            await interaction.followup.send("You don't have any favorite songs!")
            return
        
        if number < 1 or number > len(favorites):
            await interaction.followup.send("Invalid song number!")
            return
        
        selected_song = favorites[number - 1]
        
        if not interaction.guild.voice_client:
            if not interaction.user.voice:
                await interaction.followup.send('You need to be in a voice channel!')
                return
            await interaction.user.voice.channel.connect()

        # Yazıyor durumunu kaldırdık
        player = await YTDLSource.from_url(selected_song['url'], loop=client.loop, stream=True)
        song_info = {'url': selected_song['url'], 'title': selected_song['title']}

        if not interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                client.play_next(interaction), client.loop))
            client.now_playing[interaction.guild_id] = song_info
            await interaction.followup.send(f'**Now playing:** {selected_song["title"]}')
        else:
            client.song_queue[interaction.guild_id].append(song_info)
            await interaction.followup.send(f'**Added to queue:** {selected_song["title"]}')

    except Exception as e:
        await interaction.followup.send(f'An error occurred: {str(e)}')

@client.tree.command(name="playn", description="Play a song immediately after the current song")
async def playn(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    try:
        client.setup_queue(interaction.guild_id)

        # URL kontrolü
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if url_pattern.match(query):
            # URL ise direkt işle
            # Yazıyor durumunu kaldırdık
            player = await YTDLSource.from_url(query, loop=client.loop)
            song_info = {'url': query, 'title': player.title}

            if not interaction.guild.voice_client:
                if not interaction.user.voice:
                    await interaction.followup.send('You need to be in a voice channel!')
                    return
                await interaction.user.voice.channel.connect()

            if not interaction.guild.voice_client.is_playing():
                # Hiçbir şey çalmıyorsa direkt çal
                interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    client.play_next(interaction), client.loop))
                client.now_playing[interaction.guild_id] = song_info
                await interaction.followup.send(f'**Now playing:** {player.title}')
            else:
                # Çalan şarkı varsa, sıranın başına ekle
                queue = client.song_queue[interaction.guild_id]
                queue_list = list(queue)  # deque'yu listeye çevir
                queue_list.insert(0, song_info)  # başa ekle
                client.song_queue[interaction.guild_id] = deque(queue_list)  # listeyi tekrar deque'ya çevir
                await interaction.followup.send(f'**Will play next:** {player.title}')
        else:
            # Arama yap - düzeltilmiş
            # Yazıyor durumunu kaldırdık
            # Doğrudan tam işlenmiş sonuçları al
            search_query = f"ytsearch5:{query}"  # 5 sonuç ara
            data = await client.loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
            
            if not data or 'entries' not in data or not data['entries']:
                await interaction.followup.send('No results found!')
                return
            
            entries = []
            for entry in data['entries'][:5]:  # İlk 5 sonucu al
                entries.append({
                    'url': entry.get('webpage_url', f"https://www.youtube.com/watch?v={entry.get('id')}"),
                    'title': entry.get('title', 'Unknown Title')
                })

            view = PlayNextView(entries, client, interaction)
            
            for i, entry in enumerate(entries):
                button = Button(
                    label=f"{i+1}. {entry['title'][:50]}...",
                    custom_id=str(i),
                    style=discord.ButtonStyle.primary,
                    row=0
                )
                button.callback = view.handle_song_select
                view.add_item(button)

            await interaction.followup.send(
                "**Select a song to play next:**\n" + 
                "\n".join([f"{i+1}. {entry['title']}" for i, entry in enumerate(entries)]),
                view=view
            )

    except Exception as e:
        await interaction.followup.send(f'An error occurred: {str(e)}')

@client.tree.command(name="createp", description="Create a new playlist")
async def createp(interaction: discord.Interaction, name: str):
    if name in client.playlists:
        await interaction.response.send_message(f'Bir çalma listesi zaten **{name}** adıyla mevcut!')
        return
    
    client.playlists[name] = []
    client.save_playlists()
    
    await interaction.response.send_message(f'Çalma listesi oluşturuldu: **{name}**')

@client.tree.command(name="addp", description="Add a song to a playlist")
async def addp(interaction: discord.Interaction, playlist_name: str, url: str, title: str):
    if playlist_name not in client.playlists:
        await interaction.response.send_message(f'Çalma listesi **{playlist_name}** bulunamadı!')
        return
    
    song_info = {'url': url, 'title': title}
    client.playlists[playlist_name].append(song_info)
    client.save_playlists()
    
    await interaction.response.send_message(f'**{title}** şarkısı **{playlist_name}** çalma listesine eklendi!')

@client.tree.command(name="removep", description="Remove a song from a playlist")
async def removep(interaction: discord.Interaction, playlist_name: str, number: int):
    if playlist_name not in client.playlists:
        await interaction.response.send_message(f'Çalma listesi **{playlist_name}** bulunamadı!')
        return
    
    playlist = client.playlists[playlist_name]
    if not playlist:
        await interaction.response.send_message(f'Çalma listesi **{playlist_name}** boş!')
        return
    
    if number < 1 or number > len(playlist):
        await interaction.response.send_message("Geçersiz şarkı numarası!")
        return
    
    removed_song = playlist.pop(number - 1)
    client.save_playlists()
    
    await interaction.response.send_message(f'**{removed_song["title"]}** şarkısı **{playlist_name}** çalma listesinden kaldırıldı!')

@client.tree.command(name="listp", description="List all playlists or songs in a playlist")
async def listp(interaction: discord.Interaction, playlist_name: str = None):
    if not client.playlists:
        await interaction.response.send_message("Hiç çalma listesi yok!")
        return
    
    if playlist_name is None:
        # Tüm playlist'leri listele
        playlists = list(client.playlists.keys())
        if not playlists:
            await interaction.response.send_message("Hiç çalma listesi yok!")
            return
        
        await interaction.response.send_message("**Çalma Listeleri:**\n" + "\n".join(playlists))
    else:
        # Belirli bir playlist'in içeriğini listele
        if playlist_name not in client.playlists:
            await interaction.response.send_message(f'Çalma listesi **{playlist_name}** bulunamadı!')
            return
        
        playlist = client.playlists[playlist_name]
        if not playlist:
            await interaction.response.send_message(f'Çalma listesi **{playlist_name}** boş!')
            return
        
        song_list = [f"**Çalma Listesi: {playlist_name}**"]
        for i, song in enumerate(playlist, 1):
            song_list.append(f"{i}. {song['title']}")
        
        await interaction.response.send_message('\n'.join(song_list))

@client.tree.command(name="deletep", description="Delete a playlist")
async def deletep(interaction: discord.Interaction, playlist_name: str):
    if playlist_name not in client.playlists:
        await interaction.response.send_message(f'Çalma listesi **{playlist_name}** bulunamadı!')
        return
    
    del client.playlists[playlist_name]
    client.save_playlists()
    
    await interaction.response.send_message(f'Çalma listesi silindi: **{playlist_name}**')

@client.tree.command(name="playp", description="Play a playlist")
async def playp(interaction: discord.Interaction, playlist_name: str = None):
    await interaction.response.defer()
    
    try:
        # Eğer playlist_name belirtilmişse, direkt o çalma listesini oynat
        if playlist_name:
            await client.play_playlist(interaction, playlist_name)
            return
        
        # Playlist_name belirtilmemişse, tüm çalma listelerini butonlar halinde göster
        playlists = client.playlists
        if not playlists:
            await interaction.followup.send("Hiç çalma listesi yok!")
            return
        
        # Çalma listesi seçme görünümü oluştur
        view = PlaylistSelectView(playlists, client, interaction)
        
        # Her çalma listesi için buton ekle
        for i, playlist_name in enumerate(playlists.keys()):
            button = Button(
                label=f"{playlist_name}",
                custom_id=playlist_name,
                style=discord.ButtonStyle.primary,
                row=i//3  # Her satırda 3 buton olacak şekilde düzenle
            )
            button.callback = view.handle_playlist_select
            view.add_item(button)
        
        await interaction.followup.send(
            "**Oynatmak istediğiniz çalma listesini seçin:**",
            view=view
        )

    except Exception as e:
        await interaction.followup.send(f'Bir hata oluştu: {str(e)}')

@client.tree.command(name="shuffle", description="Karıştırma modunu aç/kapat")
async def shuffle(interaction: discord.Interaction, mode: bool = None):
    guild_id = interaction.guild_id
    guild_id_str = str(guild_id)  # JSON anahtarları string olmalı
    
    # Önce mevcut durumu dosyadan oku
    current_mode = client.shuffle_mode.get(guild_id_str, False)
    
    # Eğer mod belirtilmemişse, mevcut durumu tersine çevir
    if mode is None:
        client.shuffle_mode[guild_id_str] = not current_mode
    else:
        client.shuffle_mode[guild_id_str] = mode
    
    # Değişiklikleri hemen kaydet
    client.save_shuffle_mode()
    
    # Güncel durumu dosyadan oku
    updated_mode = client.shuffle_mode.get(guild_id_str, False)
    status = "açık" if updated_mode else "kapalı"
    
    await interaction.response.send_message(f"Karıştırma modu: **{status}**")

@client.tree.command(name="shuffleq", description="Mevcut sırayı karıştır")
async def shuffleq(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    guild_id_str = str(guild_id)  # JSON anahtarları string olmalı
    
    if guild_id not in client.song_queue or not client.song_queue[guild_id]:
        await interaction.response.send_message("Sırada şarkı yok!")
        return
    
    # Mevcut sırayı karıştır
    queue_list = list(client.song_queue[guild_id])
    random.shuffle(queue_list)
    client.song_queue[guild_id] = deque(queue_list)
    
    # Shuffle modunu açık olarak ayarla ve kaydet
    client.shuffle_mode[guild_id_str] = True
    client.save_shuffle_mode()
    
    await interaction.response.send_message("Sıra karıştırıldı! Karıştırma modu açık olarak ayarlandı.")
    
    # Güncel sırayı göster
    queue_list = []
    if client.now_playing[guild_id]:
        queue_list.append(f"**Şu an çalıyor:** {client.now_playing[guild_id]['title']}")
    
    for i, song in enumerate(client.song_queue[guild_id], 1):
        queue_list.append(f"{i}. {song['title']}")
    
    if len(queue_list) > 1:  # Şu an çalınan şarkı + en az bir şarkı daha varsa
        await interaction.followup.send('\n'.join(queue_list))

@client.tree.command(name="replay", description="Son çalan şarkıyı tekrar çal")
async def replay(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        guild_id_str = str(interaction.guild_id)
        last_song = client.last_played.get(guild_id_str)
        
        if not last_song:
            await interaction.followup.send('Daha önce çalınan bir şarkı bulunamadı!')
            return
        
        if not interaction.guild.voice_client:
            if not interaction.user.voice:
                await interaction.followup.send('Bir ses kanalında olmanız gerekiyor!')
                return
            await interaction.user.voice.channel.connect()

        player = await YTDLSource.from_url(last_song['url'], loop=client.loop, stream=True)
        
        if not interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                client.play_next(interaction), client.loop))
            client.now_playing[interaction.guild_id] = last_song
            await interaction.followup.send(f'**Tekrar çalınıyor:** {last_song["title"]}')
        else:
            client.song_queue[interaction.guild_id].append(last_song)
            await interaction.followup.send(f'**Sıraya eklendi:** {last_song["title"]}')

    except Exception as e:
        await interaction.followup.send(f'Bir hata oluştu: {str(e)}')