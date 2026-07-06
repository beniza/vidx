from unittest.mock import MagicMock
import pytest
from vidx.youtube import YouTubePublisher, QuotaExceededError, YOUTUBE_AVAILABLE
from vidx.manifest import ManifestEntry


@pytest.mark.skipif(not YOUTUBE_AVAILABLE, reason="Google API libraries not installed")
def test_youtube_publisher_quota_check(tmp_path):
    pub = YouTubePublisher(
        client_secrets_file=str(tmp_path / "secrets.json"),
        token_file=str(tmp_path / "token.json"),
        quota_limit=2000,
    )
    assert pub.quota_used == 0

    pub.check_quota(1600)  # Should pass
    pub.quota_used = 1600

    with pytest.raises(QuotaExceededError):
        pub.check_quota(500)  # 1600 + 500 = 2100 > 2000


@pytest.mark.skipif(not YOUTUBE_AVAILABLE, reason="Google API libraries not installed")
def test_youtube_publisher_mocked_upload(tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.write_text("dummy mp4 data")

    thumb_file = tmp_path / "title_card.jpg"
    thumb_file.write_text("dummy jpg data")

    pub = YouTubePublisher(
        client_secrets_file=str(tmp_path / "secrets.json"),
        token_file=str(tmp_path / "token.json"),
    )

    mock_service = MagicMock()
    # Mock videos().insert().next_chunk()
    mock_req = MagicMock()
    mock_status = MagicMock()
    mock_status.progress.return_value = 1.0
    mock_req.next_chunk.return_value = (mock_status, {"id": "mock_yt_id_123"})
    mock_service.videos.return_value.insert.return_value = mock_req

    # Mock thumbnails().set()
    mock_service.thumbnails.return_value.set.return_value.execute.return_value = {}

    # Mock playlists
    mock_service.playlists.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "pl_existing_1", "snippet": {"title": "Gospel of Mark"}}]
    }
    mock_service.playlistItems.return_value.insert.return_value.execute.return_value = {
        "id": "pli_item_1"
    }

    pub.service = mock_service
    pub.credentials = MagicMock()

    entry = ManifestEntry(
        id="Mark_Ch01",
        video_path=str(video_file),
        thumbnail_path=str(thumb_file),
        book="Mark",
        chapter=1,
        language="Sindhi",
        title="Mark Chapter 01",
        description="Listen to Mark 1",
        privacy_status="unlisted",
        category_id="22",
        playlist_name="Gospel of Mark",
        tags=["Scripture", "Sindhi"],
    )

    vid_id = pub.publish_entry(entry)
    assert vid_id == "mock_yt_id_123"
    # Quota used: 1600 (video) + 50 (thumbnail) + 50 (playlist item) = 1700
    assert pub.quota_used == 1700
