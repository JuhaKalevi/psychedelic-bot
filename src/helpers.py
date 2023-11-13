import json
import tiktoken

def count_tokens(msg:str) -> int:
  return len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(msg)))
