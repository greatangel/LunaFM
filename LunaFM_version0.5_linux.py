import discord
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import os
import asyncio
from youtubesearchpython import VideosSearch
import time

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Configuración para yt-dlp
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'ffmpeg_location': 'C:\FFmpeg'  # Actualiza esta ruta
}

queues = {}

DISCONNECT_AFTER = 200  # 300 segundos = 5 minutos (ajusta este valor)
last_activity = {}

# Verificador de inactividad
@tasks.loop(seconds=30)
async def check_inactivity():
    current_time = time.time()
    for guild_id in list(last_activity.keys()):
        guild = bot.get_guild(guild_id)
        if not guild:
            del last_activity[guild_id]
            continue
        
        voice_client = guild.voice_client
        if not voice_client or not voice_client.is_connected():
            del last_activity[guild_id]
            continue
        
        # Calcular tiempo inactivo
        tiempo_inactivo = current_time - last_activity[guild_id]
        
        # Verificar condiciones para desconectar
        if (
            not voice_client.is_playing() and 
            not queues.get(guild_id, []) and 
            tiempo_inactivo >= DISCONNECT_AFTER
        ):
            await voice_client.disconnect()
            if guild_id in queues:
                del queues[guild_id]
            del last_activity[guild_id]
            print(f"Desconectado por inactividad en {guild.name}")

def after_playing(error, guild_id):
    if error:
        print(f'Error: {error}')
    
    if guild_id in queues and queues[guild_id]:
        next_song = queues[guild_id].pop(0)
        
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        
        voice_client = guild.voice_client
        if not voice_client:
            return
        
        ffmpeg_options = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }
        source = discord.FFmpegPCMAudio(next_song['url'], **ffmpeg_options)
        voice_client.play(source, after=lambda e: after_playing(e, guild_id))
        
        coro = next_song['ctx'].send(f"Reproduciendo: {next_song['title']}")
        asyncio.run_coroutine_threadsafe(coro, bot.loop)

         # Actualizar la última actividad al reproducir nueva canción
        last_activity[guild_id] = time.time()
    else:
        # Iniciar temporizador de desconexión
        last_activity[guild_id] = time.time()

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    check_inactivity.start()

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
    else:
        await ctx.send("Debes estar en un canal de voz.")

@bot.command()
async def play(ctx, *, query: str):
    # Verifica que el usuario esté en un canal de voz
    if ctx.author.voice is None:
        await ctx.send("❌ Debes estar en un canal de voz para reproducir música.")
        return

    # Intenta obtener el voice_client actual
    voice_client = ctx.voice_client

    # Si no está conectado, intenta unirte
    if not voice_client:
        try:
            voice_client = await ctx.author.voice.channel.connect()
        except Exception as e:
            await ctx.send(f"❌ No pude conectarme al canal de voz: {e}")
            return

    # Determinar si es URL o búsqueda
    if not query.startswith(('http://', 'https://', 'www.', 'youtube.com', 'youtu.be')):
        # Buscar en YouTube
        search = VideosSearch(query, limit=1)
        result = search.result()
        if not result['result']:
            await ctx.send("❌ No se encontraron resultados.")
            return
        url = result['result'][0]['link']
    else:
        url = query

    # Extraer información de la canción
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        url_audio = info['url']
        title = info.get('title', 'Título desconocido')

    song = {
        'url': url_audio,
        'title': title,
        'ctx': ctx
    }

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    queues[guild_id].append(song)

    # Reproducir si no hay música en curso
    if not voice_client.is_playing():
        next_song = queues[guild_id].pop(0)
        ffmpeg_options = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }
        source = discord.FFmpegPCMAudio(next_song['url'], **ffmpeg_options)
        voice_client.play(source, after=lambda e: after_playing(e, guild_id))
        await ctx.send(f"🎶 Reproduciendo: **{next_song['title']}**")
    else:
        await ctx.send(f"🎵 Añadido a la cola: **{title}**")


@bot.command()
async def skip(ctx):
    voice_client = ctx.voice_client
    
    if not voice_client or not voice_client.is_playing():
        await ctx.send("No hay ninguna canción reproduciéndose")
        return
    
    voice_client.stop()
    await ctx.send("⏩ Canción saltada")

@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    
    if not queues.get(guild_id):
        await ctx.send("La cola está vacía")
        return
    
    queue_list = [f"**{i+1}.** {song['title']}" for i, song in enumerate(queues[guild_id])]
    await ctx.send(f"**Cola de reproducción:**\n" + "\n".join(queue_list))

@bot.command()
async def pause(ctx):
    voice_client = ctx.voice_client
    
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸ Reproducción pausada")
    else:
        await ctx.send("No hay nada reproduciéndose")

@bot.command()
async def resume(ctx):
    voice_client = ctx.voice_client
    
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶ Reproducción reanudada")
    else:
        await ctx.send("La reproducción no está pausada")

@bot.command()
async def remove(ctx, index: int):
    guild_id = ctx.guild.id
    
    if not queues.get(guild_id):
        await ctx.send("La cola está vacía")
        return
    
    if index < 1 or index > len(queues[guild_id]):
        await ctx.send("Número de canción inválido")
        return
    
    removed_song = queues[guild_id].pop(index - 1)
    await ctx.send(f"❌ Canción eliminada: **{removed_song['title']}**")        

@bot.command()
async def clear(ctx):
    guild_id = ctx.guild.id
    
    if not queues.get(guild_id):
        await ctx.send("La cola ya está vacía")
        return
    
    queues[guild_id].clear()
    await ctx.send("🧹 Cola limpiada")

import random

@bot.command()
async def shuffle(ctx):
    guild_id = ctx.guild.id
    
    if not queues.get(guild_id) or len(queues[guild_id]) < 2:
        await ctx.send("No hay suficientes canciones en la cola para mezclar")
        return
    
    random.shuffle(queues[guild_id])
    await ctx.send("🔀 Cola mezclada")

#### Añadir los comandos antes del de leave para llevar un mejor orden        

    # Actualizar actividad al añadir canción
    last_activity[ctx.guild.id] = time.time()

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in queues:
            del queues[guild_id]
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("No estoy en un canal de voz.")

bot.run(TOKEN)
