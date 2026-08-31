import requests
import os

def get_secret(key):
    with open(".streamlit/secrets.toml", "r") as f:
        for line in f:
            if line.startswith(key):
                return line.split("=")[1].strip().replace('"', "")
    return None

api_key = get_secret("YOUTUBE_API_KEY")
channel_id = get_secret("YOUTUBE_CHANNEL_ID")

print(f"DEBUG: Key: {api_key}, Channel: {channel_id}")

# 1. Get uploads playlist ID
url1 = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}&key={api_key}"
res1 = requests.get(url1).json()
print(f"URL1 Response: {res1}")

if 'items' in res1 and len(res1['items']) > 0:
    playlist_id = res1['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    print(f"Playlist ID: {playlist_id}")
    
    # 2. Get latest video
    url2 = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=1&playlistId={playlist_id}&key={api_key}"
    res2 = requests.get(url2).json()
    print(f"URL2 Response: {res2}")
else:
    print("Failed to get playlist ID")
