from os import environ
import discord
from discord_actions import DiscordActions

class DiscordClient(discord.Client):

  def __init__(self):
    super().__init__(intents=discord.Intents(members=True, messages=True)).run(environ['DISCORD_TOKEN'])

  async def on_message(self, message:discord.Message):
    if not message.author.bot:
      DiscordActions(self, message)
