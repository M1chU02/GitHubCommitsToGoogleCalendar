import os
import requests
import datetime
import time
from tqdm import tqdm

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- CONFIGURATION ---
GITHUB_USERNAME = ""
GITHUB_TOKEN = ""
TIMEZONE = "UTC"
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = ''

# --- GOOGLE AUTH ---
def authenticate_google():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return build('calendar', 'v3', credentials=creds)

# --- GITHUB API ---
def get_repos(_):
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    params = {"per_page": 1000, "affiliation": "owner"}
    response = requests.get(url, headers=headers, params=params)

    try:
        data = response.json()
    except Exception as e:
        print("❌ Error decoding JSON:", e)
        print("🔁 Response:", response.text)
        return []

    if response.status_code != 200:
        print(f"❌ GitHub API error {response.status_code}")
        print("🔁 Response:", data)
        return []

    return [repo['full_name'] for repo in data]

def get_commits(_, repo_full_name):
    print(f"🔍 Sprawdzam repozytorium: {repo_full_name}")

    repo_url = f"https://api.github.com/repos/{repo_full_name}"
    repo_resp = requests.get(repo_url, auth=(GITHUB_USERNAME, GITHUB_TOKEN))
    if repo_resp.status_code != 200:
        print(f"⚠️ Nie udało się pobrać repo: {repo_full_name}")
        return []

    default_branch = repo_resp.json().get("default_branch", "main")
    print(f"🔀 Domyślna gałąź: {default_branch}")

    commits = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo_full_name}/commits"
        params = {"per_page": 100, "page": page, "sha": default_branch}
        response = requests.get(url, auth=(GITHUB_USERNAME, GITHUB_TOKEN), params=params)

        if response.status_code != 200:
            print(f"❌ Błąd przy pobieraniu commitów: {response.status_code}")
            break

        page_data = response.json()
        if not page_data:
            break

        for item in page_data:
            commit_data = item['commit']
            commits.append({
                "message": commit_data['message'],
                "datetime": commit_data['author']['date'],
                "sha": item['sha'],
                "repo": repo_full_name
            })

        page += 1

    return commits

# --- EVENT TRACKING ---
def has_been_synced(sha):
    if not os.path.exists("synced.txt"):
        return False
    with open("synced.txt", "r") as f:
        return sha.strip() in [line.strip() for line in f.readlines()]

def mark_as_synced(sha):
    with open("synced.txt", "a") as f:
        f.write(sha.strip() + "\n")

# --- CALENDAR EVENT CREATION ---
def create_event(service, commit):
    dt = commit['datetime']
    event = {
        'summary': f"GitHub Commit: {commit['message'][:100]}",
        'start': {'dateTime': dt, 'timeZone': TIMEZONE},
        'end': {'dateTime': dt, 'timeZone': TIMEZONE},
        'description': f"Repo: {commit['repo']}\nCommit SHA: {commit['sha']}\nAuto-generated from GitHub"
    }

    try:
        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    except Exception as e:
        print(f"Error creating event: {e}")

# --- MAIN LOGIC ---
def main():
    print("Authenticating with Google Calendar...")
    service = authenticate_google()

    print("Fetching repositories from GitHub...")
    repos = get_repos(GITHUB_USERNAME)

    for repo in tqdm(repos, desc="Processing repositories"):
        commits = get_commits(GITHUB_USERNAME, repo)
        print(f"📄 Repo: {repo} → znaleziono {len(commits)} commitów")
        for commit in commits:
            sha = commit.get("sha", None)
            if not sha:
                continue
            if not has_been_synced(sha):
                create_event(service, commit)
                mark_as_synced(sha)
                time.sleep(0.2)

    print("✅ All new commits have been added to your calendar.")

if __name__ == "__main__":
    main()