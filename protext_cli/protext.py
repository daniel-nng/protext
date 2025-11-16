#! /usr/bin/env python3
welcome_text = r"""
                                 /$$                           /$$    
                                | $$                          | $$    
  /$$$$$$   /$$$$$$   /$$$$$$  /$$$$$$    /$$$$$$  /$$   /$$ /$$$$$$  
 /$$__  $$ /$$__  $$ /$$__  $$|_  $$_/   /$$__  $$|  $$ /$$/|_  $$_/  
| $$  \ $$| $$  \__/| $$  \ $$  | $$    | $$$$$$$$ \  $$$$/   | $$    
| $$  | $$| $$      | $$  | $$  | $$ /$$| $$_____/  >$$  $$   | $$ /$$
| $$$$$$$/| $$      |  $$$$$$/  |  $$$$/|  $$$$$$$ /$$/\  $$  |  $$$$/
| $$____/ |__/       \______/    \___/   \_______/|__/  \__/   \___/  
| $$                                                                  
| $$                                                                  
|__/                                                                                                         

Cybersecurity made musical!
Generates passwords phrases from song lyrics of your chosen songs. 
Select a song from Genius.com and fetch its lyrics to create memorable passphrases.
"""

import json
import requests
import time
from typing import List, Dict, Optional
import re
import html

client_id = "UMuIuVGe24S9_XsKeoV43k2QvrGf35nzE_CTWXzOOyfDh0i1F6SykCBE1SYcvvA4" 
client_secret = "baZ4K0erwDTXbewdI6cYaCLqrkim6SDUTcFeWqPx3nZJAG0IQxmDuE-Cq7g8pUbfWmaUkcLkN8m7XKFgpl59_w"
client_access_token = "3tmZw43Nl7MrhK5684f36wQmyo1BMQSUjhn_4vt2cyh7G0Rq582PUSS4dEI5P0VW"

GENIUS_SEARCH_URL = "https://api.genius.com/search"

def user_song() -> Optional[Dict]:
    """Interactive CLI form to search Genius and let the user pick a song.

    Returns the selected song dict (simplified) or None if the user quits.
    """
    token = client_access_token

    while True:
        try:
            query = input("Search for a song or artist (or 'q' to quit): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return None

        if not query:
            continue
        if query.lower() in {"q", "quit", "exit"}:
            return None

        try:
            results = search_genius(query, token)
        except requests.HTTPError as e:
            print(f"HTTP error while searching: {e}")
            continue
        except Exception as e:
            print(f"Error while searching: {e}")
            continue

        if not results:
            print("No results found. Try another query.")
            continue

        # Display results
        print("\nSearch results:")
        for i, s in enumerate(results, start=1):
            title = s.get("full_title") or s.get("title")
            artist = s.get("artist") or "Unknown"
            print(f"  {i}. {title} — {artist}")

        # Prompt for selection
        while True:
            sel = input("Enter number to select, 's' to search again, or 'q' to quit: ").strip()
            if not sel:
                continue
            if sel.lower() in {"q", "quit", "exit"}:
                return None
            if sel.lower() in {"s", "search"}:
                break  # break to outer loop to search again
            if sel.isdigit():
                idx = int(sel) - 1
                if 0 <= idx < len(results):
                    return results[idx]
                else:
                    print("Number out of range. Try again.")
            else:
                print("Unrecognized input. Enter a number, 's', or 'q'.")

def search_genius(query: str, access_token: str, page: int = 1, max_retries: int = 3) -> List[Dict]:
    """
    Search Genius for songs matching `query`.
    Returns a list of simplified song dicts.
    Raises requests.HTTPError on non-recoverable HTTP errors.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": query, "page": page}

    attempt = 0
    while True:
        attempt += 1
        resp = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("response", {})
            hits = data.get("hits", [])
            results = []
            for hit in hits:
                r = hit.get("result", {})
                results.append({
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "full_title": r.get("full_title"),
                    "artist": r.get("primary_artist", {}).get("name"),
                    "artist_id": r.get("primary_artist", {}).get("id"),
                    "url": r.get("url"),
                    "song_art_image_url": r.get("song_art_image_url"),
                })
            return results

        if resp.status_code == 429 and attempt <= max_retries:
            # Rate limited — respect Retry-After if present
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
            time.sleep(wait)
            continue
        # For 4xx/5xx other than handled above, raise so caller can handle
    resp.raise_for_status()


def fetch_lyrics_from_url(url: str) -> Optional[str]:
    """Fetch and extract lyrics from a Genius song page URL.

    This function attempts to parse the HTML returned by the Genius song page and
    extract the lyric text. It prefers using BeautifulSoup (if installed). If
    BeautifulSoup isn't available it falls back to a regex-based extractor that
    looks for <div data-lyrics-container="true"> blocks.

    Note: Genius does not provide lyrics via their public API. Scraping pages
    may be subject to Genius's terms of service and robots.txt — use responsibly.
    """
    headers = {
        "User-Agent": "protext/1.0 (+https://github.com)"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    html_text = resp.text

    # Try BeautifulSoup first for robust parsing
    try:
        from bs4 import BeautifulSoup
    except Exception:
        # Fallback: regex-based extraction of data-lyrics-container divs
        parts = re.findall(r'<div[^>]+data-lyrics-container=\"true\"[^>]*>(.*?)</div>', html_text, flags=re.S)
        if not parts:
            # Try legacy .lyrics container
            legacy = re.search(r'<div[^>]+class=["\']lyrics["\'][^>]*>(.*?)</div>', html_text, flags=re.S)
            if legacy:
                text = re.sub(r'<.*?>', '', legacy.group(1))
                return html.unescape(text).strip()
            return None
        cleaned_parts = []
        for p in parts:
            # remove tags and unescape HTML entities
            plain = re.sub(r'<.*?>', '', p)
            cleaned_parts.append(html.unescape(plain).strip())
        return "\n\n".join(cleaned_parts).strip()

    # Using BeautifulSoup, use it to gather all lyrics blocks
    soup = BeautifulSoup(html_text, "html.parser")
    parts = soup.find_all("div", attrs={"data-lyrics-container": "true"})
    if not parts:
        # Legacy container
        legacy = soup.find("div", class_="lyrics")
        if legacy:
            return legacy.get_text("\n").strip()
        return None

    blocks = []
    for div in parts:
        # get_text preserves line breaks when using separator
        blocks.append(div.get_text(separator="\n").strip())
    return "\n\n".join(blocks).strip()

def gather_input():
    
    print(welcome_text)
    selected = user_song()
    if selected:
        print("\nSelected:")
        print(f"Title: {selected.get('full_title')}")
        print(f"Artist: {selected.get('artist')}")
        print(f"URL: {selected.get('url')}")
        # Offer to fetch lyrics
        try:
            fetch = input("Fetch lyrics for this song? (y/N): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            fetch = "n"
        if fetch in {"y", "yes"}:
            print("\nFetching lyrics...\n")
            try:
                lyrics = fetch_lyrics_from_url(selected.get("url"))
            except Exception as e:
                print(f"Error fetching lyrics: {e}")
                lyrics = None
            if lyrics:
                # Print a reasonable chunk so terminal output isn't huge
                print(lyrics[:10000])
            else:
                print("Could not fetch lyrics for this song.")
        print(f"Lyrics")
    else:
        print("No song selected. Exiting.")


if __name__ == "__main__":
    gather_input()