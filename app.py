import json
import os
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
  return generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}') == 'True'

def is_asking_for_multiple_images(message):
  return generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}') == 'True'

def is_mainly_english(text):
  return langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"

def upscale_image(file_ids, post, resize_w: int = 1024, resize_h: int = 1024, upscaler="R-ESRGAN 4x+"):
  comment = ''
  for post_file_id in post['file_ids']:
    mm.files.get_file(post_file_id)
    image_path = mm.files.get_file(file_id=post_file_id)
    print(image_path)
    try:
      with open(image_path, 'wb') as image_file:
        image_file.write(image_binary)
      result = webui_api.extra_single_image(
        image_path,
        upscaling_resize=2,
        upscaling_resize_w=resize_w,
        upscaling_resize_h=resize_h,
        upscaler_1=upscaler,
      )
      result.image.save("upscaled_result.png")
      with open('upscaled_result.png', 'rb') as image_file:
        file_id = mm.files.upload_file(
          post['channel_id'],
          files={'files': ('upscaled_result.png', image_file)}
        )['file_infos'][0]['id']
        file_ids.append(file_id)
        comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      os.remove(image_path)
      if os.path.exists('upscaled_result.png'):
        os.remove('upscaled_result.png')
  else:
    comment = "No image file attached in the post"
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

def generate_text_from_context(context):
  messages = []
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    messages.append({'role': role, 'content': context['posts'][post_id]['message']})
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
