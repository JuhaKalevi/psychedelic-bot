import bot
import mattermost_api
import txt2bool
import txt2txt

async def consider_image_generation(message: dict, file_ids:list, post:dict) -> (str | None):
  image_requested = await txt2bool.is_asking_for_image_generation(message)
  if image_requested:
    asking_for_multiple_images = await txt2bool.is_asking_for_multiple_images(message)
    if asking_for_multiple_images:
      image_generation_comment = await generate_images(file_ids, post, 8)
    else:
      image_generation_comment = await generate_images(file_ids, post, 1)
    return image_generation_comment

async def generate_images(file_ids:list, post:dict, count:int) -> str:
  comment = ''
  mainly_english = await txt2bool.is_mainly_english(post['message'].encode('utf-8'))
  if not mainly_english:
    comment = post['message'] = await txt2txt.fix_image_generation_prompt(post['message'])
  options = bot.webui_api.get_options()
  options = {}
  options['sd_model_checkpoint'] = 'realisticVisionV30_v30VAE.safetensors [c52892e92a]'
  options['sd_vae'] = 'vae-ft-mse-840000-ema-pruned.safetensors'
  bot.webui_api.set_options(options)
  result = bot.webui_api.txt2img(prompt = post['message'], negative_prompt = "(unfinished:1.43), (sloppy and messy:1.43), (incoherent:1.43), (deformed:1.43)", steps = 42, sampler_name = 'UniPC', batch_size = count, restore_faces = True)
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(mattermost_api.files.upload_file(post['channel_id'], files={'files':('result.png', image_file)})['file_infos'][0]['id'])
  return comment
