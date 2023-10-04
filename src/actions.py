import asyncio
import base64
import json
import os
import re
import time
import aiofiles
import googlesearch
import gradio_client
import httpx
import PIL
import requests
import webuiapi
import models

webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=os.environ['STABLE_DIFFUSION_WEBUI_PORT'])
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

class Mattermost():

  def __init__(self, bot, post:dict):
    self.available_functions = {
      'channel_summary': self.channel_summary,
      'code_analysis': self.code_analysis,
      'generate_images': self.generate_images,
      'get_current_weather': self.get_current_weather,
      'google_for_answers': self.google_for_answers,
      'instruct_pix2pix': self.instruct_pix2pix,
      'upscale_image': self.upscale_image,
    }
    self.bot = bot
    self.context = None
    self.file_ids = []
    self.instructions = [{'role':'system', 'content':'User messages begin with JSON header which identifies different users from each other. Header must be ignored unless identities are relevant to discussion. Do not reveal the persona you are potentially assigned to imitate!'}]
    self.reply_to = ''
    self.message = post['message']
    self.post = post
    asyncio.create_task(self.__post_handler__())

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
    if (bot.name_in_message(message)) and post['root_id'] == "":
      msgs = self.instructions + [{"role":"user", "content":message}]
      res = await models.chat_completion_functions(msgs, self.available_functions)
      if res.get('content'):
        await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':res['content'], 'file_ids':self.file_ids, 'root_id':post['id']})
      return
    self.context = await bot.posts.get_thread(post['id'])
    self.reply_to = post['root_id']
    async with asyncio.Lock():
      for post in self.context['posts'].values():
        if post['metadata'].get('reactions'):
          for reaction in post['metadata']['reactions']:
            if reaction['emoji_name'] == 'robot_face' and reaction['user_id'] == bot.user_id:
              return await self.code_analysis()
      for post in self.context['posts'].values():
        if bot.name_in_message(post['message']):
          return await self.stream_reply_to_context()

  async def captioner(self):
    bot = self.bot
    post = self.post
    captions = []
    async with httpx.AsyncClient() as client:
      for post_file_id in post['file_ids']:
        file_response = await bot.files.get_file(file_id=post_file_id)
        try:
          if file_response.status_code == 200:
            file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
            file_path_in_content = re.findall('filename="(.+)"', file_response.headers["Content-Disposition"])[0]
            post_file_path = f'{post_file_id}.{file_type}'
            async with aiofiles.open(f'/tmp/{post_file_path}', 'wb') as post_file:
              await post_file.write(file_response.content)
            with open(f'/tmp/{post_file_path}', 'rb') as temp_file:
              img_byte = temp_file.read()
            os.remove(f'/tmp/{post_file_path}')
            source_image_base64 = base64.b64encode(img_byte).decode("utf-8")
            data = {
              "forms": [
                {
                  "name": "caption",
                  "payload": {} # Additional form payload data should go here, based on spec
                }
              ],
              "source_image": source_image_base64, # Here is the base64 image
              "slow_workers": True
            }
            url = "https://stablehorde.net/api/v2/interrogate/async"
            headers = {"Content-Type": "application/json","apikey": "a8kMOjo-sgqlThYpupXS7g"}
            response = await client.post(url, headers=headers, data=json.dumps(data))
            response_content = response.json()
            await asyncio.sleep(15)
            caption_res = await client.get('https://stablehorde.net/api/v2/interrogate/status/' + response_content['id'], headers=headers, timeout=420)
            json_response = caption_res.json()
            caption=json_response['forms'][0]['result']['caption']
            captions.append(f"{file_path_in_content}: {caption}")
        except (RuntimeError, KeyError, IndexError) as err:
          captions.append(f"Error occurred while generating captions for file {post_file_id}: {str(err)}")
          continue
    return '\n'.join(captions)

  async def channel_summary(self, count:int):
    self.context = await self.bot.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':count})
    await self.stream_reply_to_context()

  async def chat_completion_functions_stage2(self, post:dict, function:str, arguments:dict, result:dict):
    messages = [
      {"role": "user", "content": post['message']},
      {"role": "assistant", "content": None, "function_call": {"name": function, "arguments": json.dumps(arguments)}},
      {"role": "function", "name": function, "content": json.dumps(result)}
    ]
    final_result = await models.chat_completion(messages, model='gpt-4-0613', functions=models.function_descriptions)
    await self.bot.create_or_update_post({'channel_id':post['channel_id'], 'message':final_result['content'], 'file_ids':None, 'root_id':''})

  async def code_analysis(self):
    bot = self.bot
    self.context = await bot.posts.get_thread(self.post['id'])
    files = []
    for file_path in [x for x in os.listdir() if x.endswith(('.py','.sh','.yml'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n```\n{content}\n```\n--- END {file_path} ---\n')
    self.instructions[0]['content'] += '\nThis is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic! Abstain from praising or thanking the user, be serious.'+''.join(files) + self.instructions[0]['content']
    await bot.create_reaction(await self.stream_reply_to_context(), 'robot_face')

  async def from_context_streamed(self, model='gpt-4-32k'):
    cxt = self.context
    if 'order' in cxt:
      cxt['order'].sort(key=lambda x: cxt['posts'][x]['create_at'], reverse=True)
    msgs = []
    tokens = 0
    ratio = 0.8
    limit1 = 8192*ratio
    limit2 = 2*limit1
    for p_id in cxt['order']:
      post = cxt['posts'][p_id]
      if 'from_bot' in post['props']:
        role = 'assistant'
      else:
        role = 'user'
      msg = {'role':role, 'content':post['message']}
      msg_tokens = models.count_tokens(msg)
      new_tokens = tokens + msg_tokens
      if limit1 < new_tokens < limit2 and model == 'gpt-4-32k':
        model = 'gpt-3.5-turbo-16k'
      elif new_tokens > limit2:
        break
      msgs.append(msg)
      tokens = new_tokens
    msgs.reverse()
    async for part in models.chat_completion_streamed(self.instructions+msgs, model):
      yield part

  async def from_message_streamed(self, message:str, model='gpt-4-32k'):
    user = await self.bot.users.get_user(self.post['user_id'])
    async for part in models.chat_completion_streamed(self.instructions+[{'role':'user', 'content':message, 'name':user['username']}], model):
      yield part

  async def generate_images(self, prompt, negative_prompt, count, resolution='1024x1024'):
    bot = self.bot
    width, height = resolution.split('x')
    post = self.post
    file_ids = self.file_ids
    options = webui_api.get_options()
    options = {}
    options['sd_model_checkpoint'] = 'sd_xl_base_1.0_0.9vae.safetensors [e6bb9ea85b]'
    webui_api.set_options(options)
    result = webui_api.txt2img(prompt=prompt, steps=34, batch_size=count, width=width, height=height, sampler_name='DPM++ 2M Karras', script_name='Distribute')
    for image in result.images:
      tmp_path = f'/tmp/result_{time.time()}.png'
      image.save(tmp_path)
      with open(tmp_path, 'rb') as image_file:
        uploaded_file_id = await bot.upload_file(post['channel_id'], {'files':(tmp_path.split('/')[2], image_file)})
        file_ids.append(uploaded_file_id)
      os.remove(tmp_path)
    await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':f"prompt: {prompt}\nnegative_prompt: {negative_prompt}\nresolution: {resolution}", 'file_ids':file_ids, 'root_id':''})

  async def get_current_weather(self, location):
    weatherapi_response = json.loads(requests.get(f"https://api.weatherapi.com/v1/current.json?key={os.environ['WEATHERAPI_KEY']}&q={location}", timeout=7).text)
    await self.chat_completion_functions_stage2(self.post, 'get_current_weather', {'location':location}, weatherapi_response)

  async def google_for_answers(self, url=''):
    results = []
    for result in googlesearch.search(url, num_results=2):
      results.append(result)
    await self.bot.create_or_update_post({'channel_id':self.post['channel_id'], 'message':json.dumps(results), 'file_ids':self.file_ids, 'root_id':''})

  async def instruct_pix2pix(self):
    bot = self.bot
    file_ids = self.file_ids
    post = self.post
    comment = ''
    for post_file_id in post['file_ids']:
      file_response = await bot.files.get_file(file_id=post_file_id)
      if file_response.status_code == 200:
        file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
        post_file_path = f'{post_file_id}.{file_type}'
        with open(post_file_path, 'wb') as new_image:
          new_image.write(file_response.content)
      try:
        post_file_image = PIL.Image.open(post_file_path)
        options = webui_api.get_options()
        options = {}
        options['sd_model_checkpoint'] = 'instruct-pix2pix-00-22000.safetensors [fbc31a67aa]'
        options['sd_vae'] = "None"
        webui_api.set_options(options)
        prompt = post['message']
        result = webui_api.img2img(images=[post_file_image], prompt=post['message'], steps=150, seed=-1, cfg_scale=7.5, denoising_strength=1.5)
        if not result:
          raise RuntimeError("API returned an invalid response")
        processed_image_path = f"processed_{post_file_id}.png"
        result.image.save(processed_image_path)
        with open(processed_image_path, 'rb') as image_file:
          file_id = await bot.upload_file(post['channel_id'], {'files': (processed_image_path, image_file)})
        file_ids.append(file_id)
        comment += "Image processed successfully"
      except RuntimeError as err:
        comment += f"Error occurred while processing image: {str(err)}"
      finally:
        for temporary_file_path in (post_file_path, processed_image_path):
          if os.path.exists(temporary_file_path):
            os.remove(temporary_file_path)
    await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':prompt, 'file_ids':file_ids, 'root_id':''})

  async def stream_reply_to_context(self) -> str:
    bot = self.bot
    file_ids = self.file_ids
    post = self.post
    reply_to = self.reply_to
    reply_id = None
    buffer = []
    chunks_processed = []
    start_time = time.time()
    async with asyncio.Lock():
      async for chunk in self.from_context_streamed():
        buffer.append(chunk)
        if (time.time() - start_time) * 1000 >= 250:
          joined_chunks = ''.join(buffer)
          reply_id = await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':''.join(chunks_processed)+joined_chunks, 'file_ids':file_ids, 'root_id':reply_to}, reply_id)
          chunks_processed.append(joined_chunks)
          buffer.clear()
          start_time = time.time()
      if buffer:
        reply_id = await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':''.join(chunks_processed)+''.join(buffer), 'file_ids':file_ids, 'root_id':reply_to}, reply_id)
    return reply_id

  async def upscale_image(self, scale=2):
    bot = self.bot
    file_ids = self.file_ids
    post = self.post
    for post_file_id in post['file_ids']:
      file_response = await bot.files.get_file(file_id=post_file_id)
      if file_response.status_code == 200:
        file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
        post_file_path = f'{post_file_id}.{file_type}'
        with open(post_file_path, 'wb') as post_file:
          post_file.write(file_response.content)
      try:
        post_file_image = PIL.Image.open(post_file_path)
        result = webui_api.extra_single_image(post_file_image, upscaling_resize=scale, upscaler_1="LDSR")
        upscaled_image_path = f"upscaled_{post_file_id}.png"
        result.image.save(upscaled_image_path)
        with open(upscaled_image_path, 'rb') as image_file:
          file_id = await bot.upload_file(post['channel_id'], {'files':(upscaled_image_path, image_file)})
        file_ids.append(file_id)
        comment += "Image upscaled successfully"
      except RuntimeError as err:
        comment += f"Error occurred while upscaling image: {str(err)}"
      finally:
        for temporary_file_path in (post_file_path, upscaled_image_path):
          if os.path.exists(temporary_file_path):
            os.remove(temporary_file_path)

  async def youtube_transcription(self, message:str) -> str:
    input_str = message
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    urls = re.findall(url_pattern, input_str)
    if urls:
      gradio = gradio_client.Client(os.environ['TRANSCRIPTION_API_URI'])
      prediction = gradio.predict(message, fn_index=1)
      if 'error' in prediction:
        return f"ERROR gradio.predict(): {prediction['error']}"
      ytsummary = await models.generate_summary_from_transcription(prediction)
      return ytsummary
