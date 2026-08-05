"""
Parses filenames/captions like:
    "Mob Psycho 100 S01 E09 [480p] Tamil.mkv"
    "Solo Leveling - S1E12 - 1080p - Multi Audio.mkv"
    "Attack on Titan Season 2 Episode 5 720p Hindi Dub"

into (title, season, episode, quality, audio).
"""
import re
from dataclasses import dataclass
from typing import Optional

QUALITY_RE = re.compile(r"\b(480p|576p|720p|1080p|2160p|4k)\b", re.IGNORECASE)
SEASON_EP_RE = re.compile(
    r"\bS(?:eason)?\s?0*(\d{1,2})\s?[\s._-]?\s?E(?:p(?:isode)?)?\s?0*(\d{1,4})\b",
    re.IGNORECASE,
)
SEASON_ONLY_RE = re.compile(r"\bS(?:eason)?\s?0*(\d{1,2})\b", re.IGNORECASE)
EPISODE_ONLY_RE = re.compile(r"\bE(?:p(?:isode)?)?\s?0*(\d{1,4})\b", re.IGNORECASE)

KNOWN_LANGUAGES = [
    "tamil", "english", "hindi", "telugu", "malayalam", "japanese", "kannada",
    "korean", "multi", "dual audio", "dubbed", "sub",
]

JUNK_TOKENS = [
    r"\[.*?\]", r"\(.*?\)", r"@\w+", r"https?://\S+", r"www\.\S+",
    r"\.mkv|\.mp4|\.avi|\.webm", r"HEVC|x264|x265|10bit|WEB-?DL|HDRip|BluRay|WEBRip",
]


@dataclass
class ParsedFile:
    title: str
    season: int
    episode: Optional[int]
    quality: str
    audio: str
    is_movie: bool = False


def _extract_quality(text: str) -> str:
    match = QUALITY_RE.search(text)
    return match.group(1).lower() if match else "unknown"


def _extract_languages(text: str) -> str:
    found = [lang.title() for lang in KNOWN_LANGUAGES if lang in text.lower()]
    # de-dup while keeping order, skip generic descriptors when a real language is present
    real = [l for l in found if l.lower() not in ("multi", "dual audio", "dubbed", "sub")]
    chosen = real or found
    return " + ".join(dict.fromkeys(chosen)) if chosen else "Unknown"


def _extract_season_episode(text: str):
    match = SEASON_EP_RE.search(text)
    if match:
        return int(match.group(1)), int(match.group(2))

    season_match = SEASON_ONLY_RE.search(text)
    episode_match = EPISODE_ONLY_RE.search(text)
    season = int(season_match.group(1)) if season_match else 1
    episode = int(episode_match.group(1)) if episode_match else None
    return season, episode


def _extract_title(text: str, season: int, episode: Optional[int]) -> str:
    cleaned = text
    for pattern in JUNK_TOKENS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = QUALITY_RE.sub(" ", cleaned)
    cleaned = SEASON_EP_RE.sub(" ", cleaned)
    cleaned = SEASON_ONLY_RE.sub(" ", cleaned)
    cleaned = EPISODE_ONLY_RE.sub(" ", cleaned)
    for lang in KNOWN_LANGUAGES:
        cleaned = re.sub(rf"\b{re.escape(lang)}\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[._]+", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -_.")
    return cleaned.title() if cleaned else "Unknown Title"


def parse(filename: str, caption: str = "") -> ParsedFile:
    """Caption usually has cleaner/more reliable metadata than the raw
    filename - prefer it, fall back to the filename."""
    text = caption if caption.strip() else filename

    season, episode = _extract_season_episode(text)
    quality = _extract_quality(text)
    audio = _extract_languages(text)
    title = _extract_title(text, season, episode)
    is_movie = episode is None and "movie" in text.lower()

    return ParsedFile(
        title=title,
        season=season,
        episode=episode if episode is not None else 1,
        quality=quality,
        audio=audio,
        is_movie=is_movie,
    )


def season_key(season: int) -> str:
    return f"S{season:02d}"


def episode_key(episode: int) -> str:
    return f"E{episode:02d}"
