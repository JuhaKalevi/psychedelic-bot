from json import dumps, loads
from os import environ, path, listdir, remove
import chardet
import langdetect
import openai
import requests
import mattermostdriver
import tiktoken
import webuiapi
from PIL import Image

DEBUG_LEVEL = int(environ['DEBUG_LEVEL'])
openai.api_key = environ['OPENAI_API_KEY']
BOT_NAME = environ['MATTERMOST_BOTNAME']

async def maybe_debug(value):
  if DEBUG_LEVEL > 0:
    print(value)
  return value

async def is_mainly_english(text: str) -> bool:
  response = await maybe_debug(langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en")
  return response

async def count_tokens(message: str) -> int:
  token_count = await maybe_debug(len(tiktoken.get_encoding('cl100k_base').encode(dumps(message))))
  return token_count

async def channel_from_post(post: dict) -> dict:
  channel = await maybe_debug(mm.channels.get_channel(post['channel_id']))
  return channel

async def channel_context(post: dict) -> dict:
  context = await maybe_debug(mm.posts.get_posts_for_channel(post['channel_id']))
  return context

async def thread_context(post: dict) -> dict:
  context = await maybe_debug({'order':[post['id']], 'posts':{post['id']:post}})
  return context

async def choose_system_message(post: dict) -> list:
  analyze_code = await is_asking_for_code_analysis(post['message'])
  if analyze_code:
    code_snippets = []
    for file_path in [x for x in listdir() if x.endswith('.py')]:
      with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
      code_snippets.append(f'--- BEGING {file_path} ---\n{code}\n')
    return [{'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)}]
  return [{'role':'system', 'content':'You are an assistant with no specific role determined right now.'}]

async def is_asking_for_channel_summary(message: dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_code_analysis(message: dict) -> bool:
  if message.startswith('@code-analysis'):
    response = "True"
  else:
    response = await generate_text_from_message(f'Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_image_generation(message: dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_multiple_images(message: dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_configured_for_replies_without_tagging(channel: dict) -> bool:
  if channel['display_name'] == 'Testing':
    return True
  if f"{BOT_NAME} responds without tagging" in channel['purpose']:
    return True
  return False

async def respond_to_magic_words(post: dict, file_ids: list):
  if post['message'].lower().startswith("2x"):
    response = await upscale_image_2x(file_ids, post)
  elif post['message'].lower().startswith("4x"):
    response = await upscale_image_4x(file_ids, post)
  elif post['message'].lower().startswith("pix2pix"):
    response = await instruct_pix2pix(file_ids, post)
  elif post['message'].lower().startswith("llm"):
    response = await textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif post['message'].lower().startswith("transcribe"):
    response = await youtube_transcription(post['message'])
  else:
    return None
  return response

async def create_mattermost_post(options: dict) -> dict:
  try:
    mm.posts.create_post(options=options)
    return "Posted successfully"
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    return f"Mattermost API Error: {err}"

async def generate_text_from_message(message: dict, model='gpt-4'):
  response = await openai_chat_completion([{'role': 'user', 'content': message}], model)
  return response

async def openai_chat_completion(messages: list, model='gpt-4'):
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return str(response['choices'][0]['message']['content'])
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout) as err:
    return f"OpenAI API Error: {err}"

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

async def generate_text_from_context(context: dict) -> str:
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

async def context_manager(event: dict):
  file_ids = []
  event = loads(event)
  response = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != BOT_NAME:
    post = loads(event['data']['post'])
    message = post['message']
    thread = post['root_id']
    if thread == '':
      channel = await channel_from_post(post)
      reply_without_tagging = await is_configured_for_replies_without_tagging(channel)
      if reply_without_tagging:
        reply_to = post['id']
        response = await respond_to_magic_words(post, file_ids)
        if response is None:
          context = await channel_context(post)
          response = await generate_text_from_context(context)
    elif thread == '' and BOT_NAME in message:
      reply_to = post['id']
      response = await respond_to_magic_words(post, file_ids)
      if response is None:
        summarize = await is_asking_for_channel_summary(message)
        if summarize:
          context = await channel_context(post)
        else:
          context = await thread_context(post)
        response = await generate_text_from_context(context)
      if response is None:
        image_requested = await is_asking_for_image_generation(message)
        if image_requested:
          response = await generate_images(file_ids, post, 8)
        else:
          response = await generate_images(file_ids, post, 1)
    else:
      reply_to = post['root_id']
      context = await thread_context(post)
      if any(BOT_NAME in context_post['message'] for context_post in context['posts'].values()):
        response = await generate_text_from_context(context)
    if response:
      response_posted = await create_mattermost_post(options={'channel_id':post['channel_id'], 'message':response, 'file_ids':file_ids, 'root_id':reply_to})
      return response_posted

async def fix_image_generation_prompt(prompt):
  return await generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}")

async def generate_images(file_ids, post, count):
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
      file_ids.append(mm.files.upload_file(post['channel_id'], files={'files': ('result.png', image_file)})['file_infos'][0]['id'])
  return comment

async def upscale_image_4x(file_ids, post, resize_w: int = 2048, resize_h: int = 2048, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mm.files.get_file(file_id=post_file_id)
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
        file_id = mm.files.upload_file(post['channel_id'], files={'files': (upscaled_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def upscale_image_2x(file_ids, post, resize_w: int = 1024, resize_h: int = 1024, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mm.files.get_file(file_id=post_file_id)
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
        file_id = mm.files.upload_file(post['channel_id'], files={'files': (upscaled_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def instruct_pix2pix(file_ids, post):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mm.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = Image.open(post_file_path)
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
        file_id = mm.files.upload_file(post['channel_id'], files={'files': (processed_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image processed successfully"
    except RuntimeError as err:
      comment += f"Error occurred while processing image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, processed_image_path):
        if path.exists(temporary_file_path):
          remove(temporary_file_path)
  return comment

async def youtube_transcription(user_input):
  print(user_input)
  return user_input
#  if user_input.startswith("transcribe @gpt3 "):
#    print(user_input)
#    regex = r"\[(.*?)\]\((.*?)\)"
#    matches = re.findall(regex, user_input)
#    if matches:
        # matches[0][1] will give the URL present in user_input
#      user_input = matches[0][1]
#    else:
#      return "Incorrect command format. Please use the following format: 'transcribe @gpt3 [http://youtubeURL](http://youtubeURL)'"
#    client = Client(TRANSCRIPTION_API_URI)
#    response = client.predict(user_input, fn_index=1)
#    print(response)
#    return response
#  return "Incorrect command format. Please use the following format: 'transcribe @gpt3 [http://youtubeURL](http://youtubeURL)'"


mm = mattermostdriver.Driver({'url': environ['MATTERMOST_URL'], 'token': environ['MATTERMOST_TOKEN'], 'scheme':'https', 'port':443})
mm.login()
mm.init_websocket(context_manager)

webui_api = webuiapi.WebUIApi(host=environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', environ['STABLE_DIFFUSION_WEBUI_API_KEY'])
