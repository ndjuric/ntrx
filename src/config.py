#!/usr/bin/env python
import os
from dotenv import load_dotenv
from vfs.fs import FS

fs = FS()
load_dotenv(fs.env_file)

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "changeme")

# FastAPI configuration
FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
FASTAPI_PORT = os.getenv("FASTAPI_PORT", "8000")