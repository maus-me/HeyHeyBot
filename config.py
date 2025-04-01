# config.py

import os
from dotenv import load_dotenv

load_dotenv()

def get_config():
    def check_val(value, default=True):
        if value is not None:
            if type(value) == bool:
                return value
            if value.lower() == 'true':
                value = True
            else:
                value = False
        else:
            value = default
        return value

    def check_loglevel(value):
        if value is not None:
            if value.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                return value.upper()
        return 'INFO'

    config = {
        'token': os.getenv('DISCORD_TOKEN'),
        'continue_presence': check_val(os.getenv('DISCORD_CONTINUE_PRESENCE'), default=False),
        'arrival_announce': check_val(os.getenv('DISCORD_ARRIVAL_ANNOUNCE')),
        'muting_announce': check_val(os.getenv('DISCORD_MUTING_ANNOUNCE')),
        'leaving_announce': check_val(os.getenv('DISCORD_LEAVING_ANNOUNCE')),
        'loglevel': check_loglevel(os.getenv('DISCORD_LOGLEVEL', 'WARNING'))
    }

    return config