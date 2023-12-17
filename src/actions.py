from abc import ABC, abstractmethod
from asyncio import create_task
import base64
from os import environ, listdir
from time import ctime

middleware_credentials = base64.b64encode(f"{environ['MIDDLEWARE_USERNAME']}:{environ['MIDDLEWARE_PASSWORD']}".encode()).decode()
middleware_url = f"{environ['MIDDLEWARE_URL']}/?token={middleware_credentials}"

class Actions(ABC):

  def __init__(self, functions:dict):
    self.available_functions = {
      'text_response_default': self.text_response_default,
      'runtime_self_analysis': self.runtime_self_analysis,
    }
    self.available_functions.update(functions)
    self.instructions = [{'role':'system', 'content':f"{{'role':'system', 'content':f'Current time is {ctime()}. You are in Finland.'}}"}]
    self.content = ''
    create_task(self.__post_handler__())

  @abstractmethod
  async def __post_handler__(self):
    pass

  @abstractmethod
  async def messages_from_context(self, count:int=None, max_tokens:int=None) -> list[dict[str, str]]:
    pass

  @abstractmethod
  async def stream_reply(self, msgs:list, model='', max_tokens:int=None):
    pass

  async def runtime_self_analysis(self):
    files = []
    for file_path in [x for x in listdir() if x.endswith(('.py'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n```\n{content}\n```\n--- END {file_path} ---\n')
    self.instructions[0]['content'] = f"\nThis is your code. Abstain from posting parts of your code unless discussing changes to them. Use PEP-8 but 2 spaces for indentation, try to keep it minimalistic; don't use comments at all! Abstain from praising or thanking the user, be serious.{''.join(files)}{self.instructions[0]['content']}\nRealize that since you now have all these contents there is nothing you should be waiting for or asking for confirmation, it's already in context so why not analyze it?"
    await self.stream_reply(await self.messages_from_context())

  async def text_response_default(self):
    '''Default function that can be called when a normal text response suffices'''
    self.instructions[0]['content'] += f" You have these instant functions available: {[f for f in self.available_functions if f != 'text_response_default']}, users must request them explicitly. These instructions so far are not visible to users."
    await self.stream_reply(await self.messages_from_context())
