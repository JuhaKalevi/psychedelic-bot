import asyncio
import json
import os
import mattermostdriver
import generate_text
import multimedia
import mattermost_api
import textgen_api

bot = mattermostdriver.AsyncDriver({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
bot_name = os.environ['MATTERMOST_BOT_NAME']

def bot_name_in_message(message):
  return bot_name in message or bot_name == '@bot' and '@chatgpt' in message

async def context_manager(event):
  print('new event')
  event = json.loads(event)
  if not ('event' in event and event['event'] == 'posted' and event['data']['sender_name'] != bot_name):
    return
  post = json.loads(event['data']['post'])
  if 'from_bot' in post['props']:
    return
  if post['root_id']:
    reply_to = post['root_id']
  else:
    reply_to = post['id']
  channel_from_post = await bot.channels.get_channel(post['channel_id'])
  always_reply = f"{bot_name} always reply" in channel_from_post['purpose']
  file_ids = []
  message = post['message']
  if post['root_id'] == "" and (always_reply or bot_name_in_message(message)):
    magic_words_response = await respond_to_magic_words(post, file_ids)
    if magic_words_response is not None:
      await mattermost_api.create_or_update_post(bot, {'channel_id':post['channel_id'], 'message':magic_words_response, 'file_ids':file_ids, 'root_id':post['root_id']})
      return
    image_generation_response = await multimedia.consider_image_generation(bot, message, file_ids, post)
    if image_generation_response is not None:
      return await mattermost_api.create_or_update_post(bot, {'channel_id':post['channel_id'], 'message':image_generation_response, 'file_ids':file_ids, 'root_id':reply_to})
    if await generate_text.is_asking_for_channel_summary(message):
      context = await bot.posts.get_posts_for_channel(post['channel_id'])
    else:
      context = {'order':[post['id']], 'posts':{post['id']: post}}
    reply_id = None
    stream_chunks = []
    async for chunk in generate_text.from_context(context):
      stream_chunks.append(chunk)
      reply_id = await mattermost_api.create_or_update_post(bot, reply_id, {'channel_id':post['channel_id'], 'message':''.join(stream_chunks), 'file_ids':file_ids, 'root_id':reply_to})
  else:
    context = await bot.posts.get_thread(post['id'])
    for post in context['posts'].values():
      if bot_name_in_message(post['message']):
        reply_id = None
        stream_chunks = []
        async for chunk in generate_text.from_context(context):
          stream_chunks.append(chunk)
          reply_id = await mattermost_api.create_or_update_post(bot, reply_id, {'channel_id':post['channel_id'], 'message':''.join(stream_chunks), 'file_ids':file_ids, 'root_id':reply_to})

async def respond_to_magic_words(post, file_ids):
  word = post['message'].lower()
  if word.startswith("caption"):
    response = await multimedia.captioner(post, bot)
  elif word.startswith("pix2pix"):
    response = await multimedia.instruct_pix2pix(bot, file_ids, post)
  elif word.startswith("2x"):
    response = await multimedia.upscale_image(bot, file_ids, post, 2)
  elif word.startswith("4x"):
    response = await multimedia.upscale_image(bot, file_ids, post, 4)
  elif word.startswith("llm"):
    response = await textgen_api.textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif word.startswith("storyteller"):
    response = await multimedia.storyteller(post, bot)
  elif word.startswith("summary"):
    response = await multimedia.youtube_transcription(post['message'])
  else:
    return None
  return response

async def main():
  await bot.login()
  await bot.init_websocket(context_manager)

asyncio.run(main())
