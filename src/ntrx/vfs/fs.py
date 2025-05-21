#!/usr/bin/env python
import os
from dotenv import load_dotenv


class FS:
    def __init__(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self.env_file = os.path.join(self.project_root, ".env")
        load_dotenv(self.env_file)

        self.storage_folder = os.path.join(self.project_root, "storage")
        self.logs_folder = os.path.join(self.storage_folder, "logs")
        self.ntripcaster_log_file = os.path.join(self.logs_folder, "ntripcaster.log")
        self.ntripcaster_config_file = os.path.join(self.storage_folder, "ntripcaster.json")

        self.log_max_size_mb = int(os.getenv("LOG_MAX_SIZE_MB", 1))
        self.log_max_backup_count = int(os.getenv("LOG_MAX_BACKUP_COUNT", 5))

        self.ensure_directories()

    def ensure_directories(self):
        os.makedirs(self.logs_folder, exist_ok=True)
        os.makedirs(self.storage_folder, exist_ok=True)
