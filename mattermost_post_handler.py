import asyncio
import os
import time
import webuiapi
import basic
import generate_text
import log
import mattermost_api
import multimedia
import openai_api
import textgen_api


bot = mattermost_api.bot
logger = log.get_logger(__name__)
webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=os.environ['STABLE_DIFFUSION_WEBUI_PORT'])
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

class MattermostPostHandler():

  def __init__(self, post):
    self.available_functions = {
      'generate_images': self.generate_images
    }
    self.context = None
    self.reply_to = None
    self.post = post
    self.message = post['message']
    self.file_ids = []
    self.lock = asyncio.Lock()

  async def generate_images(self, count):
    logger.debug(count)
    post = self.post
    file_ids = self.file_ids
    prompt = post['message'].removeprefix(bot.name)
    mainly_english = await basic.is_mainly_english(prompt.encode('utf-8'))
    if not mainly_english:
      prompt = await generate_text.fix_image_generation_prompt(prompt)
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
    return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':prompt, 'file_ids':file_ids, 'root_id':''})

  async def post_handler(self):
    post = self.post
    message = self.message
    file_ids = self.file_ids
    channel = await bot.channels.get_channel(post['channel_id'])
    magic_words_response = await self.respond_to_magic_words()
    if magic_words_response is not None:
      return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':magic_words_response, 'file_ids':file_ids, 'root_id':post['root_id']})
    if post['root_id'] == "" and (f"{bot.name} always reply" in channel['purpose'] or bot.name_in_message(message)):
      function_choice = await openai_api.chat_completion_functions(message, self.available_functions)
      logger.debug(function_choice)
      if await generate_text.is_asking_for_channel_summary(post):
        self.context = await bot.posts.get_posts_for_channel(post['channel_id'], params={'per_page':143})
        return await self.stream_reply_to_context()
      self.context = {'order':[post['id']], 'posts':{post['id']: post}}
      self.reply_to = post['id']
      return await self.stream_reply_to_context()
    self.context = await bot.posts.get_thread(post['id'])
    self.reply_to = post['root_id']
    for thread_post in self.context['posts'].values():
      if bot.name_in_message(thread_post['message']):
        return await self.stream_reply_to_context()

  async def respond_to_magic_words(self):
    post = self.post
    message = self.message.lower()
    file_ids = self.file_ids
    if message.startswith("caption"):
      return await multimedia.captioner(post)
    if message.startswith("pix2pix"):
      return await multimedia.instruct_pix2pix(file_ids, message)
    if message.startswith("2x"):
      return await multimedia.upscale_image(file_ids, message, 2)
    if message.startswith("4x"):
      return await multimedia.upscale_image(file_ids, message, 4)
    if message.startswith("llm"):
      return await textgen_api.textgen_chat_completion(message, {'internal': [], 'visible': []})
    if message.startswith("storyteller"):
      captions = await multimedia.captioner(post)
      return await basic.generate_story_from_captions(captions)
    if message.startswith("summary"):
      return await multimedia.youtube_transcription(message)

  async def stream_reply_to_context(self, reply_to=''):
    lock = self.lock
    post = self.post
    file_ids = self.file_ids
    reply_id = None
    buffer = []
    chunks_processed = []
    start_time = time.time()
    async for chunk in generate_text.from_context_streamed(self.context):
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
