from mattermost_bot import upload_mattermost_file
from txt2txt import fix_image_generation_prompt
from txt2bool import is_asking_for_multiple_images, is_asking_for_image_generation, is_mainly_english
from webui_api import webui_api

async def consider_image_generation(message: dict, file_ids:list, post:dict) -> (str | None):
  image_requested = await is_asking_for_image_generation(message)
  if image_requested:
    asking_for_multiple_images = await is_asking_for_multiple_images(message)
    if asking_for_multiple_images:
      image_generation_comment = await generate_images(file_ids, post, 8)
    else:
      image_generation_comment = await generate_images(file_ids, post, 1)
    return image_generation_comment

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
