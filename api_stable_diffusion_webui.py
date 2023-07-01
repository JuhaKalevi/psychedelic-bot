import os
import webuiapi
from PIL import Image
from api_mattermost import mm
from language_processing import generate_text_from_message, is_mainly_english

webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

async def fix_image_generation_prompt(prompt):
  return generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}")

async def generate_images(file_ids, post, count):
  comment = ''
  if not is_mainly_english(post['message'].encode('utf-8')):
    comment = post['message'] = fix_image_generation_prompt(post['message'])
  result = webui_api.txt2img(
    prompt = post['message'],
    negative_prompt = "(unfinished:1.43), (sloppy and messy:1.43), (incoherent:1.43), (deformed:1.43)",
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

async def upscale_image(file_ids, post, resize_w: int = 2048, resize_h: int = 2048, upscaler="LDSR"):
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
