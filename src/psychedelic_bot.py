from threading import Thread
from discord_client import DiscordClient
from mattermost_client import MattermostClient

Thread(target=DiscordClient).start()
MattermostClient()
