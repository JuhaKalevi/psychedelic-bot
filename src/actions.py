from abc import ABC, abstractmethod
from asyncio import create_task
import base64
from os import environ, listdir

middleware_credentials = base64.b64encode(f"{environ['MIDDLEWARE_USERNAME']}:{environ['MIDDLEWARE_PASSWORD']}".encode()).decode()
middleware_url = f"{environ['MIDDLEWARE_URL']}/?token={middleware_credentials}"

class Actions(ABC):

  def __init__(self, functions:dict):
    self.available_functions = {
      'Chat': self.chat,
      'analyze_self': self.analyze_self
    }
    self.available_functions.update(functions)
    self.top_instructions = []
    self.bottom_instructions = []
    self.content = ''
    create_task(self.process_event())

  @abstractmethod
  async def process_event(self):
    pass

  @abstractmethod
  async def recall_context(self, count:int=None, max_tokens:int=None):
    pass

  @abstractmethod
  async def stream_reply(self, msgs:list):
    pass

  async def analyze_self(self):
    files = []
    for file_path in [x for x in listdir() if x.endswith(('.py'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n```\n{content}\n```\n--- END {file_path} ---\n')
    self.top_instructions[0]['content'] = "This mode is for analyzing your own functionality by injecting your source files to this context when the user talks about them. There is nothing you can do to activate this mode, it's automatic and already happening!"
    self.bottom_instructions[0]['content'] = f"\nThis is your code. Abstain from posting parts of your code unless discussing changes to them. Use PEP-8 but 2 spaces for indentation, try to keep it minimalistic; don't use comments at all! Abstain from praising or thanking the user, be serious.{''.join(files)}{self.bottom_instructions[0]['content']}\nRealize that since you now have all these contents there is nothing you should be waiting for or asking for confirmation, it's already in context so why not analyze it? NEVER REPLY JUST 0 OR 1 TO ANYTHING, ALWAYS ANALYZE THE CONTEXT AND REPLY WITH A MESSAGE THAT IS APPROPRIATE FOR THE CONTEXT!"
    await self.stream_reply(await self.recall_context())

  async def chat(self):
    self.bottom_instructions[0]['content'] += f" You have these instant functions available: {[f for f in self.available_functions if f != 'chat']}. Please refrain from mentioning these functions here, you have other modes for that."
    await self.stream_reply(await self.recall_context())
