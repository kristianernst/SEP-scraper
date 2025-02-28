import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dotenv import load_dotenv
import logging
import traceback
import httpx

load_dotenv()

from supabase import create_client
from embeddings import generate_article_embeddings

logger = logging.getLogger(__name__)


class SupabaseManager:
  """Supabase manager for SEP scraper."""

  def __init__(self, supabase_url: str = None, supabase_key: str = None, enable_embeddings: bool = True):
    """
    Initialize Supabase manager.

    Args:
        supabase_url: Supabase URL, defaults to environment variable SUPABASE_URL
        supabase_key: Supabase key, defaults to environment variable SUPABASE_KEY
        enable_embeddings: Whether to generate and store embeddings for vector search
    """
    # Get Supabase connection info from environment variables or parameters
    self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
    self.supabase_key = supabase_key or os.environ.get("SUPABASE_KEY")
    self.enable_embeddings = enable_embeddings

    if not self.supabase_url or not self.supabase_key:
      raise ValueError("Supabase URL and key must be provided via environment variables or constructor parameters")

    # Create Supabase client
    self.client = create_client(self.supabase_url, self.supabase_key)

  def wait_for_db(self, max_attempts: int = 5):
    """
    Verify Supabase connection is working.

    Args:
        max_attempts: Maximum number of connection attempts

    Returns:
        True if connection succeeded, False if max attempts reached
    """
    for attempt in range(max_attempts):
      try:
        # Try a simple query to verify connection
        self.client.table("entry_metadata").select("count", count="exact").limit(1).execute()
        return True
      except Exception as e:
        logger.warning(f"Supabase connection attempt {attempt + 1}/{max_attempts} failed: {e}")
        if attempt == max_attempts - 1:
          logger.error(f"Failed to connect to Supabase: {e}")
          return False
    return False

  def save_entry(
    self,
    entry_id: str,
    title: str,
    url: str,
    date_issued: str = None,
    date_modified: str = None,
    preamble: str = None,
    content_hash: str = None,
    html: str = None,
    markdown: str = None,
    toc: List[Dict[str, Any]] = None,
    authors: List[str] = None,
  ) -> bool:
    """
    Save entry metadata and content to Supabase.

    Args:
        entry_id: Entry ID
        title: Entry title
        url: Entry URL
        date_issued: Date entry was first issued
        date_modified: Date entry was last modified
        preamble: Entry preamble
        content_hash: Hash of entry content
        html: HTML content (not saved in simplified version)
        markdown: Markdown content
        toc: Table of contents
        authors: List of authors

    Returns:
        True if saved successfully, False otherwise
    """
    try:
      # First, check if entry already exists
      logger.info(f"Checking if entry {entry_id} exists in database")
      response = self.client.table("entry_metadata").select("*").eq("entry_id", entry_id).execute()

      # Prepare metadata
      metadata = {
        "entry_id": entry_id,
        "title": title,
        "last_updated": date_modified,
        "published": date_issued,
        "preamble": preamble,
        "content_hash": content_hash,
        "authors": authors or [],
        "updated_at": datetime.now().isoformat(),
      }

      # Generate embeddings if enabled
      if self.enable_embeddings and markdown and title:
        logger.info(f"Generating embeddings for entry: {entry_id}")
        try:
          embeddings = generate_article_embeddings(title, markdown)
          if "title_embedding" in embeddings:
            metadata["title_embedding"] = embeddings["title_embedding"]
          if "content_embedding" in embeddings:
            metadata["content_embedding"] = embeddings["content_embedding"]
          logger.info(f"Successfully generated embeddings for entry: {entry_id}")
        except Exception as e:
          logger.error(f"Failed to generate embeddings for entry {entry_id}: {str(e)}")
          # Continue with save even if embeddings fail

      # Prepare content
      content = {
        "entry_id": entry_id,
        "content": html,  # Store the HTML content
        "markdown": markdown,
        "toc": toc,
        "updated_at": datetime.now().isoformat(),
      }

      # Log content details
      logger.info(f"Content data for {entry_id}: markdown length={len(markdown) if markdown else 0}, toc items={len(toc) if toc else 0}")

      if len(response.data) > 0:
        # Update existing entry
        logger.info(f"Updating existing entry in entry_metadata table: {entry_id}")
        metadata_response = self.client.table("entry_metadata").update(metadata).eq("entry_id", entry_id).execute()
        logger.info(f"Metadata update response: {metadata_response.data}")

        logger.info(f"Updating existing entry in entry_content table: {entry_id}")
        content_response = self.client.table("entry_content").update(content).eq("entry_id", entry_id).execute()
        logger.info(f"Content update response: {content_response.data}")
      else:
        # Insert new entry
        logger.info(f"Inserting new entry in entry_metadata table: {entry_id}")
        metadata_response = self.client.table("entry_metadata").insert(metadata).execute()
        logger.info(f"Metadata insert response: {metadata_response.data}")

        logger.info(f"Inserting new entry in entry_content table: {entry_id}")
        content_response = self.client.table("entry_content").insert(content).execute()
        logger.info(f"Content insert response: {content_response.data}")

      return True
    except Exception as e:
      error_text = f"Error saving entry {entry_id}: {str(e)}\n{traceback.format_exc()}"
      logger.error(error_text)
      return False

  def get_entry(self, entry_id: str) -> Dict:
    """
    Get entry by ID.

    Args:
        entry_id: Entry ID

    Returns:
        Entry data including metadata and content
    """
    try:
      # Get metadata
      metadata = self.client.table("entry_metadata").select("*").eq("entry_id", entry_id).execute()

      # Get content
      content = self.client.table("entry_content").select("*").eq("entry_id", entry_id).execute()

      # Merge data
      if len(metadata.data) > 0 and len(content.data) > 0:
        result = {**metadata.data[0]}
        result["content"] = content.data[0]
        return result

      return None
    except Exception as e:
      logger.error(f"Error getting entry: {e}")
      return None

  def list_entries(self, limit: int = 100, offset: int = 0) -> List[Dict]:
    """
    List entries.

    Args:
        limit: Maximum number of entries to return
        offset: Offset for pagination

    Returns:
        List of entry metadata
    """
    try:
      response = self.client.table("entry_metadata").select("*").order("last_scraped", desc=True).range(offset, offset + limit - 1).execute()

      return response.data
    except Exception as e:
      logger.error(f"Error listing entries: {e}")
      return []

  def search_by_text(self, query: str, limit: int = 10) -> List[Dict]:
    """
    Search entries by text.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        List of matching entries
    """
    try:
      # Search for entries where title contains the query
      response = (
        self.client.table("entry_metadata").select("entry_id, title, url, date_modified, last_scraped").ilike("title", f"%{query}%").limit(limit).execute()
      )

      results = response.data

      # If we got fewer than limit results, also search in the markdown content
      if len(results) < limit:
        remaining = limit - len(results)
        # Get entry_ids from content where markdown contains query
        content_response = self.client.table("entry_content").select("entry_id").ilike("markdown", f"%{query}%").limit(remaining).execute()

        content_entry_ids = [item["entry_id"] for item in content_response.data]

        # Exclude entry_ids already in results
        existing_ids = [item["entry_id"] for item in results]
        new_ids = [id for id in content_entry_ids if id not in existing_ids]

        # If we have new IDs to fetch, get their metadata
        if new_ids:
          # Using "in" filter for multiple IDs
          additional_entries = []
          for entry_id in new_ids:
            meta_response = (
              self.client.table("entry_metadata").select("entry_id, title, url, date_modified, last_scraped").eq("entry_id", entry_id).execute()
            )
            if meta_response.data:
              additional_entries.extend(meta_response.data)

          # Combine results
          results.extend(additional_entries)

      return results
    except Exception as e:
      logger.error(f"Error searching entries: {e}")
      return []

  def count_entries(self) -> int:
    """Count total number of entries."""
    try:
      response = self.client.table("entry_metadata").select("count", count="exact").limit(1).execute()
      return response.count
    except Exception as e:
      logger.error(f"Error counting entries: {e}")
      return 0

  def vector_search(self, query: str, limit: int = 10, search_type: str = "content", similarity_threshold: float = 0.75) -> List[Dict]:
    """
    Perform vector similarity search on articles.

    Args:
        query: Search query text
        limit: Maximum number of results to return
        search_type: Type of search ('content' or 'title')
        similarity_threshold: Minimum similarity threshold (0-1)

    Returns:
        List of articles matching the query by semantic similarity
    """
    try:
      from embeddings import generate_embedding

      # Generate embedding for the query
      query_embedding = generate_embedding(query)
      if not query_embedding:
        logger.error("Failed to generate embedding for query")
        return []

      # Execute vector search using the match_entries function
      rpc_response = self.client.rpc(
        "match_entries",
        {"query_embedding": query_embedding, "similarity_threshold": similarity_threshold, "match_count": limit, "search_type": search_type},
      ).execute()

      if rpc_response.data:
        logger.info(f"Vector search found {len(rpc_response.data)} results")
        return rpc_response.data

      # If no results, log and return empty list
      logger.warning(f"No results found for vector search query: {query}")
      return []

    except Exception as e:
      error_text = f"Error in vector search: {str(e)}\n{traceback.format_exc()}"
      logger.error(error_text)
      return []

  def regenerate_embeddings(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
    """
    Regenerate embeddings for entries in the database.
    Useful for updating existing entries after adding vector search capabilities.

    Args:
        limit: Maximum number of entries to process
        offset: Offset for pagination

    Returns:
        Dictionary with success count and failure count
    """
    success_count = 0
    failure_count = 0

    try:
      # Get entries without embeddings or process all entries
      entries_response = (
        self.client.table("entry_metadata").select("entry_id, title").order("updated_at", desc=True).range(offset, offset + limit - 1).execute()
      )

      entries = entries_response.data
      logger.info(f"Found {len(entries)} entries to process")

      for entry in entries:
        entry_id = entry["entry_id"]
        title = entry["title"]

        # Get content for this entry
        content_response = self.client.table("entry_content").select("markdown").eq("entry_id", entry_id).execute()

        if not content_response.data:
          logger.warning(f"No content found for entry: {entry_id}")
          failure_count += 1
          continue

        markdown = content_response.data[0].get("markdown")
        if not markdown:
          logger.warning(f"No markdown content for entry: {entry_id}")
          failure_count += 1
          continue

        # Generate embeddings
        try:
          embeddings = generate_article_embeddings(title, markdown)
          if not embeddings:
            logger.error(f"Failed to generate embeddings for entry: {entry_id}")
            failure_count += 1
            continue

          # Update the metadata record with embeddings
          update_data = {}
          if "title_embedding" in embeddings:
            update_data["title_embedding"] = embeddings["title_embedding"]
          if "content_embedding" in embeddings:
            update_data["content_embedding"] = embeddings["content_embedding"]

          if update_data:
            update_response = self.client.table("entry_metadata").update(update_data).eq("entry_id", entry_id).execute()

            if update_response.data:
              logger.info(f"Successfully updated embeddings for entry: {entry_id}")
              success_count += 1
            else:
              logger.error(f"Failed to update embeddings for entry: {entry_id}")
              failure_count += 1
        except Exception as e:
          logger.error(f"Error processing entry {entry_id}: {str(e)}")
          failure_count += 1

      return {"success_count": success_count, "failure_count": failure_count, "total_processed": len(entries)}
    except Exception as e:
      error_text = f"Error regenerating embeddings: {str(e)}\n{traceback.format_exc()}"
      logger.error(error_text)
      return {"success_count": success_count, "failure_count": failure_count, "error": str(e)}

  def execute_sql(self, sql: str) -> bool:
    """
    Execute a SQL statement.

    Args:
        sql: SQL statement to execute

    Returns:
        True if successful, False otherwise
    """
    try:
      # For executing SQL, we need to use the Supabase REST API directly
      # by making a POST request to the SQL endpoint
      headers = {
        "apikey": self.supabase_key,
        "Authorization": f"Bearer {self.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
      }

      url = f"{self.supabase_url}/rest/v1/rpc/exec"

      # Create a client with proper SSL verification
      with httpx.Client(verify=True) as client:
        response = client.post(url, headers=headers, json={"query": sql})

        if response.status_code < 300:
          logger.info(f"SQL executed successfully: {sql[:50]}...")
          return True
        else:
          logger.error(f"Error executing SQL: {response.status_code} - {response.text}")
          return False

    except Exception as e:
      logger.error(f"Error executing SQL: {str(e)}")
      return False
