import asyncio
import json
import os
import mattermostdriver
import basic
import generate_text
import multimedia
import mattermost_api
import textgen_api

bot = mattermostdriver.AsyncDriver({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
bot_name = os.environ['MATTERMOST_BOT_NAME']
tasks = []

def bot_name_in_message(message):
  return bot_name in message or bot_name == '@bot' and '@chatgpt' in message

async def context_manager(event):
  event = json.loads(event)
  lock = asyncio.Lock()
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != bot_name:
    post = json.loads(event['data']['post'])
    if 'from_bot' not in post['props']:
      asyncio.create_task(delegated_post_handler(lock, post))

async def delegated_post_handler(lock, post):
  if post['root_id']:
    reply_to = post['root_id']
  else:
    reply_to = post['id']
  channel = await bot.channels.get_channel(post['channel_id'])
  file_ids = []
  message = post['message']
  if post['root_id'] == "" and (f"{bot_name} always reply" in channel['purpose'] or bot_name_in_message(message)):
    magic_words_response = await respond_to_magic_words(post, file_ids)
    if magic_words_response is not None:
      return await mattermost_api.create_or_update_post(bot, {'channel_id':post['channel_id'], 'message':magic_words_response, 'file_ids':file_ids, 'root_id':''})
    if f"{bot_name} always generate image" in channel['purpose'] or await generate_text.is_asking_for_image_generation(message):
      if f"{bot_name} always generate images" in channel['purpose'] or await generate_text.is_asking_for_multiple_images(message):
        image_generation_comment = await multimedia.generate_images(bot, file_ids, post, 8)
      else:
        image_generation_comment = await multimedia.generate_images(bot, file_ids, post, 1)
    else:
      image_generation_comment = None
    if image_generation_comment:
      return await mattermost_api.create_or_update_post(bot, {'channel_id':post['channel_id'], 'message':image_generation_comment, 'file_ids':file_ids, 'root_id':reply_to})
    if await generate_text.is_asking_for_channel_summary(post):
      context = await bot.posts.get_posts_for_channel(post['channel_id'])
    else:
      context = {'order':[post['id']], 'posts':{post['id']: post}}
    return await stream_reply_to_context(lock, context, post, file_ids, reply_to)
  context = await bot.posts.get_thread(post['id'])
  for thread_post in context['posts'].values():
    if bot_name_in_message(thread_post['message']):
      return await stream_reply_to_context(lock, context, post, file_ids, reply_to)

async def respond_to_magic_words(post, file_ids):
  post = post['message'].lower()
  if post.startswith("caption"):
    return await multimedia.captioner(bot, post)
  if post.startswith("pix2pix"):
    return await multimedia.instruct_pix2pix(bot, file_ids, post)
  if post.startswith("2x"):
    return await multimedia.upscale_image(bot, file_ids, post, 2)
  if post.startswith("4x"):
    return await multimedia.upscale_image(bot, file_ids, post, 4)
  if post.startswith("llm"):
    return await textgen_api.textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  if post.startswith("storyteller"):
    captions = await multimedia.captioner(bot, post)
    return await basic.generate_story_from_captions(captions)
  if post.startswith("summary"):
    return await multimedia.youtube_transcription(post['message'])

async def stream_reply_to_context(lock, context, post, file_ids, reply_to):
  reply_id = None
  stream_chunks = []
  async with lock:
    async for chunk in generate_text.from_context_streamed(context):
      stream_chunks.append(chunk)
      reply_id = await mattermost_api.create_or_update_post(bot, {'channel_id':post['channel_id'], 'message':''.join(stream_chunks), 'file_ids':file_ids, 'root_id':reply_to}, reply_id)
  return reply_id

async def main():
  await bot.login()
  await bot.init_websocket(context_manager)

asyncio.run(main())
