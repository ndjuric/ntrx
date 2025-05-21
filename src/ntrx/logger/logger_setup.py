#!/usr/bin/env python
"""Logging setup and configuration class."""
import logging
import logging.config
from vfs.fs import FS
from gzip_rotating_file_handler import GZipRotatingFileHandler


class LoggerSetup:
    """Class to encapsulate logging configuration and logger retrieval."""

    _is_configured = False

    @classmethod
    def configure_logging(cls) -> None:
        """Configure logging with rotating file handler and stdout console."""
        if cls._is_configured:
            return
        try:
            fs = FS()
            log_path = fs.log_file
            max_bytes = int(fs.log_max_size_mb * 1024 * 1024)
            backup_count = int(fs.log_max_backup_count)

            config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "standard": {
                        "format": "%(asctime)s %(levelname)s %(name)s: %(message)s"
                    }
                },
                "handlers": {
                    "file": {
                        "class": "gzip_rotating_file_handler.GZipRotatingFileHandler",
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
            cls.get_logger(__name__).exception("Failed to configure logging", extra={})

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a logger by name, ensuring logging is configured."""
        try:
            cls.configure_logging()
            return logging.getLogger(name)
        except Exception as e:
            fallback_logger = logging.getLogger(name)
            fallback_logger.exception(
                "Failed to get logger, returning fallback",
                extra={"name": name}
            )
            return fallback_logger
