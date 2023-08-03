import asyncio
import base64
import json
import os
import re
import time
import aiofiles
import httpx
import PIL
import webuiapi
import common
import log
import mattermost_api
import openai_api

bot = mattermost_api.bot
logger = log.get_logger(__name__)
webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=os.environ['STABLE_DIFFUSION_WEBUI_PORT'])
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

class MattermostPostHandler():

  def __init__(self, post:dict):
    self.available_functions = {
      'channel_summary': self.channel_summary,
      'code_analysis': self.code_analysis,
      'generate_images': self.generate_images,
    }
    self.context = None
    self.file_ids = []
    self.reply_to = ''
    self.message = post['message']
    self.post = post
    self.system_message = None

  async def captioner(self):
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

  async def channel_summary(self, count:int) -> None:
    self.context = await bot.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':count})
    await self.stream_reply_to_context()

  async def code_analysis(self) -> None:
    self.context = await bot.posts.get_thread(self.post['id'])
    files = []
    for file_path in [x for x in os.listdir() if x.endswith(('.py','.sh','.yml'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n```\n{content}\n```\n--- END {file_path} ---\n')
    self.system_message = 'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic! Abstain from praising or thanking the user, be serious.'+''.join(files)
    reply_id = await self.stream_reply_to_context()
    await bot.create_reaction(reply_id, 'robot_face')

  async def fix_image_generation_prompt(self, message:str) -> str:
    return await openai_api.chat_completion([
      {'role':'system', 'content':
        "Convert user image prompt to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features."
        " Don't use full sentences, just a few keywords, separating these aspects by commas, or periods which separate bigger units consisting of multiple comma separated keywords together."
        " Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally."
        " Don't use any kind of formatting to separate these keywords, expect commas and periods!"
      },
      {'role':'user', 'content':message}
    ])

  async def from_context_streamed(self, model='gpt-4'):
    context = self.context
    if 'order' in context:
      context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
    if self.system_message:
      context_messages = [{'role':'system', 'content':self.system_message}]
      context_tokens = common.count_tokens(self.system_message)
    else:
      context_messages = []
      context_tokens = 0
    context_token_limit = 7372
    for post_id in context['order']:
      if 'from_bot' in context['posts'][post_id]['props']:
        role = 'assistant'
      else:
        role = 'user'
      message = {'role':role, 'content':context['posts'][post_id]['message']}
      message_tokens = common.count_tokens(message)
      new_context_tokens = context_tokens + message_tokens
      if context_token_limit < new_context_tokens < 14744:
        model = 'gpt-3.5-turbo-16k'
        context_token_limit *= 2
      elif new_context_tokens > 14744:
        break
      context_messages.append(message)
      context_tokens = new_context_tokens
    context_messages.reverse()
    logger.debug('token_count: %s', context_tokens)
    async for content in openai_api.chat_completion_streamed(context_messages, model):
      yield content

  async def from_message_streamed(self, message:str, model='gpt-4'):
    async for content in openai_api.chat_completion_streamed([{'role':'user', 'content':message}], model):
      yield content

  async def generate_images(self, count=0):
    post = self.post
    file_ids = self.file_ids
    prompt = post['message'].removeprefix(bot.name)
    mainly_english = await common.is_mainly_english(prompt.encode('utf-8'))
    if not mainly_english:
      prompt = await self.fix_image_generation_prompt(prompt)
    options = webui_api.get_options()
    options = {}
    options['sd_model_checkpoint'] = 'realisticVisionV40_v4 0VAE.safetensors [e9d3cedc4b]'
    options['sd_vae'] = 'vae-ft-mse-840000-ema-pruned.safetensors'
    webui_api.set_options(options)
    result = webui_api.txt2img(prompt=prompt, negative_prompt="(unfinished:1.43),(sloppy and messy:1.43),(incoherent:1.43),(deformed:1.43)", steps=42, sampler_name='UniPC', batch_size=count, restore_faces=True)
    for image in result.images:
      image.save('/tmp/result.png')
      with open('/tmp/result.png', 'rb') as image_file:
        uploaded_file_id = await bot.upload_file(post['channel_id'], {'files':('result.png', image_file)})
        file_ids.append(uploaded_file_id)
    await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':prompt, 'file_ids':file_ids, 'root_id':''})

  async def instruct_pix2pix(self) -> str:
    file_ids = self.file_ids
    post = self.post
    print(f"DEBUG: Starting function with bot={bot}, file_ids={file_ids}, post={post}")
    comment = ''
    for post_file_id in post['file_ids']:
      print(f"DEBUG: Processing file_id={post_file_id}")
      file_response = await bot.files.get_file(file_id=post_file_id)
      if file_response.status_code == 200:
        file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
        post_file_path = f'{post_file_id}.{file_type}'
        print(f"DEBUG: post_file_path={post_file_path}, file_type={file_type}")
        with open(post_file_path, 'wb') as new_image:
          new_image.write(file_response.content)
      try:
        post_file_image = PIL.Image.open(post_file_path)
        options = webui_api.get_options()
        print(f"DEBUG: Current options={options}")
        options = {}
        options['sd_model_checkpoint'] = 'instruct-pix2pix-00-22000.safetensors [fbc31a67aa]'
        options['sd_vae'] = "None"
        print(f"DEBUG: Set new options={options}")
        webui_api.set_options(options)
        prompt = post['message']
        print(f"DEBUG: Prompt for img2img={prompt}")
        result = webui_api.img2img(images=[post_file_image], prompt=post['message'], steps=150, seed=-1, cfg_scale=7.5, denoising_strength=1.5)
        print(f"DEBUG: img2img result={result}")
        if not result:
          raise RuntimeError("API returned an invalid response")
        processed_image_path = f"processed_{post_file_id}.png"
        result.image.save(processed_image_path)
        print(f"DEBUG: Saved result to path={processed_image_path}")
        with open(processed_image_path, 'rb') as image_file:
          file_id = await bot.upload_file(post['channel_id'], {'files': (processed_image_path, image_file)})
        print(f"DEBUG: Uploaded file, got file_id={file_id}")
        file_ids.append(file_id)
        comment += "Image processed successfully"
        print(f"DEBUG: Success, comment={comment}")
      except RuntimeError as err:
        comment += f"Error occurred while processing image: {str(err)}"
      finally:
        for temporary_file_path in (post_file_path, processed_image_path):
          if os.path.exists(temporary_file_path):
            os.remove(temporary_file_path)
    return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':prompt, 'file_ids':file_ids, 'root_id':''})

  async def post_handler(self):
    message = self.message
    post = self.post
    channel = await bot.channels.get_channel(post['channel_id'])
    bot_user = await bot.users.get_user_by_username(bot.name.strip('@'))
    bot.user_id = bot_user['id']
    if (f"{bot.name} always reply" in channel['purpose'] or bot.name_in_message(message)):
      if post['root_id'] == "":
        openai_response_message = await openai_api.chat_completion_functions(message, self.available_functions)
        if not openai_response_message.get('function_call'):
          self.context = {'order':[post['id']], 'posts':{post['id']: post}}
          self.reply_to = post['id']
          return await self.stream_reply_to_context()
    self.context = await bot.posts.get_thread(post['id'])
    self.reply_to = post['root_id']
    async with asyncio.Lock():
      for thread_post in self.context['posts'].values():
        if thread_post['metadata'].get('reactions'):
          for reaction in thread_post['metadata']['reactions']:
            logger.debug("DEBUG: reaction=%s", reaction)
            if reaction['emoji_name'] == 'robot_face' and reaction['user_id'] == bot.user_id:
              return await self.code_analysis()
      for thread_post in self.context['posts'].values():
        if bot.name_in_message(thread_post['message']):
          return await self.stream_reply_to_context()

  async def stream_reply_to_context(self) -> str:
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

  async def upscale_image(self, scale:int) -> str:
    file_ids = self.file_ids
    post = self.post
    if scale == 2:
      upscale_width = 1024
      upscale_height = 1024
    elif scale == 4:
      upscale_width = 2048
      upscale_height = 2048
    else:
      return "Invalid upscale scale"
    comment = ''
    for post_file_id in post['file_ids']:
      file_response = await bot.files.get_file(file_id=post_file_id)
      if file_response.status_code == 200:
        file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
        post_file_path = f'{post_file_id}.{file_type}'
        with open(post_file_path, 'wb') as post_file:
          post_file.write(file_response.content)
      try:
        post_file_image = PIL.Image.open(post_file_path)
        result = webui_api.extra_single_image(post_file_image, upscaling_resize=scale, upscaling_resize_w=upscale_width, upscaling_resize_h=upscale_height, upscaler_1="LDSR")
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
    return comment
