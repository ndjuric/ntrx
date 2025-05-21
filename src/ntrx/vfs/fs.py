#!/usr/bin/env python
import os
from dataclasses import dataclass, field


@dataclass
class FS:
    cwd: str = field(default_factory=lambda: os.path.dirname(os.path.abspath(__file__)))
    storage_folder: str = field(init=False)
    env_file: str = field(init=False)
    logs_folder: str = field(init=False)
    ntripcaster_log_file: str = field(init=False)
    ntripcaster_config_file: str = field(init=False)

    def __post_init__(self):
        self.storage_folder = os.path.abspath(f"{self.cwd}/../storage")
        self.env_file = os.path.abspath(f"{self.cwd}/../.env")
        self.logs_folder = f"{self.storage_folder}/logs"
        self.ntripcaster_log_file = f"{self.logs_folder}/ntripcaster.log"
        self.ntripcaster_config_file = f"{self.storage_folder}/ntripcaster.json"

    def ensure_storage_folder(self):
        if not os.path.exists(self.storage_folder):
            os.makedirs(self.storage_folder)

    def read_by_line(self, file_path):
        with open(file_path, 'r') as fh:
            for line in fh:
                yield line.strip()
