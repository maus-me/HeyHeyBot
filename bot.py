#!/usr/bin/env python3


# bot.py

# necessary imports
import discord
import os
import asyncio
from discord.ext import commands
import logging
import wave
import contextlib
from logging.handlers import RotatingFileHandler
from config import get_config

config = get_config()

# logging (rotate log every 1 MB, keep 5 old logs)
logger = logging.getLogger('HeyHeyBot')
logger.setLevel(config['loglevel'])
handler = RotatingFileHandler('logs/heyheybot.log', maxBytes=1000000, backupCount=5, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
logger.addHandler(handler)

# start bot
intents = discord.Intents.default()
intents.all()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.presences = True
intents.guilds = True

client = commands.Bot(
    command_prefix=commands.when_mentioned_or('!'),
    description='HeyHeyBot',
    intents=intents
)

'''
TODO: Move these to something not global
'''
stop_button = '⏹️ Stop '
sounds = {}  # {filename: {'source': <discord.PCMVolumeTransformer>, 'duration': <int>}}


def run_bot():
    client.run(config['token'])


@client.event
async def on_ready():
    logger.info('======')
    logger.info(f'Bot logged in as {client.user.name} (ID: {client.user.id})')
    logger.info(f'Connected to {len(client.guilds)} servers: {", ".join([guild.name for guild in client.guilds])}')
    logger.info(
        f'Bot is ready. Rich presence: {config["continue_presence"]}, arrival announce: {config["arrival_announce"]}, muting announce: {config["muting_announce"]}, leaving announce: {config["leaving_announce"]}')
    logger.info('======')


# Play audio file from ./data/audio folder
async def wav_length(audio_file):
    with contextlib.closing(wave.open(audio_file, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        audio_len = frames / float(rate)
    return audio_len


# returns BufferedIOBase from given sound path
async def get_buffered_io(file):
    return open(file, 'rb')


# We are storing audio files in the dictionary to avoid opening the same file multiple times
async def cached_sounds(audio_file):
    if audio_file not in sounds:
        sounds[audio_file] = {
            'source': audio_file,
            'duration': await wav_length(audio_file)
        }
        logger.debug(f'Playing {audio_file}')
    else:
        logger.debug(f'Playing {audio_file} from cache')
    return sounds[audio_file]['source'], sounds[audio_file]['duration']


@client.command()
async def play(client, audio_file, audio_len=5, default='./data/greetings/hello.wav'):
    try:
        # Play audio file
        if not os.path.isfile(audio_file):
            audio_file = default
        sound, audio_len = await cached_sounds(audio_file)
        sound = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound), volume=1)
        client.voice_clients[0].play(sound, after=lambda e: logger.exception(f'Player error') if e else None)
        # wait until audio is played
        await asyncio.sleep(audio_len + 1)
    except discord.errors.ClientException as e:
        # if bot is already playing audio file
        if 'Already playing audio' in str(e):
            # stop playing
            client.voice_clients[0].stop()
            # play audio file
            await play(client, audio_file, audio_len, default)
        else:
            logger.error(f'Error playing audio file (ClientException): {e}')
            return
    except Exception as e:
        logger.error(f'Error playing audio file: {e}')
        return


# List all audio files in ./data/audio folder
async def list_audio_files(sort=True):
    audio_files = []
    for file in os.listdir('./data/audio'):
        if file.endswith('.wav'):
            file = file[:-4]
            audio_files.append(file)
    if sort:
        audio_files.sort()
    return audio_files


# Disconnect from voice channel
@client.command()
async def vc_disconnect(client, force=False):
    try:
        if config["continue_presence"] and not force:
            # check if any user is in a current voice channel
            current_voice_channel = client.voice_clients[0].channel
            if len(current_voice_channel.members) == 1:
                # if no users in a current voice channel, disconnect
                logger.info(f'No users in {current_voice_channel.name}, disconnecting')
                await client.voice_clients[0].disconnect()
            else:
                # if users in a current voice channel, do nothing
                return
        await client.voice_clients[0].disconnect()
    except Exception as e:
        logger.warning(f'Error disconnecting from voice channel: {e}')


async def is_same_channel(client, channel):
    # Check if user joins same voice channel as bot currently in
    # We don't want to play audio if person joins another voice channel
    bot_current_vc = client.voice_clients[0].channel if client.voice_clients else None
    logger.info(f'User joined {channel}, bot in {bot_current_vc}')
    if bot_current_vc is None:
        print('bot_current_vc is None')
        return True
    if bot_current_vc != channel:
        print('not same channel')
        return False
    print('same channel')
    return True


# logger.info username and channel name when user joins voice channel
@client.event
async def on_voice_state_update(member, before, after):
    # If bot ignore
    if member.id == client.user.id:
        return
    # If other bot ignore
    if member.bot:
        return
    if before.channel is None and after.channel is not None:
        if config["arrival_announce"]:
            # When user joins voice channel (user was not in voice channel before)
            logger.info(f'{member.name} joined {after.channel.name}')
            # Join the same voice channel
            channel = after.channel
            try:
                await channel.connect()
            except:
                pass
            if config["continue_presence"] and not await is_same_channel(client, channel):
                return
            # Play audio file
            await play(client, f'./data/greetings/{member.name}.wav', default='./data/greetings/hello.wav')
            # Disconnect from the voice channel
            await vc_disconnect(client)
    elif before.channel is not None and after.channel is None:
        if config["leaving_announce"]:
            # When user leaves voice channel (user was in voice channel before)
            logger.info(f'{member.name} left {before.channel.name}')
            # Leave the voice channel announce
            channel = before.channel
            try:
                await channel.connect()
            except:
                pass
            if config["continue_presence"] and not await is_same_channel(client, channel):
                return
            # Play audio file
            await play(client, f'./data/leavings/{member.name}.wav', audiolen=1, default='./data/leavings/bye.wav')
            # Disconnect from the voice channel
            await vc_disconnect(client)
    elif before.channel != after.channel:
        if config["arrival_announce"]:
            # When user moves from one voice channel to another
            logger.info(f'{member.name} moved from {before.channel.name} to {after.channel.name}')
            # Disconnect from the previous voice channel
            await vc_disconnect(client, force=True)
            # Join the new voice channel
            try:
                await after.channel.connect()
            except Exception as e:
                logger.error(f'Error joining {after.channel.name}: {e}')
            if config["continue_presence"] and not await is_same_channel(client, after.channel):
                return
            # Play audio file
            await play(client, f'./data/greetings/{member.name}.wav', default='./data/greetings/hello.wav')
            # Disconnect from the voice channel
            await vc_disconnect(client)
    else:
        if config["muting_announce"]:
            # When user mutes/unmutes
            logger.info(f'{member.name} muted/unmuted')
            # Join the voice channel
            channel = after.channel
            try:
                await channel.connect()
            except:
                pass
            if config["continue_presence"] and not await is_same_channel(client, channel):
                return
            # Play audio file
            await play(client, f'./data/mutings/{member.name}.wav', default='./data/mutings/muted.wav')
            # Disconnect from the voice channel
            await vc_disconnect(client)


# Process button press
@client.event
async def on_interaction(interaction):
    # Get audio file name
    audio_file = interaction.data['custom_id']
    if audio_file == stop_button:
        client.voice_clients[0].stop()
        await interaction.response.send_message(f'⏹️ Stopped', ephemeral=True, silent=True, delete_after=1)
    try:
        audio_len = sounds[f'./data/audio/{audio_file}.wav']['duration']  # audio length from cache
    except:
        audio_len = 1  # default audio length
    await interaction.response.send_message(f'▶️ Playing: {audio_file}', ephemeral=True, silent=True,
                                            delete_after=audio_len)
    # Join the voice channel
    if interaction.user.voice is None:
        await interaction.response.send_message(f'⭕ You are not in voice channel', ephemeral=True, delete_after=3)
        return
    channel = interaction.user.voice.channel
    try:
        await channel.connect()
    except:
        pass
    # Play audio file
    await play(client, f'./data/audio/{audio_file}.wav')
    # # Delete message
    # await interaction.message.delete()
    # Disconnect from the voice channel
    await vc_disconnect(client)


# Display buttons with audio files when user types !playsound
@client.event
async def on_message(message):
    if message.content.startswith('!playsound'):
        # Get list of audio files
        audio_files = await list_audio_files()
        # Append stop button
        audio_files.append(stop_button)
        # Split to 25 files per button
        buttons_groups = [audio_files[i:i + 25] for i in range(0, len(audio_files), 25)]
        for group in buttons_groups:
            # Create buttons
            buttons = []
            for file in group:
                buttons.append(discord.ui.Button(label=file, custom_id=file))
            # Create view
            view = discord.ui.View()
            for button in buttons:
                view.add_item(button)
            # Send message
            await message.channel.send('', view=view)
    await client.process_commands(message)
