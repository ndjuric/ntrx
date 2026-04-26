#!/usr/bin/env python
import os
import json
from pathlib import Path
from dotenv import load_dotenv


class FS:
    def __init__(self):
        # Determine the root directory using a priority system
        self.project_root = self._determine_root()

        # Load environment variables if .env exists
        self.env_file = os.path.join(self.project_root, ".env")
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file)

        # Allow overriding storage folder via environment variable
        env_storage = os.getenv("NTRX_STORAGE_DIR")
        if env_storage:
            self.storage_folder = os.path.abspath(env_storage)
        else:
            self.storage_folder = os.path.join(self.project_root, "storage")

        self.logs_folder = os.path.join(self.storage_folder, "logs")
        self.ntripcaster_log_file = os.path.join(self.logs_folder, "ntripcaster.log")
        self.ntripcaster_config_file = os.path.join(self.storage_folder, "ntripcaster.json")
        self.docker_compose_file = os.path.join(self.project_root, "docker-compose.yml")

        self.log_max_size_mb = int(os.getenv("LOG_MAX_SIZE_MB", 1))
        self.log_max_backup_count = int(os.getenv("LOG_MAX_BACKUP_COUNT", 5))

        self.ensure_directories()
        self.ensure_default_config()

    def _determine_root(self) -> str:
        """Determines the root path for configs and storage."""
        # 1. Environment Variable Override
        if os.getenv("NTRX_ROOT"):
            return os.path.abspath(os.getenv("NTRX_ROOT"))

        # 2. Local Development (Current Working Directory)
        # If we are running it from a folder that looks like our workspace, use it.
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, "storage")) or os.path.exists(os.path.join(cwd, ".env")):
            return cwd

        # 3. Installed package default (User home directory: ~/.ntrx)
        # Standard for global CLI tools
        home_dir = str(Path.home())
        default_dir = os.path.join(home_dir, ".ntrx")
        os.makedirs(default_dir, exist_ok=True)
        return default_dir

    def ensure_directories(self):
        os.makedirs(self.logs_folder, exist_ok=True)
        os.makedirs(self.storage_folder, exist_ok=True)

    def ensure_default_config(self):
        """Creates a default ntripcaster.json if it doesn't exist."""
        if not os.path.exists(self.ntripcaster_config_file):
            default_config = {
                "general": {
                    "port": 2101,
                    "max_clients": 100
                },
                "sources": {},
                "clients": {}
            }
            with open(self.ntripcaster_config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
