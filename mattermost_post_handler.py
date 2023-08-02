import asyncio
import os
import time
import webuiapi
import basic
import log
import mattermost_api
import openai_api

bot = mattermost_api.bot
logger = log.get_logger(__name__)
webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=os.environ['STABLE_DIFFUSION_WEBUI_PORT'])
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

class MattermostPostHandler():

  def __init__(self, post):
    self.available_functions = {
      'channel_summary': self.channel_summary,
      'code_analysis': self.code_analysis,
      'generate_images': self.generate_images,
    }
    self.context = None
    self.reply_to = None
    self.post = post
    self.message = post['message']
    self.file_ids = []
    self.lock = asyncio.Lock()

  async def channel_summary(self, count):
    self.context = await bot.posts.get_posts_for_channel(self.post['channel_id'], params={'per_page':count})
    return await self.stream_reply_to_context()

  async def code_analysis(self):
    files = []
    for file_path in [x for x in os.listdir() if x.endswith(('.py','.sh','.yml'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'\n--- BEGIN {file_path} ---\n{content}\n--- END {file_path} ---\n')
    self.message += '\nThis is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(files)
    return await self.stream_reply_to_context()

  async def fix_image_generation_prompt(self, message):
    return await self.from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {message}")

  async def from_context_streamed(self, context, model='gpt-4'):
    if 'order' in context:
      context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
    context_messages = []
    context_tokens = 0
    context_token_limit = 7372
    for post_id in context['order']:
      if 'from_bot' in context['posts'][post_id]['props']:
        role = 'assistant'
      else:
        role = 'user'
      message = {'role':role, 'content':context['posts'][post_id]['message']}
      message_tokens = openai_api.count_tokens(message)
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

  async def from_message(self, message, model='gpt-4'):
    return await openai_api.chat_completion([{'role':'user', 'content':message}], model)

  async def from_message_streamed(self, message, model='gpt-4'):
    async for content in openai_api.chat_completion_streamed([{'role':'user', 'content':message}], model):
      yield content

  async def generate_images(self, count=0):
    post = self.post
    file_ids = self.file_ids
    prompt = post['message'].removeprefix(bot.name)
    mainly_english = await basic.is_mainly_english(prompt.encode('utf-8'))
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
        uploaded_file_id = await bot.upload_mattermost_file(post['channel_id'], {'files':('result.png', image_file)})
        file_ids.append(uploaded_file_id)
    await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':prompt, 'file_ids':file_ids, 'root_id':''})
    return True

  async def post_handler(self):
    post = self.post
    self.context = await bot.posts.get_thread(post['id'])
    message = self.message
    channel = await bot.channels.get_channel(post['channel_id'])
    if post['root_id'] == "" and (f"{bot.name} always reply" in channel['purpose'] or bot.name_in_message(message)):
      function_processed = await openai_api.chat_completion_functions(message, self.available_functions)
      if not function_processed:
        self.context = {'order':[post['id']], 'posts':{post['id']: post}}
        self.reply_to = post['id']
        return await self.stream_reply_to_context()
    self.reply_to = post['root_id']
    for thread_post in self.context['posts'].values():
      if bot.name_in_message(thread_post['message']):
        return await self.stream_reply_to_context()

  async def stream_reply_to_context(self, reply_to=''):
    lock = self.lock
    post = self.post
    file_ids = self.file_ids
    reply_id = None
    buffer = []
    chunks_processed = []
    start_time = time.time()
    async for chunk in self.from_context_streamed(self.context):
      buffer.append(chunk)
      if (time.time() - start_time) * 1000 >= 250:
        joined_chunks = ''.join(buffer)
        async with lock:
          reply_id = await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':''.join(chunks_processed)+joined_chunks, 'file_ids':file_ids, 'root_id':reply_to}, reply_id)
        chunks_processed.append(joined_chunks)
        buffer.clear()
        start_time = time.time()
    if buffer:
      async with lock:
        reply_id = await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':''.join(chunks_processed)+''.join(buffer), 'file_ids':file_ids, 'root_id':reply_to}, reply_id)
    return reply_id
