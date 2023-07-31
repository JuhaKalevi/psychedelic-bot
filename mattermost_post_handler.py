import asyncio
import time
import basic
import generate_text
import log
import mattermost_api
import multimedia
import openai_api
import textgen_api

bot = mattermost_api.bot
logger = log.get_logger(__name__)

class MattermostPostHandler():

  def __init__(self, post, available_functions):
    self.context = None
    self.reply_to = None
    self.post = post
    self.message = post['message']
    self.file_ids = []
    self.available_functions = available_functions
    self.lock = asyncio.Lock()

  async def delegated_post_handler(self):
    post = self.post
    message = self.message
    file_ids = self.file_ids
    channel = await bot.channels.get_channel(post['channel_id'])
    magic_words_response = await self.respond_to_magic_words()
    if magic_words_response is not None:
      return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':magic_words_response, 'file_ids':file_ids, 'root_id':post['root_id']})
    if post['root_id'] == "" and (f"{bot.name} always reply" in channel['purpose'] or bot.name_in_message(self.message)):
      function_choice = await openai_api.chat_completion_functions(self.message, self.available_functions)
      logger.debug(function_choice)
      if f"{bot.name} always generate image" in channel['purpose'] or await generate_text.is_asking_for_image_generation(message):
        if f"{bot.name} always generate images" in channel['purpose'] or await generate_text.is_asking_for_multiple_images(message):
          image_generation_comment = await multimedia.generate_images(file_ids, post, 8)
        else:
          image_generation_comment = await multimedia.generate_images(file_ids, post, 1)
        return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':image_generation_comment, 'file_ids':file_ids, 'root_id':''})
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
