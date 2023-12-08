from os import environ
from threading import Thread
from discord_client import DiscordClient
from mattermost_client import MattermostClient

if environ['DISCORD_TOKEN']:
  Thread(target=DiscordClient).start()

if environ['MATTERMOST_TOKEN']:
  MattermostClient()
