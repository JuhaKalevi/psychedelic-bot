
import os
import bot
import mattermost_api
import PIL

async def instruct_pix2pix(file_ids:list, post:dict):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mattermost_api.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      options = bot.webui_api.get_options()
      options = {}
      options['sd_model_checkpoint'] = 'instruct-pix2pix-00-22000.safetensors [fbc31a67aa]'
      options['sd_vae'] = "None"
      bot.webui_api.set_options(options)
      result = bot.webui_api.img2img(images = [post_file_image], prompt = post['message'], steps = 150, seed = -1, cfg_scale = 7.5, denoising_strength=1.5)
      if not result:
        raise RuntimeError("API returned an invalid response")
      processed_image_path = f"processed_{post_file_id}.png"
      result.image.save(processed_image_path)
      async with open(processed_image_path, 'rb') as image_file:
        file_id = mattermost_api.files.upload_file(post['channel_id'], files={'files': (processed_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image processed successfully"
    except RuntimeError as err:
      comment += f"Error occurred while processing image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, processed_image_path):
        if os.path.exists(temporary_file_path):
          os.remove(temporary_file_path)
  return comment

async def upscale_image_2x(file_ids:list, post:dict, resize_w:int=1024, resize_h:int=1024, upscaler="LDSR"):
  comment = ''
  for post_file_id in post['file_ids']:
    file_response = mattermost_api.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      result = bot.webui_api.extra_single_image(post_file_image, upscaling_resize=2, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = mattermost_api.files.upload_file(post['channel_id'], files={'files': (upscaled_image_path, image_file)})['file_infos'][0]['id']
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
    file_response = mattermost_api.files.get_file(file_id=post_file_id)
    if file_response.status_code == 200:
      file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
      post_file_path = f'{post_file_id}.{file_type}'
      async with open(post_file_path, 'wb') as post_file:
        post_file.write(file_response.content)
    try:
      post_file_image = PIL.Image.open(post_file_path)
      result = bot.webui_api.extra_single_image(post_file_image, upscaling_resize=4, upscaling_resize_w=resize_w, upscaling_resize_h=resize_h, upscaler_1=upscaler)
      upscaled_image_path = f"upscaled_{post_file_id}.png"
      result.image.save(upscaled_image_path)
      async with open(upscaled_image_path, 'rb') as image_file:
        file_id = mattermost_api.files.upload_file(post['channel_id'], files={'files': (upscaled_image_path, image_file)})['file_infos'][0]['id']
      file_ids.append(file_id)
      comment += "Image upscaled successfully"
    except RuntimeError as err:
      comment += f"Error occurred while upscaling image: {str(err)}"
    finally:
      for temporary_file_path in (post_file_path, upscaled_image_path):
        if os.path.exists(temporary_file_path):
          os.remove(temporary_file_path)
  return comment
