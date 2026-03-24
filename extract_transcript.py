#!/usr/bin/env python3
"""
Quick script to extract and display YouTube transcript
"""

import sys
import re
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url: str) -> str | None:
    """Extract video ID from YouTube URL."""
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_transcript.py <youtube_url>")
        sys.exit(1)

    url = sys.argv[1]
    video_id = extract_video_id(url)

    if not video_id:
        print(f"Error: Could not extract video ID from URL: {url}")
        sys.exit(1)

    print(f"Extracting transcript for video ID: {video_id}")
    print("-" * 80)

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)
        full_transcript = "\n".join([entry["text"] for entry in transcript])
        print(full_transcript)
        print("-" * 80)
        print(f"\nTranscript length: {len(full_transcript)} characters")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
