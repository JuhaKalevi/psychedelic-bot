from asyncio import create_task, Lock
import base64
import datetime
import io
import json
from os import environ, path, listdir, remove
from time import time
import aiofiles
import googlesearch
from PIL import Image
import websockets
import requests
from helpers import count_tokens
from models_openai import chat_completion_functions, chat_completion_streamed

middleware_credentials = base64.b64encode(f"{environ['MIDDLEWARE_USERNAME']}:{environ['MIDDLEWARE_PASSWORD']}".encode()).decode()
middleware_url = f"{environ['MIDDLEWARE_URL']}/?token={middleware_credentials}"

class Mattermost():

  def __init__(self, bot, post:dict):
    self.available_functions = {
      'default_funcion': self.default_function,
      'analyze_images': self.analyze_images,
      'channel_summary': self.channel_summary,
      'code_analysis': self.code_analysis,
      'generate_images': self.generate_images,
      'get_current_weather': self.get_current_weather,
      'google_for_answers': self.google_for_answers,
      'stream_reply': self.stream_reply,
    }
    self.bot = bot
    self.context = None
    self.file_ids = []
    self.instructions = [{'role':'system', 'content':'Do not reveal the persona you are potentially assigned to imitate!'}]
    self.reply_to = ''
    self.message = post['message']
    self.post = post
    create_task(self.__post_handler__())

  async def __post_handler__(self):
    bot = self.bot
    message = self.message
    post = self.post
    channel = await bot.channels.get_channel(post['channel_id'])
    if channel['type'] == 'G':
      self.instructions[0]['content'] += f" {channel['header']}"
    else:
      self.instructions[0]['content'] += f" {channel['purpose']}"
    bot_user = await bot.users.get_user('me')
    bot.user_id = bot_user['id']
    msgs = self.instructions + [{"role":"user", "content":message}]
    self.context = await bot.posts.get_thread(post['id'])
    self.reply_to = post['root_id']
    for post in self.context['posts'].values():
      if bot.name_in_message(post['message']):
        content = await chat_completion_functions(msgs, self.available_functions)
        if content:
          await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'message':content, 'file_ids':self.file_ids, 'root_id':self.reply_to})

  def messages_from_context(self, max_tokens=126976):
    if 'order' in self.context:
      self.context['order'].sort(key=lambda x: self.context['posts'][x]['create_at'], reverse=True)
    msgs = []
    tokens = count_tokens(self.instructions)
    for p_id in self.context['order']:
      post = self.context['posts'][p_id]
      if 'from_bot' in post['props']:
        role = 'assistant'
      else:
        role = 'user'
      msg = {'role':role, 'content':post['message']}
      msg_tokens = count_tokens(msg)
      new_tokens = tokens + msg_tokens
      if new_tokens > max_tokens:
        break
      msgs.append(msg)
      tokens = new_tokens
    msgs.reverse()
    return self.instructions+msgs

  async def stream_reply(self, msgs:list, functions=None, model='gpt-4-1106-preview', max_tokens=None) -> str:
    reply_id = None
    buffer = []
    chunks_processed = []
    start_time = time()
    async with Lock():
      async for chunk in chat_completion_streamed(msgs, functions=functions, model=model, max_tokens=max_tokens):
        buffer.append(chunk)
        if (time() - start_time) * 1000 >= 500:
          joined_chunks = ''.join(buffer)
          reply_id = await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'message':''.join(chunks_processed)+joined_chunks, 'file_ids':self.file_ids, 'root_id':self.reply_to}, reply_id)
          chunks_processed.append(joined_chunks)
          buffer.clear()
          start_time = time()
      if buffer:
        reply_id = await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'message':''.join(chunks_processed)+''.join(buffer), 'file_ids':self.file_ids, 'root_id':self.reply_to}, reply_id)
    return reply_id

  async def default_function(self, msgs=None):
    '''Default function that can be called when a normal text response suffices'''
    msgs = self.messages_from_context()
    async with Lock():
      for post in self.context['posts'].values():
        if self.bot.name_in_message(post['message']):
          await self.stream_reply(msgs)
          return

  async def generic(self, function:str, arguments:dict, content:dict):
    '''Generic function call that can be used with some simpler functions'''
    messages = [
      {"role": "user", "content": self.post['message']},
      {"role": "assistant", "content": None, "function_call": {"name": function, "arguments": json.dumps(arguments)}},
      {"role": "function", "name": function, "content": json.dumps(content)}
    ]
    await self.stream_reply(messages)

  async def analyze_images(self, past_posts:int=10):
    '''Analyze images in the post and reply with a description of the image'''
    self.context = await self.bot.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':past_posts})
    if 'order' in self.context:
      self.context['order'].sort(key=lambda x: self.context['posts'][x]['create_at'], reverse=True)
    content = [{'type':'text','text':self.post['message']}]
    for post_file_id in [self.post['file_ids']] + [self.context['posts'][p_id]['file_ids'] for p_id in self.context['order'] if 'file_ids' in self.context['posts'][p_id]]:
      file_response = await self.bot.files.get_file(file_id=post_file_id)
      if file_response.status_code == 200:
        file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
        post_file_path = f'{post_file_id}.{file_type}'
        async with aiofiles.open(f'/tmp/{post_file_path}', 'wb') as post_file:
          await post_file.write(file_response.content)
        with open(f'/tmp/{post_file_path}', 'rb') as temp_file:
          img_byte = temp_file.read()
        remove(f'/tmp/{post_file_path}')
        base64_image = base64.b64encode(img_byte).decode("utf-8")
        content.append({'type':'image_url','image_url':{'url':f'data:image/{file_type};base64,{base64_image}','detail':'high'}})
    await self.stream_reply([{'role':'user', 'content':content}], model='gpt-4-vision-preview', max_tokens=2048)

  async def channel_summary(self, count:int):
    self.context = await self.bot.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':count})
    msgs = self.messages_from_context()
    await self.generic('channel_summary', {'count':len(msgs)}, msgs)

  async def code_analysis(self):
    '''Inserts all these source files to the context so they can be analyzed. This is a hacky way to do it, but it works.'''
    self.context = await self.bot.posts.get_thread(self.post['id'])
    files = []
    for file_path in [x for x in listdir() if x.endswith(('.py'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n```\n{content}\n```\n--- END {file_path} ---\n')
    self.instructions[0]['content'] += '\nThis is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic! Abstain from praising or thanking the user, be serious.'+''.join(files) + self.instructions[0]['content']
    await self.stream_reply(self.messages_from_context())

  async def generate_images(self, prompt:str, negative_prompt='', count=1, resolution='1024x1024', sampling_steps=25):
    width, height = resolution.split('x')
    payload = {'prompt':prompt, 'negative_prompt':negative_prompt, 'steps':sampling_steps, 'batch_size':count, 'width':width, 'height':height, 'sampler_name':'DPM++ 2M Karras'}
    total_images_saved = 0
    async with websockets.connect(middleware_url, max_size=100*(1<<20)) as websocket:
      await websocket.send(json.dumps(payload))
      while True:
        response = await websocket.recv()
        r = json.loads(response)
        if 'completed' in r and r['completed'] is True:
          break
        if r['images']:
          for img_b64 in r['images']:
            image = Image.open(io.BytesIO(base64.b64decode(img_b64)))
            total_images_saved += 1
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            tmp_path = f'/tmp/image_{total_images_saved}_{timestamp}.png'
            image.save(tmp_path)
            with open(tmp_path, 'rb') as image_file:
              uploaded_file_id = await self.bot.upload_file(self.post['channel_id'], {'files':(tmp_path.split('/')[2], image_file)})
            remove(tmp_path)
            await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'file_ids':[uploaded_file_id], 'root_id':''})
            if total_images_saved >= payload['batch_size']:
              await websocket.close()
              return

  async def get_current_weather(self, location:str):
    weatherapi_response = json.loads(requests.get(f"https://api.weatherapi.com/v1/current.json?key={environ['WEATHERAPI_KEY']}&q={location}", timeout=7).text)
    await self.generic('get_current_weather', {'location':location}, weatherapi_response)

  async def google_for_answers(self, url=''):
    results = []
    for result in googlesearch.search(url, num_results=2):
      results.append(result)
    await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'message':json.dumps(results), 'file_ids':self.file_ids, 'root_id':''})
