from os import environ
from threading import Thread
from discord_client import DiscordClient
from mattermost_client import MattermostClient

if environ.get('DISCORD_TOKEN'):
  Thread(target=DiscordClient).start()

if environ.get('MATTERMOST_TOKEN'):
  MattermostClient()
