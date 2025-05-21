#!/usr/bin/env python
"""Logging setup and configuration class."""
import logging
import logging.config
from ntrx.vfs.fs import FS


class LoggerSetup:
    _is_configured = False

    @classmethod
    def configure_logging(cls) -> None:
        if cls._is_configured:
            return
        try:
            fs = FS()
            log_path = fs.ntripcaster_log_file
            max_bytes = int(fs.log_max_size_mb * 1024 * 1024)
            backup_count = int(fs.log_max_backup_count)

            config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "standard": {
                        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                    }
                },
                "handlers": {
                    "file": {
                        "class": "ntrx.logger.gzip_rotating_file_handler.GZipRotatingFileHandler",
                        "level": "DEBUG",
                        "formatter": "standard",
                        "filename": str(log_path),
                        "mode": "a",
                        "maxBytes": max_bytes,
                        "backupCount": backup_count
                    },
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG",
                        "formatter": "standard",
                        "stream": "ext://sys.stdout"
                    }
                },
                "root": {
                    "level": "DEBUG",
                    "handlers": ["file", "console"]
                }
            }
            logging.config.dictConfig(config)
            cls._is_configured = True
        except Exception as e:
            # Nemoj logovanje ovde — to izaziva kružni pakao
            print(f"[LoggerSetup] Failed to configure logging: {e}")

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        try:
            cls.configure_logging()
            return logging.getLogger(name)
        except Exception:
            # Fallback logger bez dodataka
            return logging.getLogger("fallback")
