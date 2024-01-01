from json import dumps
from math import ceil
from langdetect import detect_langs
from tiktoken import get_encoding

def count_image_tokens(w, h):
  return 85 + 170 * ceil(w/512) * ceil(h/512)

def count_tokens(msg):
  return len(get_encoding('cl100k_base').encode(dumps(msg)))

def is_mainly_english(msg):
  return detect_langs(msg)[0].lang == 'en'
