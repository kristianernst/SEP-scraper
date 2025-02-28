import os
import logging
from typing import Dict, Any, List, Optional
import traceback

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from simple_scraper import SimpleSEPScraper
from supabase_client import SupabaseManager

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
  title="Stanford Encyclopedia of Philosophy Scraper API",
  description="API for scraping and converting SEP articles to markdown",
  version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Initialize scraper and database
scraper = SimpleSEPScraper()
db_manager = SupabaseManager()


# Dependency for database access
def get_db():
  """Return the database manager instance."""
  return db_manager


# Pydantic models for API responses
class EntryItem(BaseModel):
  """Model for a philosopher entry."""

  url: str
  title: str


class EntryList(BaseModel):
  """Model for entry list response."""

  entries: List[EntryItem]
  count: int


class ScrapeRequest(BaseModel):
  """Request model for scrape endpoint."""

  url: str = Field(..., description="Full URL of the SEP article to scrape")


class ScrapeResult(BaseModel):
  """Response model for scrape results."""

  url: str
  title: str
  success: bool
  message: str


# Error handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
  error_msg = f"Unhandled error: {str(exc)}\n{traceback.format_exc()}"
  logger.error(error_msg)
  return JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})


# API endpoints
@app.get("/")
async def root():
  """Root endpoint with API information."""
  return {
    "name": "Stanford Encyclopedia of Philosophy Scraper API",
    "version": "1.0.0",
    "description": "Simplified API for scraping and accessing Stanford Encyclopedia of Philosophy articles",
    "endpoints": [
      {"path": "/", "method": "GET", "description": "This information"},
      {
        "path": "/entries",
        "method": "GET",
        "description": "List all articles in the database",
        "parameters": [
          {"name": "limit", "type": "integer", "description": "Maximum number of entries to return (default: 100)"},
          {"name": "offset", "type": "integer", "description": "Offset for pagination (default: 0)"},
        ],
      },
      {
        "path": "/entry",
        "method": "GET",
        "description": "Get a specific article from the database by URL",
        "parameters": [
          {
            "name": "url",
            "type": "string",
            "required": True,
            "description": "Full URL of the SEP article (e.g., https://plato.stanford.edu/entries/kant/)",
          }
        ],
      },
      {
        "path": "/scrape",
        "method": "POST",
        "description": "Scrape an article by URL and save to database",
        "request_body": {
          "content_type": "application/json",
          "schema": {
            "type": "object",
            "properties": {
              "url": {"type": "string", "description": "Full URL of the SEP article to scrape (e.g., https://plato.stanford.edu/entries/kant/)"}
            },
            "required": ["url"],
          },
        },
      },
      {
        "path": "/search",
        "method": "GET",
        "description": "Search articles by keyword",
        "parameters": [
          {"name": "query", "type": "string", "required": True, "description": "Search query"},
          {"name": "limit", "type": "integer", "description": "Maximum number of results (default: 10)"},
        ],
      },
      {
        "path": "/vector-search",
        "method": "GET",
        "description": "Semantic search using vector embeddings",
        "parameters": [
          {"name": "query", "type": "string", "required": True, "description": "Search query"},
          {"name": "limit", "type": "integer", "description": "Maximum number of results (default: 10)"},
          {"name": "search_type", "type": "string", "description": "Type of search: 'content' or 'title' (default: 'content')"},
          {"name": "similarity_threshold", "type": "number", "description": "Minimum similarity threshold (0-1)"},
        ],
      },
      {
        "path": "/regenerate-embeddings",
        "method": "POST",
        "description": "Regenerate embeddings for existing articles (admin only)",
        "request_body": {
          "content_type": "application/json",
          "schema": {
            "type": "object",
            "properties": {
              "limit": {"type": "integer", "description": "Maximum number of articles to process"},
              "offset": {"type": "integer", "description": "Offset for pagination"},
            },
          },
        },
      },
    ],
  }


@app.get("/entries", response_model=EntryList)
async def list_entries(
  limit: int = Query(100, description="Maximum number of entries to return"),
  offset: int = Query(0, description="Offset for pagination"),
  db: SupabaseManager = Depends(get_db),
):
  """List all entries in the database."""
  try:
    entries = db.list_entries(limit=limit, offset=offset)
    count = db.count_entries()

    # Transform entries to match the expected model
    entry_items = [EntryItem(url=entry.get("url", ""), title=entry.get("title", "")) for entry in entries]

    return {"entries": entry_items, "count": count}
  except Exception as e:
    error_msg = f"Error listing entries: {str(e)}"
    logger.error(error_msg)
    raise HTTPException(status_code=500, detail=error_msg)


@app.get("/entry")
async def get_entry(url: str = Query(..., description="Full URL of the SEP article to retrieve"), db: SupabaseManager = Depends(get_db)):
  """Get a specific entry from the database by URL."""
  try:
    # Validate URL format
    if not url.startswith("https://plato.stanford.edu/entries/"):
      raise HTTPException(
        status_code=400,
        detail="Invalid URL format. Must be a full Stanford Encyclopedia of Philosophy URL: https://plato.stanford.edu/entries/{entry_id}/",
      )

    # Extract entry_id from URL
    parts = url.rstrip("/").split("/")
    entry_id = parts[-1]

    # Get entry from database
    entry = db.get_entry(entry_id)

    if not entry:
      raise HTTPException(status_code=404, detail=f"Entry not found for URL: {url}")

    # Make sure content is included and properly structured
    if "content" in entry and entry["content"]:
      # Return a well-structured response with content included
      result = {
        "url": entry.get("url", url),
        "title": entry.get("title", ""),
        "entry_id": entry.get("entry_id", entry_id),
        "date_issued": entry.get("date_issued"),
        "date_modified": entry.get("date_modified"),
        "preamble": entry.get("preamble"),
        "last_scraped": entry.get("last_scraped"),
        "content": {"markdown": entry["content"].get("markdown", ""), "toc": entry["content"].get("toc", [])},
      }
      return result
    else:
      # If content is missing but we have the metadata
      logger.warning(f"Entry found but content is missing for URL: {url}")
      raise HTTPException(status_code=404, detail=f"Content not found for URL: {url}")
  except HTTPException:
    # Re-raise HTTP exceptions
    raise
  except Exception as e:
    error_msg = f"Error retrieving entry: {str(e)}"
    logger.error(f"{error_msg}\n{traceback.format_exc()}")
    raise HTTPException(status_code=500, detail=error_msg)


@app.post("/scrape", response_model=ScrapeResult)
async def scrape_url(request: ScrapeRequest, db: SupabaseManager = Depends(get_db)):
  """
  Scrape an article using its full URL and save to database.

  Args:
      request: Request with URL of the SEP article to scrape

  Returns:
      Status message with scraping results
  """
  url = request.url

  try:
    # Validate URL format
    if not url.startswith("https://plato.stanford.edu/entries/"):
      raise HTTPException(
        status_code=400,
        detail="Invalid URL format. Must be a full Stanford Encyclopedia of Philosophy URL: https://plato.stanford.edu/entries/{entry_id}/",
      )

    # Extract entry_id from URL
    parts = url.rstrip("/").split("/")
    entry_id = parts[-1]  # Last part of the URL

    # Check if the article exists at the provided URL
    if not scraper.entry_exists(url):
      raise HTTPException(status_code=404, detail=f"No article found at URL: {url}")

    # Scrape the article
    logger.info(f"Scraping article from URL: {url}")
    data = scraper.scrape_article(url)

    # Save to database
    metadata = data["metadata"]
    success = db.save_entry(
      entry_id=entry_id,
      title=data["title"],
      url=url,
      date_issued=metadata.get("date_issued"),
      date_modified=metadata.get("date_modified"),
      preamble=metadata.get("preamble"),
      content_hash=data.get("content_hash"),
      html=data.get("html_content"),  # Include the original HTML if available
      markdown=data["content"],
      toc=data.get("toc"),
      authors=metadata.get("authors", []),
    )

    if success:
      logger.info(f"Successfully scraped and saved URL: {url}")
      return {"url": url, "title": data["title"], "success": True, "message": "Article successfully scraped and saved to database"}
    else:
      error_msg = f"Failed to save article to database for URL: {url}"
      logger.error(error_msg)
      return {"url": url, "title": data["title"], "success": False, "message": "Article was scraped but could not be saved to database"}
  except HTTPException:
    # Re-raise HTTP exceptions
    raise
  except Exception as e:
    error_msg = f"Error scraping URL {url}: {str(e)}"
    logger.error(f"{error_msg}\n{traceback.format_exc()}")
    raise HTTPException(status_code=500, detail=error_msg)


@app.get("/search")
async def search_entries(
  query: str = Query(..., description="Search query"),
  limit: int = Query(10, description="Maximum number of results"),
  db: SupabaseManager = Depends(get_db),
):
  """Search entries in the database by text."""
  try:
    results = db.search_by_text(query, limit)
    return {"query": query, "results": results, "count": len(results)}
  except Exception as e:
    error_msg = f"Error searching entries: {str(e)}"
    logger.error(f"{error_msg}\n{traceback.format_exc()}")
    raise HTTPException(status_code=500, detail=error_msg)


@app.get("/vector-search")
async def vector_search(
  query: str = Query(..., description="Search query"),
  limit: int = Query(10, description="Maximum number of results"),
  search_type: str = Query("content", description="Type of search: 'content' or 'title'"),
  similarity_threshold: float = Query(0.3, description="Minimum similarity threshold (0-1)"),
  db: SupabaseManager = Depends(get_db),
):
  """
  Perform semantic search using vector embeddings.

  Args:
      query: Search query text
      limit: Maximum number of results to return
      search_type: Type of search ('content' or 'title')
      similarity_threshold: Minimum similarity threshold (0-1)

  Returns:
      List of articles matching the search query by semantic similarity
  """
  try:
    # Validate search_type
    if search_type not in ["content", "title"]:
      raise HTTPException(status_code=400, detail="search_type must be 'content' or 'title'")

    # Validate similarity_threshold
    if similarity_threshold < 0 or similarity_threshold > 1:
      raise HTTPException(status_code=400, detail="similarity_threshold must be between 0 and 1")

    # Perform vector search
    results = db.vector_search(query, limit=limit, search_type=search_type, similarity_threshold=similarity_threshold)

    return {"query": query, "search_type": search_type, "similarity_threshold": similarity_threshold, "results": results, "count": len(results)}
  except Exception as e:
    error_msg = f"Error in vector search: {str(e)}"
    logger.error(f"{error_msg}\n{traceback.format_exc()}")
    raise HTTPException(status_code=500, detail=error_msg)


class RegenerateEmbeddingsRequest(BaseModel):
  """Request model for regenerating embeddings."""

  limit: int = Field(10, description="Maximum number of articles to process")
  offset: int = Field(0, description="Offset for pagination")


@app.post("/regenerate-embeddings")
async def regenerate_embeddings(request: RegenerateEmbeddingsRequest, db: SupabaseManager = Depends(get_db)):
  """
  Regenerate embeddings for existing articles.

  Args:
      request: Request with limit and offset parameters

  Returns:
      Results of the regeneration process
  """
  try:
    # Regenerate embeddings
    results = db.regenerate_embeddings(limit=request.limit, offset=request.offset)

    return {"status": "success", "message": f"Processed {results.get('total_processed', 0)} articles", "results": results}
  except Exception as e:
    error_msg = f"Error regenerating embeddings: {str(e)}"
    logger.error(f"{error_msg}\n{traceback.format_exc()}")
    raise HTTPException(status_code=500, detail=error_msg)
