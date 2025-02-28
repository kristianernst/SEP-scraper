FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8010
ENV PYTHONUNBUFFERED=1

EXPOSE 8010

CMD ["uvicorn", "simple_api:app", "--host", "0.0.0.0", "--port", "8010"] 