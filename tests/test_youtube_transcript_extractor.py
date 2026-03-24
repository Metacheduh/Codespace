"""
Tests for YouTube Transcript Extractor
"""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_manager.jobs.youtube_transcript_extractor import YouTubeTranscriptExtractor
from agent_manager.models import Database


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = MagicMock(spec=Database)
    return db


@pytest.fixture
def test_transcript():
    """Sample transcript data."""
    return [
        {"text": "Hello world", "start": 0, "duration": 2},
        {"text": "This is a test", "start": 2, "duration": 2},
        {"text": "of the YouTube transcript extractor", "start": 4, "duration": 3},
    ]


class TestYouTubeTranscriptExtractor:
    """Test suite for YouTubeTranscriptExtractor."""

    def test_extract_video_id_from_youtube_com(self):
        """Test extracting video ID from youtube.com URL."""
        url = "https://www.youtube.com/watch?v=uSTGNHGFOAo&t=3741s"
        video_id = YouTubeTranscriptExtractor._extract_video_id(url)
        assert video_id == "uSTGNHGFOAo"

    def test_extract_video_id_from_youtu_be(self):
        """Test extracting video ID from youtu.be short URL."""
        url = "https://youtu.be/uSTGNHGFOAo?t=3741"
        video_id = YouTubeTranscriptExtractor._extract_video_id(url)
        assert video_id == "uSTGNHGFOAo"

    def test_extract_video_id_invalid_url(self):
        """Test extracting video ID from invalid URL."""
        url = "https://example.com"
        video_id = YouTubeTranscriptExtractor._extract_video_id(url)
        assert video_id is None

    @patch("agent_manager.jobs.youtube_transcript_extractor.YouTubeTranscriptApi")
    def test_execute_success(self, mock_api_class, mock_db, test_transcript):
        """Test successful transcript extraction."""
        # Setup mocks
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.fetch.return_value = test_transcript

        # Create extractor
        config = {"url": "https://www.youtube.com/watch?v=uSTGNHGFOAo"}
        extractor = YouTubeTranscriptExtractor(config, mock_db)

        # Create in-memory database
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE youtube_transcripts (
                id INTEGER PRIMARY KEY,
                video_id TEXT,
                url TEXT,
                transcript TEXT,
                content_hash TEXT,
                run_id INTEGER
            )
            """
        )
        conn.commit()

        # Execute
        extractor.execute(conn, run_id=1)

        # Verify
        cursor.execute("SELECT video_id, transcript FROM youtube_transcripts WHERE run_id = 1")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "uSTGNHGFOAo"
        assert "Hello world" in row[1]
        assert "test" in row[1]

    def test_execute_no_url_provided(self, mock_db):
        """Test that error is raised when no URL is provided."""
        config = {}
        extractor = YouTubeTranscriptExtractor(config, mock_db)

        conn = sqlite3.connect(":memory:")
        with pytest.raises(ValueError, match="YouTube URL not provided"):
            extractor.execute(conn, run_id=1)

    def test_execute_invalid_url(self, mock_db):
        """Test that error is raised for invalid URL."""
        config = {"url": "https://example.com"}
        extractor = YouTubeTranscriptExtractor(config, mock_db)

        conn = sqlite3.connect(":memory:")
        with pytest.raises(ValueError, match="Could not extract video ID"):
            extractor.execute(conn, run_id=1)

    def test_content_hash(self):
        """Test content hash generation."""
        text = "Hello world"
        hash1 = YouTubeTranscriptExtractor.content_hash(text)
        hash2 = YouTubeTranscriptExtractor.content_hash(text)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex string length
