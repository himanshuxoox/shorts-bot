"""
One-off API upload test, used as evidence for the YouTube API audit.

    pip install google-auth-oauthlib google-api-python-client
    python test_upload.py ball_escape_sample.mp4

Opens the Google consent screen, then uploads the file as a PRIVATE test video
through videos.insert and prints its link. Needs client_secret.json in this folder.
"""
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
path = sys.argv[1] if len(sys.argv) > 1 else "ball_escape_sample.mp4"

creds = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES) \
    .run_local_server(port=0, access_type="offline", prompt="consent")
yt = build("youtube", "v3", credentials=creds)

body = {
    "snippet": {"title": "API upload test (Shorts Bot)",
                "description": "Test upload via YouTube Data API videos.insert for the API compliance audit.",
                "categoryId": "24"},
    "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
}
print(f"Uploading {path} via videos.insert ...")
req = yt.videos().insert(part="snippet,status", body=body,
                         media_body=MediaFileUpload(path, mimetype="video/mp4", resumable=True))
resp = None
while resp is None:
    status, resp = req.next_chunk()
    if status:
        print(f"  {int(status.progress() * 100)}%")
print(f"Done. Video ID: {resp['id']}")
print(f"Studio: https://studio.youtube.com/video/{resp['id']}/edit")
