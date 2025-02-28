import os
import logging
import traceback
from typing import List, Dict, Any, Optional, Union
import time
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Configure OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Use the embeddings model (change as needed)
EMBEDDINGS_MODEL = "text-embedding-3-small"
# Default dimensions for the embeddings model (1536 for most OpenAI models)
EMBEDDING_DIMENSIONS = 1536


def generate_embedding(text: str, model: str = EMBEDDINGS_MODEL, max_retries: int = 3) -> Optional[List[float]]:
  """
  Generate embeddings for text using OpenAI's API.

  Args:
      text: The text to generate embeddings for
      model: The OpenAI model to use
      max_retries: Maximum number of retries on failure

  Returns:
      List of floating point values representing the embedding vector, or None if generation failed
  """
  if not text or not text.strip():
    logger.warning("Empty text provided for embedding generation")
    return None

  if not openai.api_key:
    logger.error("OpenAI API key not found in environment variables")
    return None

  # Limit text length to avoid token limits (typically ~8k tokens for embeddings models)
  # Truncate to approximately 5000 tokens to be safe
  text = text[:20000]

  for attempt in range(max_retries):
    try:
      response = openai.embeddings.create(model=model, input=text)

      # Extract the embedding from the response
      embedding = response.data[0].embedding
      logger.info(f"Successfully generated embedding of dimension {len(embedding)}")
      return embedding

    except Exception as e:
      logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to generate embedding: {str(e)}")
      if attempt < max_retries - 1:
        # Exponential backoff
        time.sleep(2**attempt)
      else:
        logger.error(f"Failed to generate embedding after {max_retries} attempts:\n{traceback.format_exc()}")
        return None


def generate_article_embeddings(title: str, content: str) -> Dict[str, Any]:
  """
  Generate embeddings for an article's title and content.

  Args:
      title: The article title
      content: The article content (markdown)

  Returns:
      Dictionary with title_embedding and content_embedding
  """
  result = {}

  # Generate embeddings for title
  title_embedding = generate_embedding(title)
  if title_embedding:
    result["title_embedding"] = title_embedding

  # Generate embeddings for content
  content_embedding = generate_embedding(content)
  if content_embedding:
    result["content_embedding"] = content_embedding

  return result
