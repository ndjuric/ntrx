#!/usr/bin/env python
"""Rotating file handler with gzip compression for old logs."""
import gzip
import logging.handlers
import os
import shutil

class GZipRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that compresses old logs and keeps limited backups."""

    def doRollover(self) -> None:
        try:
            if self.stream:
                self.stream.close()
                self.stream = None

            # Rotate existing gzipped log files
            for i in range(self.backupCount - 1, 0, -1):
                src = f"{self.baseFilename}.{i}.gz"
                dst = f"{self.baseFilename}.{i+1}.gz"
                if os.path.exists(src):
                    os.replace(src, dst)

            # Rotate current log file
            dfn = f"{self.baseFilename}.1"
            if os.path.exists(self.baseFilename):
                os.replace(self.baseFilename, dfn)
                # Compress the rotated log
                with open(dfn, "rb") as src_file, gzip.open(dfn + ".gz", "wb") as dst_file:
                    shutil.copyfileobj(src_file, dst_file)
                os.remove(dfn)

            # Reopen the log file
            self.mode = "a"
            self.stream = self._open()
        except Exception as e:
            try:
                from ntrx.logger.logger_setup import LoggerSetup
                LoggerSetup.get_logger(__name__).exception("Error during log rollover")
            except Exception:
                print(f"[LogRollover] Rollover failed: {e}")