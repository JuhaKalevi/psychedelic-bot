import base64
from json import dumps
from os import environ, path, remove
import re
from webuiapi import WebUIApi
import PIL
import basic
import mattermost_api

webui_api = WebUIApi(host=environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

async def captioner(bot, file_ids):
  from asyncio import sleep
  import aiofiles
  captions = []
  from httpx import AsyncClient
  async with AsyncClient() as client:
    for post_file_id in file_ids:
      file_response = mattermost_api.get_mattermost_file(post_file_id, bot)
      try:
        if file_response.status_code == 200:
          file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
          file_path_in_content = re.findall('filename="(.+)"', file_response.headers["Content-Disposition"])[0]
          post_file_path = f'{post_file_id}.{file_type}'
          async with aiofiles.open(post_file_path, 'wb') as post_file:
            await post_file.write(file_response.content)
          with open(post_file_path, 'rb') as perkele:
            img_byte = perkele.read()
          source_image_base64 = base64.b64encode(img_byte).decode("utf-8")
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

async def consider_image_generation(bot, message, file_ids, post):
  image_requested = await basic.is_asking_for_image_generation(message)
  if image_requested:
    asking_for_multiple_images = await basic.is_asking_for_multiple_images(message)
    if asking_for_multiple_images:
      image_generation_comment = await generate_images(bot, file_ids, post, 8)
    else:
      image_generation_comment = await generate_images(bot, file_ids, post, 1)
    return image_generation_comment
  return None

async def storyteller(bot, file_ids):
  captions = await captioner(bot, file_ids)
  story = await basic.generate_story_from_captions(captions)
  return story

async def generate_images(bot, file_ids, post, count):
  comment = ''
  mainly_english = await basic.is_mainly_english(post['message'].encode('utf-8'))
  if not mainly_english:
    comment = post['message'] = await basic.fix_image_generation_prompt(post['message'])
  options = webui_api.get_options()
  options = {}
  options['sd_model_checkpoint'] = 'realisticVisionV30_v30VAE.safetensors [c52892e92a]'
  options['sd_vae'] = 'vae-ft-mse-840000-ema-pruned.safetensors'
  webui_api.set_options(options)
  result = webui_api.txt2img(prompt=post['message'], negative_prompt="(unfinished:1.43),(sloppy and messy:1.43),(incoherent:1.43),(deformed:1.43)", steps=42, sampler_name='UniPC', batch_size=count, restore_faces=True)
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(mattermost_api.upload_mattermost_file(post['channel_id'], {'files':('result.png', image_file)}, bot))
  return comment

async def upscale_image(bot, file_ids, post, scale):
  if scale == 2:
    upscale_width = 1024
    upscale_height = 1024
  elif scale == 4:
    upscale_width = 2048
    upscale_height = 2048
  else:
    return "Invalid upscale scale"
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mattermost_api.get_mattermost_file(post_file_id, bot)
    if file_response.status_code == 200:
      file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      result = webui_api.extra_single_image(post_file_image, upscaling_resize=scale, upscaling_resize_w=upscale_width, upscaling_resize_h=upscale_height, upscaler_1="LDSR")
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = mattermost_api.upload_mattermost_file(post['channel_id'], {'files':(upscaled_image_path, image_file)}, bot)
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
    ytsummary = await basic.generate_summary_from_transcription(prediction)
    return ytsummary

async def instruct_pix2pix(bot, file_ids, post):
  comment = ''
  for input_image_id in post['file_ids']:
    file_response = mattermost_api.get_mattermost_file(input_image_id, bot)
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
        file_id = mattermost_api.upload_mattermost_file(post['channel_id'], {'files': (processed_image_path, image_file)}, bot)
      file_ids.append(file_id)
      comment += "Image processed successfully"
    except RuntimeError as err:
      comment += f"Error occurred while processing image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, processed_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment
