import os
import re
import hashlib
import requests
from bs4 import BeautifulSoup
import html2text
from typing import Dict, List, Tuple, Any
import logging
import traceback

logger = logging.getLogger(__name__)


class SimpleSEPScraper:
  """Minimal scraper for Stanford Encyclopedia of Philosophy articles."""

  def __init__(self):
    """Initialize the scraper."""
    self.session = requests.Session()

    # Configure html2text for markdown conversion
    self.md_converter = html2text.HTML2Text()
    self.md_converter.ignore_links = False
    self.md_converter.ignore_images = False
    self.md_converter.ignore_tables = False
    self.md_converter.body_width = 0  # No text wrapping

  def scrape_article(self, url: str) -> Dict[str, Any]:
    """
    Scrape an article from a URL.

    Args:
        url: Full URL of the article to scrape (e.g., https://plato.stanford.edu/entries/kant/)

    Returns:
        Dictionary containing article data
    """
    try:
      # Clean URL and extract entry_id
      url = url.rstrip("/")
      parts = url.split("/")
      entry_id = parts[-1]  # Last part of the URL

      # Fetch article
      logger.info(f"Fetching article from URL: {url}")
      response = self.session.get(url)
      response.raise_for_status()
      html_content = response.text

      # Parse HTML
      soup = BeautifulSoup(html_content, "html.parser")

      # Extract title
      title_elem = soup.select_one("h1.title")
      title = title_elem.text.strip() if title_elem else entry_id.replace("-", " ").title()

      # Extract metadata and content
      metadata = self._extract_metadata(soup)
      article_content, toc = self._process_content(soup)
      markdown_content = self.convert_to_markdown(article_content)

      # Generate content hash for change detection
      content_hash = hashlib.sha256(article_content.encode()).hexdigest()

      return {
        "entry_id": entry_id,
        "url": url,
        "title": title,
        "content_hash": content_hash,
        "metadata": metadata,
        "content": markdown_content,
        "toc": toc,
        "html_content": article_content,
      }
    except Exception as e:
      error_text = f"Error scraping article from {url}: {str(e)}\n{traceback.format_exc()}"
      logger.error(error_text)
      raise RuntimeError(error_text)

  def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract metadata from article.

    Returns:
        Dictionary of metadata
    """
    metadata = {}

    # Extract preamble (if any)
    preamble_elem = soup.select_one("#preamble")
    if preamble_elem:
      metadata["preamble"] = preamble_elem.text.strip()

    # Extract publication info
    pub_info = soup.select_one("#pubinfo")
    if pub_info:
      pub_text = pub_info.text.strip()

      # Extract date issued
      issued_match = re.search(r"First published\s+(.+?)(?=;|\n|$)", pub_text)
      if issued_match:
        metadata["date_issued"] = issued_match.group(1).strip()

      # Extract date modified
      modified_match = re.search(r"substantive revision\s+(.+?)(?=;|\n|$)", pub_text)
      if modified_match:
        metadata["date_modified"] = modified_match.group(1).strip()

    # Extract authors
    authors = []
    author_elem = soup.select_one("#aueditor")
    if author_elem:
      authors_text = author_elem.text.strip()
      # Remove "Entry by" if present
      authors_text = re.sub(r"^Entry by\s*:\s*", "", authors_text)
      # Split by commas, 'and', or '&'
      author_parts = re.split(r",\s*|\s+and\s+|\s*&\s*", authors_text)
      authors = [author.strip() for author in author_parts if author.strip()]

    metadata["authors"] = authors

    return metadata

  def _process_content(self, soup: BeautifulSoup) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Process article content and extract table of contents.

    Returns:
        Tuple of (processed_html, toc)
    """
    # Get the main content element
    content_elem = soup.select_one("#main-content")

    if not content_elem:
      # Fallback to aueditable (some older articles use this)
      content_elem = soup.select_one(".aueditable")

    if not content_elem:
      # Last resort, try to find content by elimination
      body = soup.body
      if body:
        for elem in body.select("#header, #footer, script, style"):
          elem.decompose()
        content_elem = body

    # Extract table of contents
    toc = self._extract_toc(content_elem)

    # Return content as HTML string
    return str(content_elem), toc

  def _extract_toc(self, content_elem: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract table of contents from content."""
    toc = []

    if not content_elem:
      return toc

    # Find all headings
    headings = content_elem.select("h2, h3, h4, h5, h6")

    for heading in headings:
      # Skip headings without IDs
      if not heading.get("id"):
        continue

      # Get heading level (h2 = 1, h3 = 2, etc.)
      level = int(heading.name[1]) - 1

      toc.append({"id": heading.get("id"), "text": heading.text.strip(), "level": level})

    return toc

  def convert_to_markdown(self, html: str) -> str:
    """Convert HTML to markdown."""
    return self.md_converter.handle(html)

  def entry_exists(self, url: str) -> bool:
    """
    Check if an article exists at the provided URL.

    Args:
        url: Full URL to check (e.g., https://plato.stanford.edu/entries/kant/)

    Returns:
        True if article exists, False otherwise
    """
    try:
      # Ensure URL is properly formatted
      if not url.startswith("https://plato.stanford.edu/entries/"):
        logger.warning(f"URL does not point to a SEP article: {url}")
        return False

      # Make a HEAD request to check if URL exists
      response = self.session.head(url)
      return response.status_code == 200
    except Exception as e:
      error_text = f"Error checking if URL exists: {url} - {str(e)}"
      logger.error(error_text)
      return False
