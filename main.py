import discord
from discord import app_commands
from discord.ext import commands
import uvicorn
import yt_dlp as youtube_dl
import os
import asyncio
from dotenv import load_dotenv
import sys

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'nocheckcertificate': True,
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'noplaylist': False,  # Разрешаем плейлисты
    'quiet': True,
    'default_search': 'ytsearch',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -sn -dn'
}

class Song:
    def __init__(self, title, url):
        self.title = title
        self.url = url

class GuildQueue:
    def __init__(self, bot_loop):
        self.queue: list[Song] = []
        self.now_playing: Song = None
        self.voice_client: discord.VoiceClient = None
        self.loop = bot_loop
        
    def clear(self):
        self.queue.clear()
        self.now_playing = None


class SmusicBot:
    def __init__(self, token):
        intents = discord.Intents.all()
        self.token = token
        self.bot = commands.Bot(command_prefix='/', intents=intents)
        self.queues = {}  # key: guild_id, value: GuildQueue
        self.loop = asyncio.new_event_loop()
        pass
    
    async def get_queue(self, guild_id) -> GuildQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue(self.loop)
        return self.queues[guild_id]
    
    def register_commands(self):
        @self.bot.tree.command(name="play", description="Рвать баяны")
        async def play(interaction: discord.Interaction, url: str):
            await self.play_song(interaction, url)
        
        @self.bot.tree.command(name="queue", description="Что следующее?")
        async def queue(interaction: discord.Interaction):
            await self.show_queue(interaction)
            
        @self.bot.tree.command(name="clear", description="Всё нахуй")
        async def clear_queue(interaction: discord.Interaction):
            await self.clear_queue(interaction)
            
        @self.bot.tree.command(name="skip", description="Всё нахуй")
        async def skip(interaction: discord.Interaction):
            await self.skip(interaction)
            
        @self.bot.event
        async def on_ready():
            await self.on_ready()

    async def play_next(self, guild_id):
        queue = await self.get_queue(guild_id)

        if not queue.queue:
            print("Очередь пуста")
            queue.now_playing = None
            await queue.voice_client.disconnect()
            queue.voice_client = None
            return

        queue.now_playing = queue.queue.pop(0)
        try:
            queue.voice_client.play(
                discord.FFmpegPCMAudio(queue.now_playing.url, executable='ffmpeg', **FFMPEG_OPTIONS),
                after=lambda e: self.bot.loop.create_task(self.play_next(guild_id))
            )
        except Exception as e:
            print(f'Ошибка воспроизведения: {e}')
            await self.play_next(guild_id)

    async def on_ready(self):
        print(f'Бот {self.bot.user.name} готов!')
        try:
            await self.bot.tree.sync()
            print('Слэш-команды синхронизированы!')
        except Exception as e:
            print(f'Ошибка синхронизации: {e}')

    async def skip(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        queue = await self.get_queue(guild_id)

        if queue.voice_client and queue.now_playing:
            await self.play_next(guild_id)
            await interaction.response.send_message('⏭️ Трек пропущен')
        else:
            await interaction.response.send_message('❌ Сейчас ничего не играет')<en

    async def clear_queue(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        queue = await self.get_queue(guild_id)
        queue.clear()
        await interaction.response.send_message('🗑️ Очередь очищена')<e

    async def show_queue(self,interaction: discord.Interaction):
        guild_id = interaction.guild.id
        queue = await self.get_queue(guild_id)
        
        if not queue.queue and not queue.now_playing:
            return await interaction.response.send_message('❌ Очередь пуста')
        
        message = []
        if queue.now_playing:
            message.append(f'**Сейчас играет:** {queue.now_playing.title}')
        
        if queue.queue:
            message.append('\n**Очередь:**')
            for i, song in enumerate(queue.queue, 1):
                message.append(f'{i}. {song.title}')
        
        await interaction.response.send_message('\n'.join(message)[:2000])

    async def play_song(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
    
        if not interaction.user.voice:
            return await interaction.followup.send('❌ Подключитесь к голосовому каналу!')

        guild_id = interaction.guild.id
        queue = await self.get_queue(guild_id)

        try:
            channel = interaction.user.voice.channel
            if not queue.voice_client:
                queue.voice_client = await channel.connect()
            elif queue.voice_client.channel != channel:
                await queue.voice_client.move_to(channel)
        except Exception as e:
            return await interaction.followup.send(f'❌ Ошибка подключения: {e}')

        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                added_tracks = 0
                if 'entries' in info:
                    # Обрабатываем плейлист или результаты поиска
                    for entry in info['entries']:
                        if not entry:
                            continue
                        song = Song(
                            title=entry.get('title', 'Без названия'),
                            url=entry.get('url')
                        )
                        queue.queue.append(song)
                        added_tracks += 1
                else:
                    # Одиночный трек
                    song = Song(
                        title=info.get('title', 'Без названия'),
                        url=info.get('url')
                    )
                    queue.queue.append(song)
                    added_tracks += 1

                message = f'🎶 Добавлено треков: **{added_tracks}**'
                if added_tracks > 1:
                    message += '\n_Плейлист добавлен в очередь_'
                await interaction.followup.send(message)

        except Exception as e:
            return await interaction.followup.send(f'❌ Неудалось поставить этот трек =(')

        if not queue.voice_client.is_playing():
            await self.play_next(guild_id)
        
    async def run(self):
        await self.bot.start(self.token)
        
if __name__ == '__main__':
    bot = SmusicBot(token=os.getenv('BOT_TOKEN'))
    bot.register_commands()
    async def run_bot():
        await bot.run()