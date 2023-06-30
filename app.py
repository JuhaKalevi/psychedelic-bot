import json
import os
from PIL import Image
import chardet
import langdetect
import mattermostdriver
import openai
import webuiapi

openai.api_key = os.environ['OPENAI_API_KEY']
mm = mattermostdriver.Driver({
  'url': os.environ['MATTERMOST_URL'],
  'token': os.environ['MATTERMOST_TOKEN'],
  'port': 443
})
webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

def is_asking_for_image_generation(message):
  return generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}').startswith('True')

def is_asking_for_multiple_images(message):
  return generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}').startswith('True')

def is_mainly_english(text):
  return langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"

def upscale_image(file_ids, post, resize_w: int = 2048, resize_h: int = 2048, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mm.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      post_file_path=f'{post_file_id}.jpg'
      with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = Image.open(post_file_path)
      result = webui_api.extra_single_image(
        post_file_image,
        upscaling_resize=4,
        upscaling_resize_w=resize_w,
        upscaling_resize_h=resize_h,
        upscaler_1=upscaler,
      )
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      with open(upscaled_image_path, 'rb') as image_file:
        file_id = mm.files.upload_file(
          post['channel_id'],
          files={'files': (upscaled_image_path, image_file)}
        )['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if os.path.exists(temporary_file_path):
          os.remove(temporary_file_path)
  return comment

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']:
    post = json.loads(event['data']['post'])
    if post['root_id'] == "":
      if os.environ['MATTERMOST_BOTNAME'] not in post['message']:
        return
      thread_id = post['id']
      if post['message'].lower().startswith("4x"):
        openai_response_content = upscale_image(file_ids, post)
      elif is_asking_for_image_generation(post['message']):
        if is_asking_for_multiple_images(post['message']):
          openai_response_content = generate_images(file_ids, post, 8)
        else:
          openai_response_content = generate_images(file_ids, post, 1)
      else:
        context = {'order': [post['id']], 'posts': {post['id']: post}}
        openai_response_content = generate_text_from_context(context)
    else:
      thread_id = post['root_id']
      context = mm.posts.get_thread(post['id'])
      if not any(os.environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
        return
      openai_response_content = generate_text_from_context(context)
    try:
      mm.posts.create_post(options={'channel_id':post['channel_id'], 'message':openai_response_content, 'file_ids':file_ids, 'root_id':thread_id})
    except (mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f"Mattermost API Error: {err}")

def fix_image_generation_prompt(prompt):
  return generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}")

def generate_images(file_ids, post, count):
  comment = ''
  if not is_mainly_english(post['message'].encode('utf-8')):
    comment = post['message'] = fix_image_generation_prompt(post['message'])
  result = webui_api.txt2img(
    prompt = post['message'],
    negative_prompt = "(unfinished:1.5), (sloppy and messy:1.5), (incoherent:1.5), (deformed:1.5)",
    steps = 42,
    sampler_name = 'UniPC',
    batch_size = count,
    restore_faces = True
  )
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(mm.files.upload_file(post['channel_id'], files={'files': ('result.png', image_file)})['file_infos'][0]['id'])
  return comment

def select_system_message(message):
  system_message = []
  code_snippets = []
  if generate_text_from_message(f"Is this a message where an analysis of your chatbot code is requested? Don't care whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False!: {message}") == 'True':
    for file_path in ['app.py']:
      with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()
      code_snippets.append(f"--- {file_path} ---\n{code}\n")
    system_message.append({'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)})
  return system_message

def generate_text_from_context(context):
  messages = []
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    messages.append({'role': role, 'content': context['posts'][post_id]['message']})
  messages += select_system_message(context['posts'][post_id]['message'])
  return openai_chat_completion(messages, os.environ['OPENAI_MODEL_NAME'])

def generate_text_from_message(message, model='gpt-4'):
  return openai_chat_completion([{'role': 'user', 'content': message}], model)

def openai_chat_completion(messages, model='gpt-4'):
  try:
    openai_response_content = openai.ChatCompletion.create(model=model, messages=messages)['choices'][0]['message']['content']
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.Timeout) as err:
    openai_response_content = f"OpenAI API Error: {err}"
  return openai_response_content

mm.login()
mm.init_websocket(context_manager)
