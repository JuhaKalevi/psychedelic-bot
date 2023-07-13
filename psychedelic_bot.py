import json
import os
import mattermostdriver
import basic
import multimedia
import mattermost_api
import textgen_api

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if not ('event' in event and event['event'] == 'posted' and event['data']['sender_name'] != basic.bot_name):
    return
  post = json.loads(event['data']['post'])
  message = post['message']
  if post['root_id']:
    reply_to = post['root_id']
  else:
    reply_to = post['id']
  always_reply = basic.should_always_reply(mattermost_api.channel_from_post(post, bot)['purpose'])
  if post['root_id'] == "" and (always_reply or basic.bot_name in message):
    magic_words_response = await respond_to_magic_words(post, file_ids)
    if magic_words_response:
      mattermost_api.create_post({'channel_id':post['channel_id'], 'message':magic_words_response, 'file_ids':file_ids, 'root_id':post['root_id']}, bot)
      return
    image_generation = await multimedia.consider_image_generation(bot, message, file_ids, post)
    if image_generation:
      mattermost_api.create_post({'channel_id':post['channel_id'], 'message':image_generation, 'file_ids':file_ids, 'root_id':reply_to}, bot)
      return
    summarize = await basic.is_asking_for_channel_summary(message)
    if summarize:
      context = mattermost_api.channel_context(post, bot)
    else:
      context = {'order':[post['id']], 'posts':{post['id']: post}}
    response = await basic.generate_text_from_context(context)
    mattermost_api.create_post({'channel_id':post['channel_id'], 'message':response, 'file_ids':file_ids, 'root_id':reply_to}, bot)
  else:
    context = mattermost_api.thread_context(post, bot)
    if any(basic.bot_name in post['message'] for post in context['posts'].values()):
      response = await basic.generate_text_from_context(context)
      mattermost_api.create_post({'channel_id':post['channel_id'], 'message':response, 'file_ids':file_ids, 'root_id':reply_to}, bot)

async def respond_to_magic_words(post, file_ids):
  word = post['message'].lower()
  if word.startswith("caption"):
    print("DEBUG: user msg startas with: caption! Got these file_ids:", file_ids, "and this post: ", post)
    response = await multimedia.captioner(bot, file_ids)
  elif word.startswith("pix2pix"):
    print("HAHAA! Gonna do pix2pix now! Got these file_ids:", file_ids, "and this post: ", post)
    response = await multimedia.instruct_pix2pix(bot, file_ids, post)
  elif word.startswith("2x"):
    response = await multimedia.upscale_image(bot, file_ids, post, 2)
  elif word.startswith("4x"):
    response = await multimedia.upscale_image(bot, file_ids, post, 4)
  elif word.startswith("llm"):
    response = await textgen_api.textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif word.startswith("storyteller"):
    response = await multimedia.storyteller(bot, file_ids)
  elif word.startswith("summary"):
    response = await multimedia.youtube_transcription(post['message'])
  else:
    return None
  return response

bot = mattermostdriver.Driver({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
bot.login()
bot.init_websocket(context_manager)
