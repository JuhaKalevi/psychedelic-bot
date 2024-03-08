import datetime
import io
import json
from os import environ, path, remove
from time import ctime, time
from asyncio import Lock
import base64
import aiofiles
import websockets
from PIL import Image, UnidentifiedImageError
import mattermostdriver
from actions import middleware_url, Actions
from helpers import base64_image_from_file, base64_images_from_pdf_file, count_image_tokens, count_tokens
from openai_models import react, chat_completion

class MattermostActions(Actions):

  def __init__(self, client:mattermostdriver.AsyncDriver, post:dict):
    super().__init__({
      'generate_images': self.generate_images
    })
    self.client = client
    self.file_ids = []
    self.top_instructions = [{'role':'system', 'content':f"Current time is {ctime()}. You are a helpful & concise Mattermost chatbot in Finland."}]
    self.bottom_instructions = [{'role':'assisant', 'content':''}]
    self.model = environ.get('MODEL_GOOD', 'gpt-4-0125-preview')
    self.post = post
    self.content = post['message']

  async def process_event(self):
    channel = await self.client.channels.get_channel(self.post['channel_id'])
    if channel['type'] == 'G' and channel['header']:
      self.top_instructions[0]['content'] += f"\nChannel name: {channel['name']}\nHeader: {channel['header']}"
    else:
      if channel['purpose']:
        self.top_instructions[0]['content'] += f"\nPurpose: {channel['purpose']}"
        self.bottom_instructions[0]['content'] = f"Ok, sure, I'll read my instructions again: {channel['purpose']}"
      if channel['header']:
        self.top_instructions[0]['content'] += f"\nChannel name: {channel['name']}\nHeader: {channel['header']}"
    bot_user = await self.client.users.get_user('me')
    self.client.user_id = bot_user['id']
    self.thread = await self.client.posts.get_thread(self.post['id'])
    if channel['type'] == 'D' or (len(self.thread['posts'].values()) == 1 and next(iter(self.thread['posts'].values()))['user_id'] == self.client.user_id) or any(self.client.name_in_message(post['message']) for post in self.thread['posts'].values()):
      return await react(await self.recall_context(vision=False), self.available_functions)

  async def recall_context(self, count=None, max_tokens=126976, vision=True):
    context = self.thread
    if count and len(self.thread) == 1:
      context = await self.client.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':count})
    if 'order' in context:
      context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
    msgs, msgs_vision = [], []
    if self.bottom_instructions[0]['content']:
      tokens = count_tokens(self.top_instructions+self.bottom_instructions)
    else:
      tokens = count_tokens(self.top_instructions)
    for p_id in context['order']:
      post = context['posts'][p_id]
      if 'from_bot' in post['props']:
        role = 'assistant'
      else:
        role = 'user'
      msg, msg_vision = {'role':role, 'content':post['message']}, {'role':role, 'content':[{'type':'text','text':post['message']}]}
      msg_tokens = count_tokens(msg)
      if vision and 'file_ids' in post:
        for post_file_id in post['file_ids']:
          file_response = await self.client.files.get_file(file_id=post_file_id)
          if file_response.status_code != 200:
            print(f'Error downloading attachment: {file_response.status_code}')
            continue
          file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
          tmp_file_path = f'/tmp/{post_file_id}.{file_type}'
          async with aiofiles.open(tmp_file_path, 'wb') as tmp_file:
            await tmp_file.write(file_response.content)
          try:
            if file_type == 'pdf':
              pdf_pages = base64_images_from_pdf_file(tmp_file_path)
              remove(tmp_file_path)
              msg_vision['content'].extend([{'type':'image_url','image_url':{'url':f'data:image/png;base64,{pdf_page_image}','detail':'low'}} for pdf_page_image in pdf_pages])
              msg_tokens += 85
              self.model = environ.get('MODEL_VISION', 'gpt-4-vision-preview')
            else:
              image = base64_image_from_file(tmp_file_path)
              remove(tmp_file_path)
              msg_vision['content'].extend([{'type':'image_url','image_url':{'url':f'data:image/{file_type};base64,{image}','detail':'high'}}])
              msg_tokens += count_image_tokens(*Image.open(io.BytesIO(base64.b64decode(image))).size)
              self.model = environ.get('MODEL_VISION', 'gpt-4-vision-preview')
          except UnidentifiedImageError as err:
            print(f'Error processing attachment: {err}')
      new_tokens = tokens + msg_tokens
      if new_tokens > max_tokens:
        print(f'Token limit reached: {new_tokens} > {max_tokens}')
        break
      msgs.append(msg)
      msgs_vision.append(msg_vision)
      tokens = new_tokens
    msgs.reverse()
    msgs_vision.reverse()
    if self.model == environ.get('MODEL_VISION', 'gpt-4-vision-preview'):
      if self.bottom_instructions[0]['content']:
        return self.top_instructions + msgs_vision + self.bottom_instructions
      return self.top_instructions + msgs_vision
    if self.bottom_instructions[0]['content']:
      return self.top_instructions + msgs + self.bottom_instructions
    return self.top_instructions + msgs

  async def stream_reply(self, msgs:list) -> str:
    if self.post['root_id'] == '':
      reply_to = self.post['id']
    else:
      reply_to = self.post['root_id']
    reply_id = None
    buffer, chunks_processed = [], []
    start_time = time()
    async with Lock():
      async for chunk in chat_completion({'messages':msgs, 'model':self.model, 'max_tokens':4096}):
        if not chunk.content:
          continue
        buffer.append(chunk.content)
        if (time() - start_time) * 1000 >= 500:
          joined_chunks = ''.join(buffer)
          reply_id = await self.client.create_or_update_post({'channel_id':self.post['channel_id'], 'message':''.join(chunks_processed)+joined_chunks, 'file_ids':self.file_ids, 'root_id':reply_to}, reply_id)
          chunks_processed.append(joined_chunks)
          buffer.clear()
          start_time = time()
      if buffer:
        reply_id = await self.client.create_or_update_post({'channel_id':self.post['channel_id'], 'message':''.join(chunks_processed)+''.join(buffer), 'file_ids':self.file_ids, 'root_id':reply_to}, reply_id)
    return reply_id

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
            with io.BytesIO() as output:
              image.save(output, format="PNG")
              output.seek(0)
              uploaded_file_id = await self.client.upload_file(self.post['channel_id'], {'files':(f'/tmp/image_{total_images_saved}_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.png', output)})
            await self.client.create_or_update_post({'channel_id':self.post['channel_id'], 'file_ids':[uploaded_file_id], 'root_id':''})
            if total_images_saved >= payload['batch_size']:
              await websocket.close()
              return
