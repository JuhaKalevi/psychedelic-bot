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

  async def __init__(self, post, available_functions):
    self.post = post
    self.channel = await bot.channels.get_channel(post['channel_id'])
    self.message = post['message']
    self.file_ids = []
    self.available_functions = available_functions
    self.lock = asyncio.Lock()

  async def delegated_post_handler(self, post):
    magic_words_response = await self.respond_to_magic_words()
    if magic_words_response is not None:
      return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':magic_words_response, 'file_ids':self.file_ids, 'root_id':post['root_id']})
    if post['root_id'] == "" and (f"{bot.name} always reply" in self.channel['purpose'] or bot.name_in_message(self.message)):
      function_choice = await openai_api.chat_completion_functions(self.message, self.available_functions)
      logger.debug(function_choice)
      if f"{bot.name} always generate image" in self.channel['purpose'] or await generate_text.is_asking_for_image_generation(self.message):
        if f"{bot.name} always generate images" in self.channel['purpose'] or await generate_text.is_asking_for_multiple_images(self.message):
          image_generation_comment = await multimedia.generate_images(self.file_ids, post, 8)
        else:
          image_generation_comment = await multimedia.generate_images(self.file_ids, post, 1)
        return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':image_generation_comment, 'file_ids':self.file_ids, 'root_id':''})
      if await generate_text.is_asking_for_channel_summary(post):
        context = await bot.posts.get_posts_for_channel(post['channel_id'], params={'per_page':143})
        return await self.stream_reply_to_context(context, post)
      context = {'order':[post['id']], 'posts':{post['id']: post}}
      return await self.stream_reply_to_context(context, post, post['id'])
    context = await bot.posts.get_thread(post['id'])
    for thread_post in context['posts'].values():
      if bot.name_in_message(thread_post['message']):
        return await self.stream_reply_to_context(context, post, post['root_id'])

  async def respond_to_magic_words(self):
    lowercase_message = self.message.lower()
    if lowercase_message.startswith("caption"):
      return await multimedia.captioner(self.post)
    if lowercase_message.startswith("pix2pix"):
      return await multimedia.instruct_pix2pix(self.file_ids, lowercase_message)
    if lowercase_message.startswith("2x"):
      return await multimedia.upscale_image(self.file_ids, lowercase_message, 2)
    if lowercase_message.startswith("4x"):
      return await multimedia.upscale_image(self.file_ids, lowercase_message, 4)
    if lowercase_message.startswith("llm"):
      return await textgen_api.textgen_chat_completion(lowercase_message, {'internal': [], 'visible': []})
    if lowercase_message.startswith("storyteller"):
      captions = await multimedia.captioner(lowercase_message)
      return await basic.generate_story_from_captions(captions)
    if lowercase_message.startswith("summary"):
      return await multimedia.youtube_transcription(lowercase_message)

  async def stream_reply_to_context(self, context, post, reply_to=''):
    reply_id = None
    buffer = []
    chunks_processed = []
    start_time = time.time()
    async for chunk in generate_text.from_context_streamed(context):
      buffer.append(chunk)
      if (time.time() - start_time) * 1000 >= 250:
        joined_chunks = ''.join(buffer)
        async with self.lock:
          reply_id = await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':''.join(chunks_processed)+joined_chunks, 'file_ids':self.file_ids, 'root_id':reply_to}, reply_id)
        chunks_processed.append(joined_chunks)
        buffer.clear()
        start_time = time.time()
    if buffer:
      async with self.lock:
        reply_id = await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':''.join(chunks_processed)+''.join(buffer), 'file_ids':self.file_ids, 'root_id':reply_to}, reply_id)
    return reply_id
