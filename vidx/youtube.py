"""
YouTube API Publisher Module for VIDX
Handles OAuth 2.0 authentication, resumable chunked video uploading, thumbnail attachment,
playlist management, and quota expenditure tracking (Option 2 Outbox pattern).
"""

import os
from pathlib import Path
from typing import Optional, Callable
from .manifest import ManifestEntry

try:
    import google.oauth2.credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    HttpError = Exception


class QuotaExceededError(Exception):
    """Raised when the daily YouTube API quota allowance is approached or exceeded."""

    pass


class YouTubePublisher:
    """Manages YouTube Data API v3 authentication and publishing operations."""

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ]

    def __init__(
        self,
        client_secrets_file: str = "~/.vidx/client_secrets.json",
        token_file: str = "~/.vidx/youtube_token.json",
        quota_limit: int = 9500,
    ):
        if not YOUTUBE_AVAILABLE:
            raise RuntimeError(
                "YouTube API dependencies not installed. Please run: pip install vidx[youtube]"
            )

        self.client_secrets_file = Path(client_secrets_file).expanduser().resolve()
        self.token_file = Path(token_file).expanduser().resolve()
        self.quota_limit = quota_limit
        self.quota_used = 0
        self.service = None
        self.credentials = None

    def authenticate(self, console_flow: bool = False):
        """Authenticate via OAuth 2.0, loading cached refresh tokens or initiating browser loopback."""
        creds = None
        if self.token_file.exists():
            try:
                creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
                    str(self.token_file), self.SCOPES
                )
            except Exception as e:
                print(f"[!] Warning: Could not load token file {self.token_file}: {e}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                if not self.client_secrets_file.exists():
                    raise FileNotFoundError(
                        f"YouTube OAuth client secrets file not found at: {self.client_secrets_file}\n"
                        "Please download OAuth 2.0 Client IDs (Desktop App) from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secrets_file), self.SCOPES
                )
                if console_flow or os.environ.get("VIDX_HEADLESS", "") == "1":
                    # For headless server terminals where browser opening fails
                    try:
                        creds = flow.run_console()
                    except AttributeError:
                        # Fallback for newer oauthlib versions where run_console is deprecated
                        creds = flow.run_local_server(port=0, open_browser=False)
                else:
                    creds = flow.run_local_server(port=0)

            # Cache the token
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, "w", encoding="utf-8") as token_fp:
                token_fp.write(creds.to_json())

        self.credentials = creds
        self.service = build("youtube", "v3", credentials=creds)

    def check_quota(self, cost: int):
        """Verify that executing an API action will not exceed the safety quota limit."""
        if self.quota_used + cost > self.quota_limit:
            raise QuotaExceededError(
                f"YouTube daily API quota safety limit ({self.quota_limit} units) reached. "
                f"Current session expenditure: {self.quota_used} units. "
                "Stopping publishing cleanly to preserve outbox state for next quota reset."
            )

    def upload_video(
        self,
        entry: ManifestEntry,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> str:
        """
        Upload an MP4 video file to YouTube using resumable chunked media upload.
        Cost: 1,600 quota units.
        Returns the uploaded YouTube Video ID.
        """
        self.check_quota(1600)
        if not self.service:
            self.authenticate()

        video_path = Path(entry.video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found for upload: {video_path}")

        body = {
            "snippet": {
                "title": entry.title,
                "description": entry.description,
                "tags": entry.tags,
                "categoryId": str(entry.category_id or "22"),
            },
            "status": {
                "privacyStatus": entry.privacy_status or "unlisted",
                "selfDeclaredMadeForKids": False,
            },
        }

        # 5 MB chunk size for resumable upload
        chunk_size = 5 * 1024 * 1024
        media = MediaFileUpload(
            str(video_path),
            chunksize=chunk_size,
            resumable=True,
            mimetype="video/mp4",
        )

        request = self.service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                try:
                    progress_callback(status.progress())
                except Exception:
                    pass

        self.quota_used += 1600
        video_id = response.get("id")
        if not video_id:
            raise RuntimeError(f"Upload completed but no video ID returned: {response}")
        return video_id

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """
        Attach a custom thumbnail JPG/PNG to an uploaded video.
        Cost: 50 quota units.
        """
        self.check_quota(50)
        if not self.service:
            self.authenticate()

        thumb_p = Path(thumbnail_path)
        if not thumb_p.exists():
            print(f"[!] Thumbnail file not found: {thumb_p}")
            return False

        media = MediaFileUpload(str(thumb_p), mimetype="image/jpeg")
        self.service.thumbnails().set(videoId=video_id, media_body=media).execute()
        self.quota_used += 50
        return True

    def get_or_create_playlist(self, playlist_name: str) -> str:
        """
        Locate an existing YouTube playlist by title or create a new unlisted playlist.
        Cost: 0 units (list) + 50 units (insert if created).
        """
        if not self.service:
            self.authenticate()

        # Search existing playlists
        request = self.service.playlists().list(
            part="snippet", mine=True, maxResults=50
        )
        while request is not None:
            response = request.execute()
            for item in response.get("items", []):
                if item.get("snippet", {}).get("title") == playlist_name:
                    return item["id"]
            request = self.service.playlists().list_next(request, response)

        # Create new playlist if not found
        self.check_quota(50)
        body = {
            "snippet": {"title": playlist_name},
            "status": {"privacyStatus": "unlisted"},
        }
        res = (
            self.service.playlists().insert(part="snippet,status", body=body).execute()
        )
        self.quota_used += 50
        return res["id"]

    def add_to_playlist(self, video_id: str, playlist_name: str) -> Optional[str]:
        """
        Add an uploaded video to a named playlist.
        Cost: 50 quota units.
        """
        if not playlist_name:
            return None
        self.check_quota(50)
        if not self.service:
            self.authenticate()

        playlist_id = self.get_or_create_playlist(playlist_name)
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        }
        res = self.service.playlistItems().insert(part="snippet", body=body).execute()
        self.quota_used += 50
        return res.get("id")

    def publish_entry(
        self,
        entry: ManifestEntry,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> str:
        """
        Execute full publishing pipeline for a single manifest entry:
        1. Upload Video
        2. Set Thumbnail (if present)
        3. Add to Playlist (if specified)
        Returns uploaded YouTube Video ID.
        """
        video_id = self.upload_video(entry, progress_callback=progress_callback)
        if entry.thumbnail_path and Path(entry.thumbnail_path).exists():
            try:
                self.set_thumbnail(video_id, entry.thumbnail_path)
            except Exception as e:
                print(f"[!] Warning: Thumbnail upload failed for {entry.id}: {e}")

        if entry.playlist_name:
            try:
                self.add_to_playlist(video_id, entry.playlist_name)
            except Exception as e:
                print(
                    f"[!] Warning: Playlist item insertion failed for {entry.id}: {e}"
                )

        return video_id
