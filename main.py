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

import threading
from bot import run_bot
from webserver import start_webserver

def start_webserver_thread():
    start_webserver()

if __name__ == "__main__":
    webserver_thread = threading.Thread(target=start_webserver_thread)
    webserver_thread.start()
    run_bot()