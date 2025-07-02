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
MAX_COMMITS_PER_REPO = 100  

# --- GOOGLE AUTH ---
def authenticate_google():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return build('calendar', 'v3', credentials=creds)

# --- GITHUB API ---
def get_repos(username):
    url = f"https://api.github.com/users/{username}/repos"
    response = requests.get(url, auth=(username, GITHUB_TOKEN))
    return [repo['name'] for repo in response.json() if repo['owner']['login'] == username]

def get_commits(username, repo):
    url = f"https://api.github.com/repos/{username}/{repo}/commits"
    params = {"per_page": MAX_COMMITS_PER_REPO}
    response = requests.get(url, auth=(username, GITHUB_TOKEN), params=params)
    commits = []
    if response.status_code == 200:
        for item in response.json():
            commit_data = item['commit']
            author = commit_data.get('author', {})
            if author.get('name') == username or author.get('email') == f"{username}@users.noreply.github.com":
                commits.append({
                    "message": commit_data['message'],
                    "datetime": commit_data['author']['date']
                })
    return commits

# --- CALENDAR EVENT CREATION ---
def create_event(service, commit):
    dt = commit['datetime']
    start = dt
    end = dt  # no duration, timestamp-only event

    event = {
        'summary': f"GitHub Commit: {commit['message']}",
        'start': {'dateTime': start, 'timeZone': TIMEZONE},
        'end': {'dateTime': end, 'timeZone': TIMEZONE},
        'description': 'Auto-generated from GitHub'
    }

    try:
        calendar_id = 'd338a544d41a8b9814e215dff15d63d8a590e6978b6df9a40ce1fa605df8cb71@group.calendar.google.com'
        service.events().insert(calendarId=calendar_id, body=event).execute()
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
        for commit in commits:
            create_event(service, commit)
            time.sleep(0.2)  # optional: avoid quota burst

    print("✅ All commits have been added to your calendar.")

if __name__ == "__main__":
    main()
