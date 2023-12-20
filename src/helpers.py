from json import dumps
from math import ceil
from tiktoken import get_encoding

def count_image_tokens(w, h):
  return 85 + 170 * ceil(w/512) * ceil(h/512)

def count_tokens(msg) -> int:
  return len(get_encoding('cl100k_base').encode(dumps(msg)))
