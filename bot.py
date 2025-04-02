#!/usr/bin/env python3


# bot.py

# necessary imports
import discord
import os
import asyncio

from discord import app_commands
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


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        MY_GUILD = discord.Object(id=config['guild_id'])
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


client = MyClient(intents=intents)

'''
{filename: {'source': <discord.PCMVolumeTransformer>, 'duration': <int>}}
'''
sounds = {}


def run_bot():
    client.run(config['token'])


@client.event
async def on_ready():
    logger.info('======')
    logger.info(f'Bot logged in as {client.user.name} (ID: {client.user.id})')
    logger.info(f'Connected to {len(client.guilds)} servers: {", ".join([guild.name for guild in client.guilds])}')
    logger.info(
        f'Bot is ready. Rich presence: {config["continue_presence"]}, '
        f'arrival announce: {config["arrival_announce"]}, '
        f'muting announce: {config["muting_announce"]}, '
        f'leaving announce: {config["leaving_announce"]}'
    )
    logger.info('======')


# Play audio file from ./data/audio folder
async def wav_length(audio_file):
    with contextlib.closing(wave.open(audio_file, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        audio_len = frames / float(rate)
    return audio_len

# We are storing audio files in the dictionary to avoid opening the same file multiple times
async def cached_sounds(audio_file):
    if audio_file not in sounds:
        sounds[audio_file] = {
            'source': audio_file,
            'duration': await wav_length(audio_file)
        }
        logger.info(f'Playing {audio_file}')
    else:
        logger.info(f'Playing {audio_file} from cache')
    return sounds[audio_file]['source'], sounds[audio_file]['duration']


async def play(client, audio_file, audio_len=5, default='./data/greetings/hello.wav'):
    try:
        # Check to see if the audio_file exists
        if not os.path.isfile(audio_file):
            # If the audio file does not exist, check to see if the default file exists
            if os.path.exists(default):
                # Attribute the default file to the audio_file
                audio_file = default
            else:
                logger.warning(f'Audio file {audio_file} does not exist')
                return

        sound, audio_len = await cached_sounds(audio_file)
        sound = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound), volume=1)

        # Check if the bot is already playing audio
        if client.voice_clients and client.voice_clients[0].is_playing():
            client.voice_clients[0].stop()

        # Play the audio file
        client.voice_clients[0].play(sound, after=lambda e: logger.exception('Player error') if e else None)
        await asyncio.sleep(audio_len + 1)
    except discord.errors.ClientException as e:
        logger.error(f'Error playing audio file (ClientException): {e}')
        return
    except Exception as e:
        logger.error(f'Error playing audio file: {e}')
        return


# List all audio files in ./data/audio folder
async def list_audio_files(sort=True, extensions=None):
    if extensions is None:
        extensions = ['.wav', '.mp3']
    # List all audio files in the ./data/audio folder and return the file names
    audio_files = {}

    for file in os.listdir('./data/audio'):
        # if extension match
        if any(file.endswith(ext) for ext in extensions):
            # add file to dictionary with filename as key and extension as value
            filename, ext = os.path.splitext(file)
            audio_files[filename] = ext

    if sort:
        audio_files = dict(sorted(audio_files.items()))

    logger.debug(f'{audio_files}')
    return audio_files

# Disconnect from voice channel
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
    if member.id == client.user.id or member.bot:
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
            await play(client, f'./data/greetings/{member.name}', default='./data/greetings/hello.wav')
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
            await play(client, f'./data/leavings/{member.name}', audio_len=1, default='./data/leavings/bye.wav')
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
            await play(client, f'./data/greetings/{member.name}', default='./data/greetings/hello.wav')
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
            await play(client, f'./data/mutings/{member.name}', default='./data/mutings/muted.wav')
            # Disconnect from the voice channel
            await vc_disconnect(client)


# Process button press
@client.event
async def on_interaction(interaction):
    # Get audio file name
    audio_file = interaction.data['custom_id']

    # if interaction.data['label'] == stop_button:
    #     # If audio is playing
    #     if client.voice_clients and client.voice_clients[0].is_playing():
    #         client.voice_clients[0].stop()
    #         await interaction.response.send_message(f'⏹️ Stopped', ephemeral=True, delete_after=2)
    #     else:
    #         await interaction.response.send_message(f'⭕ Nothing to stop', ephemeral=True, delete_after=2)
    # else:
    audio_len = sounds.get(f'./data/audio/{audio_file}', {}).get('duration', 1)  # audio length from cache
    if interaction.user.voice is None:
        await interaction.response.send_message(f'⭕ You are not in voice channel', ephemeral=True, delete_after=2)
        return
    await interaction.response.send_message(f'▶️ Playing: {audio_file}', ephemeral=True, delete_after=audio_len)

    # Join the voice channel
    channel = interaction.user.voice.channel

    # Check if bot is already in the channel
    if not client.voice_clients:
        # If bot is already in the channel, do nothing
        logger.info(f'Bot not in channel, {channel.name}')
    try:
        await channel.connect()
    except discord.errors.ClientException:
        pass
    # Play audio file
    await play(client, f'./data/audio/{audio_file}')
    # # Delete message
    # await interaction.message.delete()
    # Disconnect from the voice channel
    await vc_disconnect(client)


@client.tree.command()
async def playsound(interaction: discord.Interaction):
    """Plays a sound."""
    # Get list of audio files
    audio_files = await list_audio_files()

    # Split to 25 files per button
    buttons_groups = [list(audio_files.items())[i:i + 25] for i in range(0, len(audio_files), 25)]
    for group in buttons_groups:
        # Create buttons
        buttons = []
        for filename, ext in group:
            filename_with_ext = f'{filename}{ext}'
            buttons.append(discord.ui.Button(label=filename, custom_id=filename_with_ext))
        # Create view
        view = discord.ui.View()
        for button in buttons:
            view.add_item(button)
        # Send message
        await interaction.response.send_message('', view=view)


@client.tree.command()
@app_commands.describe(
    first_value='The first value you want to add something to',
    second_value='The value you want to add to the first value',
)
async def add(interaction: discord.Interaction, first_value: int, second_value: int):
    """Adds two numbers together."""
    await interaction.response.send_message(f'{first_value} + {second_value} = {first_value + second_value}')
