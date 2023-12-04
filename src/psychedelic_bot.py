from os import environ
import discord
import actions

class PsychedelicBot(discord.Client):

  def __init__(self, intents):
    self.name = environ['DISCORD_BOT_NAME']
    self.user_id = ''
    super().__init__(intents=intents)

  def name_in_message(self, message:str):
    return self.name in message or self.name == '@bot' and '@chatgpt' in message

  async def on_message(self, message:discord.Message):
    if not message.author.bot:
      actions.PsychedelicBotGeneric(self, message)

PsychedelicBot(intents=discord.Intents(members=True, messages=True)).run(environ['DISCORD_TOKEN'])
