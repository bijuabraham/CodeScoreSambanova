import requests
import configparser
import os
import json
from github import Github

# Read configuration parameters from Codescore.cfg
config = configparser.ConfigParser()
config.read('codescore.cfg')

GITHUB_TOKEN = config['Github']['Token']
SONNET_API_URL = config['API']['SonnetAPIUrl']
SONNET_API_KEY = config['API']['SonnetAPIKey']
SONNET_MODEL = config['API']['SonnetModel']
DIFF_URL_TEMPLATE = config['API']['DiffUrl']

# Read repository and file names from git.dat
git_dat_file = 'git.dat'
with open(git_dat_file, 'r') as file:
    repo_name = file.readline().strip()
    file_path = file.readline().strip()

# GitHub setup
g = Github(GITHUB_TOKEN)
repo = g.get_repo(repo_name)

# Get the commit history for the specified file
commits = list(repo.get_commits(path=file_path))
if len(commits) < 2:
    print("Error: Not enough commit history.")
    print("This file needs at least 2 commits to analyze changes.")
    print(f"Current number of commits: {len(commits)}")
    exit()

latest_commit = commits[0]
previous_commit = commits[1]

diff_url = DIFF_URL_TEMPLATE.format(repo_name=repo_name, previous_commit=previous_commit.sha, latest_commit=latest_commit.sha)
headers = {'Authorization': f'token {GITHUB_TOKEN}'}
response = requests.get(diff_url, headers=headers)

if response.status_code != 200:
    print("Error fetching the diff from GitHub")
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
    exit()

diff_data = response.json().get('files', [])
diff = ""
for file in diff_data:
    if file['filename'] == file_path:
        diff = file['patch']
        break

if not diff:
    print("No diff found for the specified file")
    exit()

# Read prompt from prompt.dat in current directory
prompt_file = 'prompt.dat'
with open(prompt_file, 'r') as file:
    prompt_template = file.read()

# Split the prompt into system and user parts
system_prompt, user_prompt = prompt_template.split("--- user")
system_prompt = system_prompt.replace("--- system", "").strip()
user_prompt = user_prompt.strip()

# Format the user prompt with the commit message and diff
user_prompt = user_prompt.replace("{{message}}", latest_commit.commit.message)
user_prompt = user_prompt.replace("{{diff | truncate: 100000}}", diff)

try:
    # Initialize OpenAI client with Sambanova configuration
    from openai import OpenAI
    client = OpenAI(
        api_key=SONNET_API_KEY,
        base_url=SONNET_API_URL
    )

    # Send request to Sambanova API
    response = client.chat.completions.create(
        model=SONNET_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0,
        top_p=0.1
    )
    
    # Extract the completion
    completion = response.choices[0].message.content
    print("\nAPI Response:")
    print(completion)
    
    # Try to find and parse the JSON within the completion
    start = completion.find('{')
    end = completion.rfind('}') + 1
    
    if start >= 0 and end > start:
        json_str = completion[start:end]
        print("\nExtracted JSON string:")
        print(json_str)
        
        # Parse and pretty print the JSON
        analysis = json.loads(json_str)
        print("\nCode Analysis Results:")
        print(json.dumps(analysis, indent=2))
    else:
        print("\nNo JSON object found in the completion")
        print("Full completion text:")
        print(completion)

except Exception as e:
    print(f"\nError: {str(e)}")
    if hasattr(e, 'response'):
        print("Response details:")
        print(e.response)
