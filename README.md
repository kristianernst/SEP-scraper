# Stanford Encyclopedia of Philosophy (SEP) Scraper

A simple and efficient scraper for the Stanford Encyclopedia of Philosophy with Supabase integration and vector search capabilities.

## Features

- Scrape articles from the Stanford Encyclopedia of Philosophy
- Store article metadata and content in Supabase
- Markdown conversion for scraped content
- Vector search using OpenAI embeddings
- FastAPI endpoints for interacting with the scraper and database

## Requirements

- Python 3.8+
- Supabase account
- OpenAI API key (for embeddings)

## Installation

### 1. Clone the repository:
```bash
git clone <repository-url>
cd sep-scraper
```

### 2. Install the required packages:
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables:
Create a `.env` file with the following variables:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
OPENAI_API_KEY=your_openai_api_key
```

### 4. Database Setup

1. Log in to your Supabase dashboard at https://app.supabase.com
2. Open your project
3. Go to the SQL Editor tab
4. Create a new query
5. Copy and paste the contents of the `supabase_setup.sql` file into the query editor
6. Click "Run" to execute the SQL statements

This will:
- Enable the pgvector extension for vector embeddings
- Create the required tables with the correct schema
- Create the vector search function
- Set up indexes for faster vector searches

#### Verifying the Database Setup

To verify that the database is set up correctly:

1. In the Supabase dashboard, go to the Table Editor tab
2. You should see the following tables:
   - `entry_metadata`
   - `entry_content`

3. In the SQL Editor, run the following query to check if the vector search function exists:
   ```sql
   SELECT * FROM pg_proc WHERE proname = 'match_entries';
   ```
   
   If the function exists, you should see at least one row in the result.

#### Troubleshooting Database Setup

If you encounter errors:

1. Check that the pgvector extension is enabled in your Supabase project
2. Verify that you have admin rights to the database
3. Make sure your Supabase API key has the necessary permissions
4. Look at the error messages in the API logs or SQL Editor for specific details

### 5. Starting the API

Start the FastAPI server:
```bash
python simple_api.py
```

The API will be available at http://localhost:8010

## Docker Support

### Option 1: Using Docker Compose (Recommended)

1. Ensure your `.env` file contains the required environment variables:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   OPENAI_API_KEY=your_openai_api_key
   ```

2. Build and start the container:
   ```bash
   docker-compose up -d
   ```

3. Stop the container:
   ```bash
   docker-compose down
   ```

### Option 2: Using Docker Directly

1. Build the Docker image:
   ```bash
   docker build -t sep-scraper .
   ```

2. Run the container:
   ```bash
   docker run -p 8010:8010 \
     -e SUPABASE_URL=your_supabase_url \
     -e SUPABASE_KEY=your_supabase_key \
     -e OPENAI_API_KEY=your_openai_api_key \
     sep-scraper
   ```

### Accessing the API

Once the container is running, the API is available at:
```
http://localhost:8010
```

You can test it with:
```bash
curl http://localhost:8010/
```

## API Endpoints

### Scraping Endpoints

- `POST /scrape/{entry_id}` - Scrape an article by its entry ID or full URL
- `POST /scrape-url?url=<full-url>` - Scrape an article using a query parameter

### Data Access Endpoints

- `GET /entry?url=<full-url>` - Get an entry by URL
- `GET /entries` - List all entries
- `GET /search?query=<search_query>` - Text-based search

### Vector Search Endpoints

- `GET /vector-search?query=<search_query>&limit=10&search_type=content&similarity_threshold=0.3` - Perform semantic search
- `POST /regenerate-embeddings` - Regenerate embeddings for existing articles

## Usage Examples

### Scrape an article

```bash
# By entry ID
curl -X POST "http://localhost:8010/scrape/kant"

# By full URL
curl -X POST "http://localhost:8010/scrape/https://plato.stanford.edu/entries/kant/"
```

### Vector search

```bash
# Basic vector search
curl -X GET "http://localhost:8010/vector-search?query=categorical%20imperative&limit=5"

# With custom parameters
curl -X GET "http://localhost:8010/vector-search?query=categorical%20imperative&limit=5&search_type=content&similarity_threshold=0.2"
```

### Regenerate embeddings

```bash
curl -X POST "http://localhost:8010/regenerate-embeddings" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "offset": 0}'
```

## Implementation Details

### Architecture

- `simple_scraper.py` - Core scraper functionality
- `supabase_client.py` - Supabase database manager
- `simple_api.py` - FastAPI server
- `embeddings.py` - OpenAI embeddings generation

### Vector Search

The system uses OpenAI's embeddings to convert article text into vectors for semantic search. These embeddings are stored in the Supabase database and can be searched using the vector_search endpoint.

Vector search allows for finding articles that are semantically similar to a query, rather than just matching keywords.
