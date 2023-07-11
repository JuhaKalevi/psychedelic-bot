import re
from asyncio import sleep
from base64 import b64encode
from json import dumps, loads
from os import environ, listdir, path, remove
import chardet
import langdetect
from httpx import AsyncClient
import aiofiles
import requests
import gradio_client
import tiktoken
from PIL import Image
from mattermost_bot import channel_from_post, get_mattermost_file, upload_mattermost_file
from openai_api import openai_chat_completion
from webui_api import webui_api

async def upscale_image_2x(file_ids:list, post:dict, resize_w:int=1024, resize_h:int=1024, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = get_mattermost_file(post_file_id)
    if file_response.status_code == 200:
      file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = Image.open(post_file_path)
      result = webui_api.extra_single_image(post_file_image, upscaling_resize=2, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = upload_mattermost_file(post['channel_id'], files={'files':(upscaled_image_path, image_file)})
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def captioner(file_ids:list) -> str:
  captions = []
  async with AsyncClient() as client:
    for post_file_id in file_ids:
      file_response = get_mattermost_file(post_file_id)
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

async def storyteller(post:dict) -> str:
  captions = await captioner(post)
  story = await generate_story_from_captions(captions)
  return story

async def upscale_image_4x(file_ids:list, post:dict, resize_w:int=2048, resize_h:int=2048, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = get_mattermost_file(post_file_id)
    if file_response.status_code == 200:
      file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = Image.open(post_file_path)
      result = webui_api.extra_single_image(post_file_image, upscaling_resize=4, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = upload_mattermost_file(post['channel_id'], files={'files': (upscaled_image_path, image_file)})
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def consider_image_generation(message: dict, file_ids:list, post:dict) -> str:
  image_requested = await is_asking_for_image_generation(message)
  if image_requested:
    asking_for_multiple_images = await is_asking_for_multiple_images(message)
    if asking_for_multiple_images:
      image_generation_comment = await generate_images(file_ids, post, 8)
    else:
      image_generation_comment = await generate_images(file_ids, post, 1)
    return image_generation_comment
  return ''

async def generate_images(file_ids:list, post:dict, count:int) -> str:
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
      file_ids.append(upload_mattermost_file(post['channel_id'], files={'files':('result.png', image_file)}))
  return comment

async def generate_text_from_message(message:dict, model='gpt-4') -> str:
  response = await openai_chat_completion([{'role': 'user', 'content': message}], model)
  return response

async def is_asking_for_channel_summary(post:dict) -> bool:
  channel = await channel_from_post(post)
  if channel['display_name'] == 'GitLab':
    return 'True'
  response = await generate_text_from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {post["message"]}')
  return response.startswith('True')

async def is_asking_for_code_analysis(post:dict) -> bool:
  channel = await channel_from_post(post)
  if channel['display_name'] == 'GitLab' or post['message'].startswith('@code-analysis'):
    return 'True'
  response = await generate_text_from_message(f"Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {post['message']}")
  return response.startswith('True')

async def is_asking_for_image_generation(message:dict) -> bool:
  response = await generate_text_from_message(f"Is this a message where an image is probably requested? Answer only True or False: {message}")
  return response.startswith('True')

async def is_asking_for_multiple_images(message:dict) -> bool:
  response = await generate_text_from_message(f"Is this a message where multiple images are requested? Answer only True or False: {message}")
  return response.startswith('True')

async def is_mainly_english(text:str) -> bool:
  response = langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"
  return response

async def choose_system_message(post:dict, analyze_code:bool=False) -> list:
  default_system_message = [{'role':'system', 'content':'You are an assistant with no specific role determined right now.'}]
  if not analyze_code:
    analyze_code = await is_asking_for_code_analysis(post)
  if analyze_code:
    code_snippets = []
    for file_path in [x for x in listdir() if x.endswith('.py')]:
      with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
      code_snippets.append(f'--- BEGIN {file_path} ---\n{code}\n')
    default_system_message = [{'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)}]
  return default_system_message

async def count_tokens(message:str) -> int:
  return len(tiktoken.get_encoding('cl100k_base').encode(dumps(message)))

async def fix_image_generation_prompt(prompt:str) -> str:
  fixed_prompt = await generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}")
  return fixed_prompt

async def generate_story_from_captions(message:dict, model='gpt-4') -> str:
  story = await openai_chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {message}")}], model)
  return story

async def generate_text_from_context(context:dict, model='gpt-4') -> str:
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await choose_system_message(context['posts'][context['order'][0]])
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
  if environ['LOG_LEVEL'] == 'Trace':
    print(f'TRACE: context_tokens: {context_tokens}')
  context_messages.reverse()
  openai_response = await openai_chat_completion(system_message + context_messages, model)
  return openai_response

async def generate_summary_from_transcription(message:dict, model='gpt-4'):
  response = await openai_chat_completion([
    {
      'role': 'user',
      'content': (f"Summarize in appropriate detail, adjusting the summary length"
        f" according to the transcription's length, the YouTube-video transcription below."
        f" Also make a guess on how many different characters' speech is included in the transcription."
        f" Also analyze the style of this video (comedy, drama, instructional, educational, etc.)."
        f" IGNORE all advertisement(s), sponsorship(s), discount(s), promotions(s),"
        f" all War Thunder/Athletic Green etc. talk completely. Also give scoring 0-10 about the video for each of these three categories: originality, difficulty, humor, boringness, creativity, artful, . Transcription: {message}")
    }
], model)
  return response

async def textgen_chat_completion(user_input:str, history:dict) -> str:
  request = {
    'user_input': user_input,
    'max_new_tokens': 1200,
    'history': history,
    'mode': 'instruct',
    'character': 'Example',
    'instruction_template': 'WizardLM',
    'your_name': 'You',
    'regenerate': False,
    '_continue': False,
    'stop_at_newline': False,
    'chat_generation_attempts': 1,
    'chat-instruct_command': 'Continue the chat dialogue below. Write a lengthy step-by-step answer for the character "<|character|>".\n\n<|prompt|>',
    'preset': 'None',
    'do_sample': True,
    'temperature': 0.7,
    'top_p': 0.1,
    'typical_p': 1,
    'epsilon_cutoff': 0,  # In units of 1e-4
    'eta_cutoff': 0,  # In units of 1e-4
    'tfs': 1,
    'top_a': 0,
    'repetition_penalty': 1.18,
    'repetition_penalty_range': 0,
    'top_k': 40,
    'min_length': 0,
    'no_repeat_ngram_size': 0,
    'num_beams': 1,
    'penalty_alpha': 0,
    'length_penalty': 1,
    'early_stopping': False,
    'mirostat_mode': 0,
    'mirostat_tau': 5,
    'mirostat_eta': 0.1,
    'seed': -1,
    'add_bos_token': True,
    'truncation_length': 2048,
    'ban_eos_token': False,
    'skip_special_tokens': True,
    'stopping_strings': []
  }
  response = requests.post(environ['TEXTGEN_WEBUI_URI'], json=request, timeout=420)
  if response.status_code == 200:
    response_content = loads(response.text)
    results = response_content["results"]
    for result in results:
      chat_history = result.get("history", {})
      internal_history = chat_history.get("internal", [])
      if internal_history:
        last_entry = internal_history[-1]
        if len(last_entry) > 1:
          answer = last_entry[1]
          return answer
  return 'oops'

async def youtube_transcription(user_input:str) -> str:
  input_str = user_input
  url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
  urls = re.findall(url_pattern, input_str)
  if urls:
    gradio = gradio_client.Client(environ['TRANSCRIPTION_API_URI'])
    prediction = gradio.predict(user_input, fn_index=1)
    if 'error' in prediction:
      return f"ERROR gradio.predict(): {prediction['error']}"
    ytsummary = await generate_summary_from_transcription(prediction)
    return ytsummary
