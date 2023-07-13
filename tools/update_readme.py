import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']

summaries = []
for path, dirs, files in os.walk('.'):
  for file in files:
    if file.endswith(".py"):
      with open(os.path.join(path, file), "r", encoding="utf-8") as source:
        text = source.read()
        response = openai.ChatCompletion.create(
          model="gpt-4",
          prompt=f"Summarize the following Python code:\n```python\n{text}\n```",
          temperature=0.3,
          max_tokens=420
        )
        summaries.append(f"# {file}\n{response.choices[0].text.strip()}")
SOURCE_SUMMARIES = '\n'.join(summaries)
response = openai.Completion.create(
  model="gpt-4",
  prompt=f"Generate a README for a project with the following source files:\n{SOURCE_SUMMARIES}",
  temperature=0.3,
  max_tokens=1337
)
with open("README.md", "w", encoding="utf-8") as readme_file:
  readme_file.write(response.choices[0].text.strip())
