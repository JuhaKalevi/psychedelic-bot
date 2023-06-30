import os
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

def openai_chat_completion(messages, model='gpt-4'):
  try:
    openai_response_content = openai.ChatCompletion.create(model=model, messages=messages)['choices'][0]['message']['content']
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.Timeout) as err:
    openai_response_content = f"OpenAI API Error: {err}"
  return openai_response_content