import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
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

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
    else:
        await ctx.send("Debes estar en un canal de voz.")

@bot.command()
async def play(ctx, url: str):
    voice_client = ctx.voice_client

    if not voice_client:
        await ctx.invoke(join)
        voice_client = ctx.voice_client

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

    if not voice_client.is_playing():
        next_song = queues[guild_id].pop(0)
        ffmpeg_options = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }
        source = discord.FFmpegPCMAudio(next_song['url'], **ffmpeg_options)
        voice_client.play(source, after=lambda e: after_playing(e, guild_id))
        await ctx.send(f"Reproduciendo: {next_song['title']}")
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