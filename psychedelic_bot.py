from json import dumps, loads
from os import environ, path, remove
import re
import openai
from mattermostdriver import Driver
from webuiapi import WebUIApi
import PIL
from basic_parsing import bot_name,count_tokens,choose_system_message,fix_image_generation_prompt,generate_story_from_captions,generate_text_from_message,is_asking_for_channel_summary,is_asking_for_image_generation,is_asking_for_multiple_images,is_mainly_english,should_always_reply_on_channel
from mattermost_api import channel_context,channel_from_post,create_post,get_mattermost_file,thread_context,upload_mattermost_file
from openai_api import generate_summary_from_transcription,openai_chat_completion
from textgen_api import textgen_chat_completion

bot_name = environ['MATTERMOST_BOT_NAME']

bot = Driver({'url':environ['MATTERMOST_URL'], 'token':environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
bot.login()
openai.api_key = environ['OPENAI_API_KEY']
webui_api = WebUIApi(host=environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

async def context_manager(event):
  file_ids = []
  event = loads(event)
  signal = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != bot_name:
    post = loads(event['data']['post'])
    signal = await respond_to_magic_words(post, file_ids)
    if signal:
      create_post({'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':post['root_id']}, bot)
    else:
      print('no magic words')
      message = post['message']
      channel = channel_from_post(post, bot)
      always_reply = should_always_reply_on_channel(channel['purpose'])
      if always_reply:
        print('always_reply')
        reply_to = post['root_id']
        signal = await consider_image_generation(message, file_ids, post)
        if not signal:
          summarize = await is_asking_for_channel_summary(post, channel)
          if summarize:
            print('summarize')
            context = channel_context(post, bot)
          else:
            context = thread_context(post, bot)
          signal = await generate_text_from_context(context, channel)
      elif bot_name in message:
        print('bot_name in message')
        reply_to = post['root_id']
        context = await generate_text_from_message(message)
      else:
        reply_to = post['root_id']
        context = thread_context(post, bot)
        if any(bot_name in context_post['message'] for context_post in context['posts'].values()):
          signal = await generate_text_from_context(context, channel)
      if signal:
        create_post({'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':reply_to}, bot)

async def generate_text_from_context(context, channel, model='gpt-4'):
  print(f"{channel['display_name']}: generate_text_from_context")
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await choose_system_message(context['posts'][context['order'][0]], channel)
  context_messages = []
  context_tokens = await count_tokens(context)
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    message = {'role': role, 'content': context['posts'][post_id]['message']}
    message_tokens = await count_tokens(message)
    if context_tokens + message_tokens < 7777:
      context_messages.append(message)
      context_tokens += message_tokens
    else:
      break
  context_messages.reverse()
  openai_response = await openai_chat_completion(system_message + context_messages, model)
  return openai_response

async def captioner(file_ids:list) -> str:
  from base64 import b64encode
  from asyncio import sleep
  import aiofiles
  captions = []
  from httpx import AsyncClient
  async with AsyncClient() as client:
    for post_file_id in file_ids:
      file_response = get_mattermost_file(post_file_id, bot)
      try:
        if file_response.status_code == 200:
          file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
          file_path_in_content = re.findall('filename="(.+)"', file_response.headers["Content-Disposition"])[0]
          post_file_path = f'{post_file_id}.{file_type}'
          async with aiofiles.open(post_file_path, 'wb') as post_file:
            await post_file.write(file_response.content)
          with open(post_file_path, 'rb') as perkele:
            img_byte = perkele.read()
          source_image_base64 = b64encode(img_byte).decode("utf-8")
          data = {'forms':[{'name':'caption','payload':{}}], 'source_image':source_image_base64, 'slow_workers':True}
          url = 'https://stablehorde.net/api/v2/interrogate/async'
          headers = {"Content-Type": "application/json","apikey": "a8kMOjo-sgqlThYpupXS7g"}
          response = await client.post(url, headers=headers, data=dumps(data))
          response_content = response.json()
          await sleep(15) # WHY IS THIS NECESSARY?!
          caption_res = await client.get('https://stablehorde.net/api/v2/interrogate/status/' + response_content['id'], headers=headers, timeout=420)
          caption = caption_res.json()['forms'][0]['result']['caption']
          captions.append(f'{file_path_in_content}: {caption}')
      except (RuntimeError, KeyError, IndexError) as err:
        captions.append(f'Error occurred while generating captions for file {post_file_id}: {str(err)}')
        continue
  return '\n'.join(captions)

async def storyteller(post):
  captions = await captioner(post)
  story = await generate_story_from_captions(captions)
  return story

async def consider_image_generation(message, file_ids, post):
  print('consider_image_generation')
  image_requested = await is_asking_for_image_generation(message)
  if image_requested:
    asking_for_multiple_images = await is_asking_for_multiple_images(message)
    if asking_for_multiple_images:
      image_generation_comment = await generate_images(file_ids, post, 8)
    else:
      image_generation_comment = await generate_images(file_ids, post, 1)
    return image_generation_comment
  return ''

async def generate_images(file_ids, post, count):
  comment = ''
  mainly_english = await is_mainly_english(post['message'].encode('utf-8'))
  if not mainly_english:
    comment = post['message'] = await fix_image_generation_prompt(post['message'])
  options = webui_api.get_options()
  options = {}
  options['sd_model_checkpoint'] = 'realisticVisionV30_v30VAE.safetensors [c52892e92a]'
  options['sd_vae'] = 'vae-ft-mse-840000-ema-pruned.safetensors'
  webui_api.set_options(options)
  result = webui_api.txt2img(prompt=post['message'], negative_prompt="(unfinished:1.43),(sloppy and messy:1.43),(incoherent:1.43),(deformed:1.43)", steps=42, sampler_name='UniPC', batch_size=count, restore_faces=True)
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(upload_mattermost_file(post['channel_id'], {'files':('result.png', image_file)}, bot))
  return comment

async def upscale_image_2x(file_ids, post, resize_w=1024, resize_h=1024, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = get_mattermost_file(post_file_id, bot)
    if file_response.status_code == 200:
      file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      result = webui_api.extra_single_image(post_file_image, upscaling_resize=2, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = upload_mattermost_file(post['channel_id'], {'files':(upscaled_image_path, image_file)}, bot)
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def upscale_image_4x(file_ids, post, resize_w=2048, resize_h=2048, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = get_mattermost_file(post_file_id, bot)
    if file_response.status_code == 200:
      file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      result = webui_api.extra_single_image(post_file_image, upscaling_resize=4, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = upload_mattermost_file(post['channel_id'], {'files': (upscaled_image_path, image_file)}, bot)
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def youtube_transcription(user_input):
  from gradio_client import Client
  input_str = user_input
  url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
  urls = re.findall(url_pattern, input_str)
  if urls:
    gradio = Client(environ['TRANSCRIPTION_API_URI'])
    prediction = gradio.predict(user_input, fn_index=1)
    if 'error' in prediction:
      return f"ERROR gradio.predict(): {prediction['error']}"
    ytsummary = await generate_summary_from_transcription(prediction)
    return ytsummary

async def instruct_pix2pix(file_ids, post):
  comment = ''
  for input_image_id in post['file_ids']:
    file_response = get_mattermost_file(input_image_id, bot)
    if file_response.status_code == 200:
      file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{input_image_id}.{file_type}'
      async with open(post_file_path, 'wb') as new_image:
        new_image.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      options = webui_api.get_options()
      options = {}
      options['sd_model_checkpoint'] = 'instruct-pix2pix-00-22000.safetensors [fbc31a67aa]'
      options['sd_vae'] = "None"
      webui_api.set_options(options)
      result = webui_api.img2img(images=[post_file_image], prompt=post['message'], steps=150, seed=-1, cfg_scale=7.5, denoising_strength=1.5)
      if not result:
        raise RuntimeError("API returned an invalid response")
      processed_image_path = f"processed_{input_image_id}.png"
      result.image.save(processed_image_path)
      async with open(processed_image_path, 'rb') as image_file:
        file_id = upload_mattermost_file(post['channel_id'], {'files': (processed_image_path, image_file)}, bot)
      file_ids.append(file_id)
      comment += "Image processed successfully"
    except RuntimeError as err:
      comment += f"Error occurred while processing image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, processed_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def respond_to_magic_words(post, file_ids):
  lowercase_message = post['message'].lower()
  if lowercase_message.startswith("caption"):
    magic_response = await captioner(file_ids)
  elif lowercase_message.startswith("pix2pix"):
    magic_response = await instruct_pix2pix(file_ids, post)
  elif lowercase_message.startswith("2x"):
    magic_response = await upscale_image_2x(file_ids, post)
  elif lowercase_message.startswith("4x"):
    magic_response = await upscale_image_4x(file_ids, post)
  elif lowercase_message.startswith("llm"):
    magic_response = await textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif lowercase_message.startswith("storyteller"):
    magic_response = await storyteller(post)
  elif lowercase_message.startswith("summary"):
    magic_response = await youtube_transcription(post['message'])
  else:
    return None
  return magic_response

bot.init_websocket(context_manager)
