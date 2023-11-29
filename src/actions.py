from asyncio import create_task, Lock
import base64
import datetime
import io
import json
from os import environ, path, listdir, remove
from time import ctime, time
import aiofiles
import googlesearch
from PIL import Image
import requests
import websockets
from helpers import count_tokens
from models_openai import chat_completion_functions, chat_completion

middleware_credentials = base64.b64encode(f"{environ['MIDDLEWARE_USERNAME']}:{environ['MIDDLEWARE_PASSWORD']}".encode()).decode()
middleware_url = f"{environ['MIDDLEWARE_URL']}/?token={middleware_credentials}"

class Mattermost():

  def __init__(self, bot, post:dict):
    self.available_functions = {
      'text_response_default': self.text_response_default,
      'analyze_images': self.analyze_images,
      'channel_summary': self.channel_summary,
      'generate_images': self.generate_images,
      'get_current_weather': self.get_current_weather,
      'instant_self_code_analysis': self.instant_self_code_analysis,
    }
    self.bot = bot
    self.context = None
    self.file_ids = []
    self.instructions = [{'role':'system', 'content':f"Current time is {ctime()}."}]
    self.message = post['message']
    self.post = post
    create_task(self.__post_handler__())

  async def __post_handler__(self):
    channel = await self.bot.channels.get_channel(self.post['channel_id'])
    if channel['type'] == 'G':
      self.instructions[0]['content'] += f" {channel['header']}"
    else:
      self.instructions[0]['content'] += f" {channel['purpose']}"
    bot_user = await self.bot.users.get_user('me')
    self.bot.user_id = bot_user['id']
    self.context = await self.bot.posts.get_thread(self.post['id'])
    if channel['type'] == 'D' or (len(self.context['posts'].values()) == 1 and next(iter(self.context['posts'].values()))['user_id'] == self.bot.user_id) or any(self.bot.name_in_message(post['message']) for post in self.context['posts'].values()):
      return await chat_completion_functions(self.messages_from_context(max_tokens=12288), self.available_functions)

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

  async def stream_reply(self, msgs:list, model='gpt-4-1106-preview', max_tokens=None) -> str:
    if self.post['root_id'] == '':
      reply_to = self.post['id']
    else:
      reply_to = self.post['root_id']
    reply_id = None
    buffer = []
    chunks_processed = []
    start_time = time()
    async with Lock():
      async for chunk in chat_completion(msgs, model=model, max_tokens=max_tokens):
        buffer.append(chunk)
        if (time() - start_time) * 1000 >= 500:
          joined_chunks = ''.join(buffer)
          reply_id = await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'message':''.join(chunks_processed)+joined_chunks, 'file_ids':self.file_ids, 'root_id':reply_to}, reply_id)
          chunks_processed.append(joined_chunks)
          buffer.clear()
          start_time = time()
      if buffer:
        reply_id = await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'message':''.join(chunks_processed)+''.join(buffer), 'file_ids':self.file_ids, 'root_id':reply_to}, reply_id)
    return reply_id

  async def text_response_default(self):
    '''Default function that can be called when a normal text response suffices'''
    self.instructions[0]['content'] += f"You have these functions available: {[f for f in self.available_functions if f != 'text_response_default']}"
    await self.stream_reply(self.messages_from_context())

  async def generic(self, function:str, arguments:dict, content:dict):
    '''Generic function call that can be used with some simpler functions'''
    messages = [
      {"role": "user", "content": self.post['message']},
      {"role": "assistant", "content": None, "function_call": {"name": function, "arguments": json.dumps(arguments)}},
      {"role": "function", "name": function, "content": json.dumps(content)}
    ]
    await self.stream_reply(messages)

  async def analyze_images(self, count_images=0, count_posts=0):
    '''Analyze images in a channel or thread and reply with a description of the image'''
    print(f'analyze_images: count_images:{count_images} count_posts:{count_posts}')
    if self.post['root_id'] == '':
      if count_posts == 0:
        per_page = 200
      else:
        per_page = count_posts+1
      self.context = await self.bot.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':per_page})
    else:
      self.context = await self.bot.posts.get_thread(self.post['id'])
    if 'order' in self.context:
      self.context['order'].sort(key=lambda x: self.context['posts'][x]['create_at'], reverse=True)
    content = [{'type':'text','text':self.post['message']}]
    images = 0
    posts_checked = 0
    for post_id in self.context['order']:
      post = self.context['posts'][post_id]
      if 'file_ids' in post:
        for post_file_id in post['file_ids']:
          print(post_file_id)
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
            images += 1
          if count_images and images >= count_images:
            break
      posts_checked += 1
      if (count_images and images >= count_images) or (count_posts and posts_checked >= count_posts):
        break
    await self.stream_reply([{'role':'user', 'content':content}], model='gpt-4-vision-preview', max_tokens=2048)

  async def channel_summary(self, count:int):
    self.context = await self.bot.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':count})
    msgs = self.messages_from_context()
    await self.generic('channel_summary', {'count':len(msgs)}, msgs)

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

  async def instant_self_code_analysis(self):
    '''Inserts all these source files to the context so they can be analyzed. This is a hacky way to do it, but it works.'''
    self.context = await self.bot.posts.get_thread(self.post['id'])
    files = []
    for file_path in [x for x in listdir() if x.endswith(('.py'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n```\n{content}\n```\n--- END {file_path} ---\n')
    self.instructions[0]['content'] += '\nThis is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic! Abstain from praising or thanking the user, be serious.'+''.join(files) + self.instructions[0]['content']
    await self.stream_reply(self.messages_from_context())
