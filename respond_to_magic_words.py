from any2any import captioner, upscale_image_2x, upscale_image_4x, textgen_chat_completion, storyteller, youtube_transcription
from instruct_pix2pix import instruct_pix2pix

async def respond_to_magic_words(post:dict, file_ids:list):
  lowercase_message = post['message'].lower()
  if lowercase_message.startswith("caption"):
    magic_response = await captioner(file_ids)
  elif lowercase_message.startswith("pix2pix"):
    magic_response = await instruct_pix2pix(file_ids, post)
  elif lowercase_message.startswith("2x"):
    magic_response = await upscale_image_2x(file_ids, post)
  elif lowercase_message.startswith("4x"):
    magic_response = await upscale_image_4x(file_ids, post)
  elif lowercase_message.startswith("llm"):
    magic_response = await textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif lowercase_message.startswith("storyteller"):
    magic_response = await storyteller(post)
  elif lowercase_message.startswith("summary"):
    magic_response = await youtube_transcription(post['message'])
  else:
    return None
  return magic_response
