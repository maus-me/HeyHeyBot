# main.py
"""
HeyHeyBot

Small bot for Discord that will announce when a user joins voice chat to other users in the same channel.
Greeting message is customizable and depends on user (one user - one audio file).
Audio files are stored in the ./data/greetings folder.
Also people can play audio files from the ./data/audio folder by typing !play <filename> in chat.

All audio played by the bot joining the voice channel.
We will store user-audio pairs in the JSON. It will be loaded on bot start.
"""

from bot import run_bot
from webserver import start_webserver

if __name__ == "__main__":
    start_webserver()
    run_bot()