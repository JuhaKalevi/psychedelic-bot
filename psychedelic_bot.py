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
  return_signal = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != basic.bot_name:
    post = json.loads(event['data']['post'])
    return_signal = await respond_to_magic_words(post, file_ids)
    if return_signal:
      mattermost_api.create_post({'channel_id':post['channel_id'], 'message':return_signal, 'file_ids':file_ids, 'root_id':post['root_id']}, bot)
    else:
      message = post['message']
      channel = mattermost_api.channel_from_post(post, bot)
      always_reply = basic.should_always_reply(channel['purpose'])
      if post['root_id']:
        reply_to = post['root_id']
      else:
        reply_to = post['id']
      if always_reply or basic.bot_name in message:
        return_signal = await multimedia.consider_image_generation(bot, message, file_ids, post)
        if not return_signal:
          summarize = await basic.is_asking_for_channel_summary(message)
          if summarize:
            context = mattermost_api.channel_context(post, bot)
          else:
            context = mattermost_api.thread_context(post, bot)
          return_signal = await basic.generate_text_from_context(context, channel)
          mattermost_api.create_post({'channel_id':post['channel_id'], 'message':return_signal, 'file_ids':file_ids, 'root_id':reply_to}, bot)
        context = await basic.generate_text_from_message(message)
      else:
        reply_to = post['root_id']
        context = mattermost_api.thread_context(post, bot)
        if any(basic.bot_name in context_post['message'] for context_post in context['posts'].values()):
          return_signal = await basic.generate_text_from_context(context, channel)
        if return_signal:
          mattermost_api.create_post({'channel_id':post['channel_id'], 'message':return_signal, 'file_ids':file_ids, 'root_id':reply_to}, bot)

async def respond_to_magic_words(post, file_ids):
  word = post['message'].lower()
  if word.startswith("caption"):
    response = await multimedia.captioner(bot, file_ids)
  elif word.startswith("pix2pix"):
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
