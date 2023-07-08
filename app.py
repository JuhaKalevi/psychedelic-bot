import base64
import json
import os
import re
import time
import chardet
import langdetect
import requests
import gradio_client
import openai
import mattermostdriver
import tiktoken
import webuiapi
import PIL

openai.api_key = os.environ['OPENAI_API_KEY']
BOT_NAME = os.environ['MATTERMOST_BOTNAME']
TRANSCRIPTION_API_URI = "https://d007e5503a6b32d07a.gradio.live"
mattermost = mattermostdriver.Driver({'url': os.environ['MATTERMOST_URL'], 'token': os.environ['MATTERMOST_TOKEN'], 'scheme':'https', 'port':443})
mattermost.login()
webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

async def captioner(post):
  caption = ''
  for post_file_id in post['file_ids']:
    file_response = mattermost.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
  url = "https://stablehorde.net/api/v2/interrogate/async"
  headers = {"Content-Type": "application/json", "apikey": "a8kMOjo-sgqlThYpupXS7g"}
  with open(post_file_path, 'rb') as perkele:
    img_byte = perkele.read()
  source_image_base64 = base64.b64encode(img_byte).decode("utf-8")
  data = {
      "forms": [
          {
              "name": "caption",
              "payload": {} # Additional form payload data should go here, based on spec
          }
      ],
      "source_image": source_image_base64, # Here is the base64 image
      "slow_workers": True
  }
  response = post(url, headers=headers, data=data, timeout=420)
  print(response.json())
  response_content = response.json()
  id_value = response_content['id']
  print(id_value)
  time.sleep(20)
  caption = requests.get(f"https://stablehorde.net/api/v2/interrogate/status/{id_value}", headers=headers, timeout=420)
  json_response = caption.json()
  print(json_response)
  caption=json_response['forms'][0]['result']['caption']
  print(caption)
  return caption

async def channel_context(post:dict) -> dict:
  context = mattermost.posts.get_posts_for_channel(post['channel_id'])
  return context

async def channel_from_post(post:dict) -> dict:
  channel = mattermost.channels.get_channel(post['channel_id'])
  return channel

async def choose_system_message(post:dict) -> list:
  analyze_code = await is_asking_for_code_analysis(post['message'])
  if analyze_code:
    print('analyze_code: True')
    code_snippets = []
    for file_path in [x for x in os.listdir() if x.endswith('.py')]:
      with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
      code_snippets.append(f'--- BEGIN {file_path} ---\n{code}\n')
    return [{'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)}]
  return [{'role':'system', 'content':'You are an assistant with no specific role determined right now.'}]

async def consider_image_generation(message: dict, file_ids:list, post:dict):
  image_requested = await is_asking_for_image_generation(message)
  print(f'image_requested: {image_requested}')
  if image_requested:
    asking_for_multiple_images = await is_asking_for_multiple_images(message)
    if asking_for_multiple_images:
      response = await generate_images(file_ids, post, 8)
    else:
      response = await generate_images(file_ids, post, 1)
    return response

async def context_manager(event:dict):
  file_ids = []
  event = json.loads(event)
  signal = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != BOT_NAME:
    post = json.loads(event['data']['post'])
    signal = await respond_to_magic_words(post, file_ids)
    message = post['message']
    channel = await channel_from_post(post)
    reply_untagged = await should_reply_untagged(channel)
    print(f'reply_untagged: {reply_untagged}')
    if BOT_NAME in channel['purpose'] or reply_untagged:
      signal = await consider_image_generation(message, file_ids, post)
      if not signal:
        summarize = await is_asking_for_channel_summary(message)
        if summarize:
          context = await channel_context(post)
        else:
          context = await thread_context(post)
    elif BOT_NAME in message:
      context = await generate_text_from_message(message)
      reply_to = post['id']
    else:
      context = await thread_context(post)
      reply_to = post['id']
      if any(BOT_NAME in context_post['message'] for context_post in context['posts'].values()):
        signal = await generate_text_from_context(context)
    if signal:
      await create_mattermost_post(options={'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':reply_to})

async def count_tokens(message:str) -> int:
  return len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))

async def create_mattermost_post(options:dict):
  try:
    mattermost.posts.create_post(options=options)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f"Mattermost API Error: {err}")

async def fix_image_generation_prompt(prompt):
  return await generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}")

async def generate_images(file_ids:list, post:dict, count:int):
  comment = ''
  if not is_mainly_english(post['message'].encode('utf-8')):
    comment = post['message'] = await fix_image_generation_prompt(post['message'])
  options = webui_api.get_options()
  options = {}
  options['sd_model_checkpoint'] = 'realisticVisionV30_v30VAE.safetensors [c52892e92a]'
  options['sd_vae'] = 'vae-ft-mse-840000-ema-pruned.safetensors'
  webui_api.set_options(options)
  result = webui_api.txt2img(prompt = post['message'], negative_prompt = "(unfinished:1.43), (sloppy and messy:1.43), (incoherent:1.43), (deformed:1.43)", steps = 42, sampler_name = 'UniPC', batch_size = count, restore_faces = True)
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(mattermost.files.upload_file(post['channel_id'], files={'files': ('result.png', image_file)})['file_infos'][0]['id'])
  return comment

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

async def generate_text_from_context(context:dict) -> str:
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
  context_messages.reverse()
  openai_response = await openai_chat_completion(system_message + context_messages, 'gpt-4')
  return openai_response

async def generate_text_from_message(message:dict, model='gpt-4'):
  response = await openai_chat_completion([{'role': 'user', 'content': message}], model)
  return response

async def instruct_pix2pix(file_ids:list, post:dict):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mattermost.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      options = webui_api.get_options()
      options = {}
      options['sd_model_checkpoint'] = 'instruct-pix2pix-00-22000.safetensors [fbc31a67aa]'
      options['sd_vae'] = "None"
      webui_api.set_options(options)
      result = webui_api.img2img(images = [post_file_image], prompt = post['message'], steps = 150, seed = -1, cfg_scale = 7.5, denoising_strength=1.5)
      if not result:
        raise RuntimeError("API returned an invalid response")
      processed_image_path = f"processed_{post_file_id}.png"
      result.image.save(processed_image_path)
      async with open(processed_image_path, 'rb') as image_file:
        file_id = mattermost.files.upload_file(post['channel_id'], files={'files': (processed_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image processed successfully"
    except RuntimeError as err:
      comment += f"Error occurred while processing image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, processed_image_path):
        if os.path.exists(temporary_file_path):
          os.remove(temporary_file_path)
  return comment

async def is_asking_for_channel_summary(message:dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_code_analysis(message:dict) -> bool:
  if message.startswith('@code-analysis'):
    response = 'True'
  else:
    response = await generate_text_from_message(f'Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_image_generation(message:dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_multiple_images(message:dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_mainly_english(text:str) -> bool:
  response = await langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"
  return response

async def openai_chat_completion(messages:list, model='gpt-4'):
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return str(response['choices'][0]['message']['content'])
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout) as err:
    return f"OpenAI API Error: {err}"

async def respond_to_magic_words(post:dict, file_ids:list):
  if post['message'].lower().startswith("2x"):
    response = await upscale_image_2x(file_ids, post)
  elif post['message'].lower().startswith("4x"):
    response = await upscale_image_4x(file_ids, post)
  elif post['message'].lower().startswith("pix2pix"):
    response = await instruct_pix2pix(file_ids, post)
  elif post['message'].lower().startswith("llm"):
    response = await textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif post['message'].lower().startswith("summary"):
    response = await youtube_transcription(post['message'])
  elif post['message'].lower().startswith("caption"):
    response = await captioner(post)
  else:
    return None
  return response

async def should_reply_untagged(channel:dict) -> bool:
  if channel['type'] == 'D':
    return True
  if f"{BOT_NAME} responds without tagging" in channel['purpose']:
    return True
  return False

async def textgen_chat_completion(user_input, history):
  request = {
    'user_input': user_input,
    'max_new_tokens': 800,
    'history': history,
    'mode': 'instruct',
    'character': 'Example',
    'instruction_template': 'WizardLM',
    'your_name': 'You',
    'regenerate': False,
    '_continue': False,
    'stop_at_newline': False,
    'chat_generation_attempts': 1,
    'chat-instruct_command': 'Continue the chat dialogue below. Write a single reply for the character "<|character|>".\n\n<|prompt|>',
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
  response = requests.post(os.environ['TEXTGEN_WEBUI_URI'], json=request, timeout=420)
  if response.status_code == 200:
    response_content = json.loads(response.text)
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

async def thread_context(post:dict) -> dict:
  context = {'order':[post['id']], 'posts':{post['id']:post}}
  return context

async def upscale_image_2x(file_ids:list, post:dict, resize_w:int=1024, resize_h:int=1024, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mattermost.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      result = webui_api.extra_single_image(post_file_image, upscaling_resize=2, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = mattermost.files.upload_file(post['channel_id'], files={'files': (upscaled_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if os.path.exists(temporary_file_path):
          os.remove(temporary_file_path)
  return comment

async def upscale_image_4x(file_ids:list, post:dict, resize_w:int=2048, resize_h:int=2048, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mattermost.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      result = webui_api.extra_single_image(post_file_image, upscaling_resize=4, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = mattermost.files.upload_file(post['channel_id'], files={'files': (upscaled_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if os.path.exists(temporary_file_path):
          os.remove(temporary_file_path)
  return comment

async def youtube_transcription(user_input):
  input_str = user_input
  url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
  urls = re.findall(url_pattern, input_str)
  if urls:
    new_user_input = urls[0]  # Take the first URL found
    print(new_user_input)
    client = gradio_client.Client(TRANSCRIPTION_API_URI)
    response = client.predict(user_input, fn_index=1)
    print(response)
    ytsummary = await generate_summary_from_transcription(response)
    print(ytsummary)
    return ytsummary
  print("No URL found in the input.")

mattermost.init_websocket(context_manager)
