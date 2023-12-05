from abc import ABC, abstractmethod
from asyncio import create_task
import base64
import json
from os import environ, listdir
from time import ctime
import requests

middleware_credentials = base64.b64encode(f"{environ['MIDDLEWARE_USERNAME']}:{environ['MIDDLEWARE_PASSWORD']}".encode()).decode()
middleware_url = f"{environ['MIDDLEWARE_URL']}/?token={middleware_credentials}"
system_instruction = {'role':'system', 'content':f"Current time is {ctime()}. Don't mention that you are an AI, everybody knows it!"}

class Actions(ABC):

  def __init__(self, client, functions:dict):
    self.client = client
    self.available_functions = functions + {
      'text_response_default': self.text_response_default,
      'channel_summary': self.channel_summary,
      'get_current_weather': self.get_current_weather,
      'instant_self_code_analysis': self.instant_self_code_analysis,
    }
    self.instructions = [{'role':'system', 'content':f"{system_instruction}"}]
    self.content = ''
    create_task(self.__post_handler__())

  @abstractmethod
  async def __post_handler__(self):
    pass

  async def channel_summary(self, count:int):
    msgs = await self.messages_from_context(count)
    await self.generic('channel_summary', {'count':len(msgs)}, msgs)

  async def generic(self, function:str, arguments:dict, response:dict):
    '''Generic function call that can be used with some simpler functions'''
    messages = [
      {"role": "user", "content": self.content},
      {"role": "assistant", "content": None, "function_call": {"name": function, "arguments": json.dumps(arguments)}},
      {"role": "function", "name": function, "content": json.dumps(response)}
    ]
    await self.stream_reply(messages)

  async def get_current_weather(self, location:str):
    weatherapi_response = json.loads(requests.get(f"https://api.weatherapi.com/v1/current.json?key={environ['WEATHERAPI_KEY']}&q={location}", timeout=7).text)
    await self.generic('get_current_weather', {'location':location}, weatherapi_response)

  async def instant_self_code_analysis(self):
    '''Inserts all these source files to the context so they can be analyzed. This is a hacky way to do it, but it works.'''
    files = []
    for file_path in [x for x in listdir() if x.endswith(('.py'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n```\n{content}\n```\n--- END {file_path} ---\n')
    self.instructions[0]['content'] = f"\nThis is your code. Abstain from posting parts of your code unless discussing changes to them. Use PEP-8 but 2 spaces for indentation, try to keep it minimalistic; don't use comments at all! Abstain from praising or thanking the user, be serious.{''.join(files)}{self.instructions[0]['content']}"
    await self.stream_reply(self.messages_from_context())

  @abstractmethod
  async def messages_from_context(self, count:int=None, max_tokens:int=None) -> list[dict[str, str]]:
    pass

  @abstractmethod
  async def stream_reply(self, msgs:list, model='gpt-3.5-turbo-16k', max_tokens:int=None):
    pass

  async def text_response_default(self):
    '''Default function that can be called when a normal text response suffices'''
    self.instructions[0]['content'] += f" You have these functions available: {[f for f in self.available_functions if f != 'text_response_default']}"
    await self.stream_reply(self.messages_from_context())
