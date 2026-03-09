"""
Confluence REST API client using only Python stdlib (urllib).
"""

import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional


class ConfluenceError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ConfluenceClient:
    def __init__(self, base_url: str, username: str, api_token: str):
        # Normalize base URL: strip trailing slash, handle /wiki/spaces/... input
        if "/spaces/" in base_url:
            base_url = base_url.split("/spaces/")[0]
        self.base_url = base_url.rstrip("/")

        credentials = f"{username}:{api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self._auth_header = f"Basic {encoded}"

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/rest/api/content{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": self._auth_header,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            raise ConfluenceError(
                f"Confluence API error {e.code} on {method} {url}: {body_text}",
                status_code=e.code,
            ) from e
        except urllib.error.URLError as e:
            raise ConfluenceError(f"Network error reaching Confluence: {e.reason}") from e

    def _page_url(self, page_id: str, space_key: str = "", title: str = "") -> str:
        """Build a human-readable Confluence page URL."""
        if space_key and title:
            encoded_title = urllib.parse.quote(title.replace(" ", "+"), safe="+")
            return f"{self.base_url}/spaces/{space_key}/pages/{page_id}/{encoded_title}"
        return f"{self.base_url}/pages/{page_id}"

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    def create_page(
        self,
        space_key: str,
        title: str,
        wiki_content: str,
        parent_id: Optional[str] = None,
    ) -> dict:
        """Create a new Confluence page.

        Returns dict with keys: page_id, page_url, version, space_key, title
        """
        payload: dict = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": wiki_content,
                    "representation": "wiki",
                }
            },
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        result = self._request("POST", "", payload)
        page_id = str(result["id"])
        return {
            "page_id": page_id,
            "page_url": self._page_url(page_id, space_key, title),
            "version": result["version"]["number"],
            "space_key": space_key,
            "title": result["title"],
        }

    def update_page(self, page_id: str, title: str, wiki_content: str) -> dict:
        """Update an existing Confluence page (auto-increments version).

        Returns dict with keys: page_id, page_url, version, space_key, title
        """
        # Fetch current version and space
        current = self._request("GET", f"/{page_id}?expand=version,space")
        current_version = current["version"]["number"]
        space_key = current["space"]["key"]

        payload = {
            "type": "page",
            "title": title,
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": wiki_content,
                    "representation": "wiki",
                }
            },
        }
        result = self._request("PUT", f"/{page_id}", payload)
        return {
            "page_id": page_id,
            "page_url": self._page_url(page_id, space_key, title),
            "version": result["version"]["number"],
            "space_key": space_key,
            "title": result["title"],
        }

    def get_page_info(self, page_id: str) -> dict:
        """Fetch basic page metadata (no body content).

        Returns dict with keys: page_id, title, space_key, version, page_url
        """
        result = self._request("GET", f"/{page_id}?expand=version,space")
        space_key = result["space"]["key"]
        title = result["title"]
        return {
            "page_id": page_id,
            "title": title,
            "space_key": space_key,
            "version": result["version"]["number"],
            "page_url": self._page_url(page_id, space_key, title),
        }

    def get_page_wiki(self, page_id: str) -> dict:
        """Fetch page content in wiki markup format.

        Returns dict with keys: page_id, title, space_key, version, page_url, wiki_content
        """
        result = self._request(
            "GET", f"/{page_id}?expand=body.wiki_markup,version,space"
        )
        space_key = result["space"]["key"]
        title = result["title"]
        wiki_content = result.get("body", {}).get("wiki_markup", {}).get("value", "")
        return {
            "page_id": page_id,
            "title": title,
            "space_key": space_key,
            "version": result["version"]["number"],
            "page_url": self._page_url(page_id, space_key, title),
            "wiki_content": wiki_content,
        }


def extract_page_id_from_url(url_or_id: str) -> str:
    """Accept either a raw page ID or a Confluence URL and return the page ID."""
    if url_or_id.isdigit():
        return url_or_id
    # Try /pages/<id>/ pattern
    for part in url_or_id.split("/"):
        if part.isdigit():
            return part
    raise ConfluenceError(
        f"Cannot extract page ID from: {url_or_id}\n"
        "Provide a numeric page ID or a Confluence URL containing /pages/<id>/."
    )
