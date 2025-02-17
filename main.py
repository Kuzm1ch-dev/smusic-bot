import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp as youtube_dl
import os
import asyncio

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
            discord.FFmpegPCMAudio(queue.now_playing.url, executable='ffmpeg'),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id), queue.loop)
        )
    except Exception as e:
        print(f'Ошибка воспроизведения: {e}')
        await play_next(guild_id)

@bot.tree.command(name='play', description='Добавить трек в очередь')
async def play(interaction: discord.Interaction, запрос: str):
    await interaction.response.defer()
    
    # Проверка подключения к голосовому каналу
    if not interaction.user.voice:
        return await interaction.followup.send('❌ Сначала подключитесь к голосовому каналу!')

    guild_id = interaction.guild.id
    queue = get_queue(guild_id)

    # Подключение/перемещение бота
    try:
        channel = interaction.user.voice.channel
        if not queue.voice_client:
            queue.voice_client = await channel.connect()
        elif queue.voice_client.channel != channel:
            await queue.voice_client.move_to(channel)
    except Exception as e:
        return await interaction.followup.send(f'❌ Ошибка подключения: {e}')

    # Поиск трека
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(запрос, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            song = Song(info['title'], info['url'])
    except Exception as e:
        return await interaction.followup.send(f'❌ Не удалось запустить этот трек')

    # Добавление в очередь
    queue.queue.append(song)
    await interaction.followup.send(f'🎶 Добавлено в очередь: **{song.title}** (Позиция: {len(queue.queue)})')

    # Запуск воспроизведения если ничего не играет
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
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    bot.run(os.getenv('BOT_TOKEN'))