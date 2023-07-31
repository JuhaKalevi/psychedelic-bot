import asyncio
import json
import time
import basic
import generate_text
import log
import multimedia
import mattermost_api
import openai_api
import textgen_api

bot = mattermost_api.bot
logger = log.get_logger(__name__)
tasks = []

available_functions = {
  'generate_images': multimedia.generate_images
}

async def context_manager(event):
  event = json.loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != bot.name:
    post = json.loads(event['data']['post'])
    if 'from_bot' not in post['props']:
      asyncio.create_task(delegated_post_handler(post))

async def delegated_post_handler(post, lock=asyncio.Lock()):
  channel = await bot.channels.get_channel(post['channel_id'])
  message = post['message']
  file_ids = []
  magic_words_response = await respond_to_magic_words(post, file_ids)
  if magic_words_response is not None:
    return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':magic_words_response, 'file_ids':file_ids, 'root_id':post['root_id']})
  if post['root_id'] == "" and (f"{bot.name} always reply" in channel['purpose'] or bot.name_in_message(message)):
    function_choice = await openai_api.chat_completion_functions(message, available_functions)
    logger.debug(function_choice)
    if f"{bot.name} always generate image" in channel['purpose'] or await generate_text.is_asking_for_image_generation(message):
      if f"{bot.name} always generate images" in channel['purpose'] or await generate_text.is_asking_for_multiple_images(message):
        image_generation_comment = await multimedia.generate_images(file_ids, post, 8)
      else:
        image_generation_comment = await multimedia.generate_images(file_ids, post, 1)
      return await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':image_generation_comment, 'file_ids':file_ids, 'root_id':''})
    if await generate_text.is_asking_for_channel_summary(post):
      context = await bot.posts.get_posts_for_channel(post['channel_id'], params={'per_page':143})
      return await stream_reply_to_context(lock, context, post, file_ids)
    context = {'order':[post['id']], 'posts':{post['id']: post}}
    return await stream_reply_to_context(lock, context, post, file_ids, post['id'])
  context = await bot.posts.get_thread(post['id'])
  for thread_post in context['posts'].values():
    if bot.name_in_message(thread_post['message']):
      return await stream_reply_to_context(lock, context, post, file_ids, post['root_id'])

async def respond_to_magic_words(post, file_ids):
  message = post['message'].lower()
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
    captions = await multimedia.captioner(message)
    return await basic.generate_story_from_captions(captions)
  if message.startswith("summary"):
    return await multimedia.youtube_transcription(message)

async def stream_reply_to_context(lock, context, post, file_ids, reply_to=''):
  reply_id = None
  buffer = []
  chunks_processed = []
  start_time = time.time()
  async for chunk in generate_text.from_context_streamed(context):
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

async def main():
  await bot.login()
  await bot.init_websocket(context_manager)

asyncio.run(main())
