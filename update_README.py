import openai
import os

openai.api_key = os.environ['OPENAPI_API_KEY']

summaries = []
for path, dirs, files in os.walk('.'):
  for file in files:
    if file.endswith(".py"):
      with open(os.path.join(path, file), "r", encoding="utf-8") as source:
        text = source.read()
        response = openai.Completion.create(
          model="gpt-4",
          prompt=f"Summarize the following Python code:\n```python\n{text}\n```",
          temperature=0.3,
          max_tokens=420
        )
        summaries.append(f"# {file}\n{response.choices[0].text.strip()}")
source_summaries = "\n".join(summaries)
response = openai.Completion.create(
  model="gpt-4",
  prompt=f"Generate a README for a project with the following source files:\n{source_summaries}",
  temperature=0.3,
  max_tokens=512
)
with open("README.md", "w", encoding="utf-8") as readme_file:
  readme_file.write(response.choices[0].text.strip())