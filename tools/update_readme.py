import glob
import openai

summaries = []
for path in glob.glob('*.py'):
  print(path)
  with open(path, encoding='utf-8') as file:
    code_block = f'\n```python\n{file.read()}\n```'
    summaries.append(f"# {path}\n{openai.ChatCompletion.create(model='gpt-3.5-turbo-16k', messages=[{'role':'user','content':f'Summarize the following Python code:{code_block}'}])['choices'][0]['message']}")
with open('README.md', 'w', encoding='utf-8') as readme_file:
  readme_file.write(openai.ChatCompletion.create(model='gpt-4', messages=[{'role':'user','content':'Generate a README for a project with the following source files: {}'.format('\n'.join(summaries))}], temperature=0.3, max_tokens=1337)['choices'][0]['message']['content'])
