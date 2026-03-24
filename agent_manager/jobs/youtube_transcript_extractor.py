"""
YouTube Transcript Extractor Job

Extracts transcripts from YouTube videos and stores them in the database.
"""

import logging
import re
import sqlite3
from typing import Any
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

from agent_manager.jobs.base import BaseJob
from agent_manager.models import Database

logger = logging.getLogger(__name__)


class YouTubeTranscriptExtractor(BaseJob):
    """Extracts transcripts from YouTube videos."""

    name = "youtube_transcript_extractor"

    def execute(self, conn: sqlite3.Connection, run_id: int) -> None:
        """Extract transcript from a YouTube URL.

        Config should contain:
          - url: The YouTube video URL
        """
        url = self.config.get("url")
        if not url:
            raise ValueError("YouTube URL not provided in config")

        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        logger.info(f"Extracting transcript for video: {video_id}")

        try:
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id)
        except Exception as e:
            logger.error(f"Failed to extract transcript: {e}")
            raise

        # Combine transcript entries into a single text
        full_transcript = "\n".join([entry["text"] for entry in transcript])
        content_hash = self.content_hash(full_transcript)

        # Store in database
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO youtube_transcripts (video_id, url, transcript, content_hash, run_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (video_id, url, full_transcript, content_hash, run_id),
        )
        conn.commit()

        logger.info(
            f"Transcript stored for {video_id}. "
            f"Length: {len(full_transcript)} characters"
        )

    @staticmethod
    def _extract_video_id(url: str) -> str | None:
        """Extract video ID from various YouTube URL formats."""
        # Handle youtu.be short links
        if "youtu.be/" in url:
            match = re.search(r"youtu\.be/([a-zA-Z0-9_-]+)", url)
            if match:
                return match.group(1)

        # Handle youtube.com links
        if "youtube.com" in url or "youtube.co" in url:
            parsed = urlparse(url)
            if parsed.query:
                params = parse_qs(parsed.query)
                if "v" in params:
                    return params["v"][0]

        return None
