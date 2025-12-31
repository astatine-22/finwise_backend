"""
Gunicorn Configuration for Production Deployment
================================================
This configuration file is used when deploying to cloud platforms
like Render, Railway, Heroku, etc.

Usage:
    gunicorn -c gunicorn_conf.py main:app
"""

import os
import multiprocessing

# =============================================================================
# SERVER SOCKET BINDING
# =============================================================================
# Bind to 0.0.0.0 to accept connections from any network interface
# Port is read from environment variable (cloud providers set this automatically)
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"

# =============================================================================
# WORKER CONFIGURATION
# =============================================================================
# Use uvicorn workers for ASGI support with FastAPI
worker_class = "uvicorn.workers.UvicornWorker"

# Number of worker processes
# For cloud platforms, use 2-4 workers depending on your plan
# Formula: 2 * CPU cores + 1 (but capped for free/starter tier instances)
workers = int(os.getenv("WEB_CONCURRENCY", 2))

# Number of threads per worker
threads = 2

# Maximum number of pending connections
backlog = 2048

# =============================================================================
# WORKER LIFECYCLE
# =============================================================================
# Workers silent for more than this many seconds are killed and restarted
timeout = 120

# How long to wait for workers to finish serving during graceful shutdown
graceful_timeout = 30

# Time to wait between sending SIGTERM and SIGKILL during restart
kill_timeout = 5

# =============================================================================
# LOGGING
# =============================================================================
# Access log - log all incoming requests
accesslog = "-"  # Log to stdout

# Error log - log errors and warnings
errorlog = "-"  # Log to stderr

# Log level
loglevel = os.getenv("LOG_LEVEL", "info")

# =============================================================================
# PERFORMANCE TUNING
# =============================================================================
# Maximum requests a worker will process before restarting
# Helps prevent memory leaks from impacting the server
max_requests = 1000

# Add some variance to max_requests to prevent all workers restarting at once
max_requests_jitter = 50

# Keep-alive timeout (seconds)
keepalive = 5

# =============================================================================
# SECURITY
# =============================================================================
# Limit the allowed size of an incoming HTTP request's line
limit_request_line = 4094

# Limit the number of headers in a request
limit_request_fields = 100

# Limit the allowed size of an HTTP request header field
limit_request_field_size = 8190
