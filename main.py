import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl
import os
import asyncio

async def run_bot():
    await bot.start(os.getenv('BOT_TOKEN'))


class Song:
    def __init__(self, title, url):
        self.title = title
        self.url = url

class GuildQueue:
    def __init__(self):
        self.queue = []
        self.now_playing = None
        self.voice_client = None
        self.loop = asyncio.new_event_loop()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)
queues = {}  # key: guild_id, value: GuildQueue
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
    'options': '-vn -sn -dn -f mp3'
}

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} готов!')
    try:
        await bot.tree.sync()
        print('Слэш-команды синхронизированы!')
    except Exception as e:
        print(f'Ошибка синхронизации: {e}')

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = GuildQueue()
    return queues[guild_id]

async def play_next(guild_id):
    queue = get_queue(guild_id)
    if len(queue.queue) == 0:
        queue.now_playing = None
        return

    queue.now_playing = queue.queue.pop(0)
    
    try:
        queue.voice_client.play(
            discord.FFmpegPCMAudio(queue.now_playing.url, executable='ffmpeg', **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), queue.loop)
        )
    except Exception as e:
        print(f'Ошибка воспроизведения: {e}')
        await play_next(guild_id)

@bot.tree.command(name='play', description='Добавить трек или плейлист')
async def play(interaction: discord.Interaction, request: str):
    await interaction.response.defer()
    
    if not interaction.user.voice:
        return await interaction.followup.send('❌ Подключитесь к голосовому каналу!')

    guild_id = interaction.guild.id
    queue = get_queue(guild_id)

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
            info = ydl.extract_info(request, download=False)
            
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
        await play_next(guild_id)

@bot.tree.command(name='skip', description='Пропустить текущий трек')
async def skip(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)
    
    if queue.voice_client and queue.voice_client.is_playing():
        queue.voice_client.stop()
        await interaction.response.send_message('⏭️ Трек пропущен')
    else:
        await interaction.response.send_message('❌ Сейчас ничего не играет')

@bot.tree.command(name='queue', description='Показать текущую очередь')
async def show_queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)
    
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

@bot.tree.command(name='leave', description='Отключиться от голосового канала')
async def leave(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    queue = get_queue(guild_id)
    
    if queue.voice_client:
        await queue.voice_client.disconnect()
        queue.voice_client = None
        queue.queue.clear()
        queue.now_playing = None
        await interaction.response.send_message('✅ Отключился от голосового канала')
    else:
        await interaction.response.send_message('❌ Бот не подключен к голосовому каналу')

if __name__ == '__main__':
    asyncio.run(run_bot())
