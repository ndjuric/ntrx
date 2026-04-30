#!/usr/bin/env python
import os
import json
from pathlib import Path
from dotenv import load_dotenv


class FS:
    def __init__(self):
        # 0. Load environment variables from .env if found in CWD or parents
        # This populates os.environ so os.getenv("NTRX_ROOT") works in _determine_root
        load_dotenv(override=True)

        # 1. Determine the root directory using a priority system
        self.project_root = self._determine_root()

        # 2. Re-load environment variables from the specific project root if needed
        # (Usually redundant but ensures we use the correct file for this instance)
        self.env_file = os.path.join(self.project_root, ".env")
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file, override=True)

        # 3. Allow overriding storage folder via environment variable
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
        # 1. Check if NTRX_ROOT is already in environment (e.g. set in shell)
        if os.getenv("NTRX_ROOT"):
            return os.path.abspath(os.getenv("NTRX_ROOT"))

        # 2. Search upwards from current working directory for indicators (.env or storage/)
        curr = Path.cwd()
        for p in [curr] + list(curr.parents):
            if (p / ".env").exists() or (p / "storage").exists():
                return str(p)

        # 3. Local Development fallback (relative to this file)
        # src/ntrx/vfs/fs.py -> parents[3] is the project root
        try:
            root_candidate = Path(__file__).resolve().parents[3]
            if (root_candidate / "src").exists():
                return str(root_candidate)
        except (IndexError, ValueError):
            pass

        # 4. Installed package default (User home directory: ~/.ntrx)
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
