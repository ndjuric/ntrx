#!/usr/bin/env python
import gzip
import logging.handlers
import os
import shutil
from ntrx.logger.logger_setup import LoggerSetup


class GZipRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def doRollover(self) -> None:
        try:
            if self.stream:
                self.stream.close()
                self.stream = None

            for i in range(self.backupCount - 1, 0, -1):
                src = f"{self.baseFilename}.{i}.gz"
                dst = f"{self.baseFilename}.{i+1}.gz"
                if os.path.exists(src):
                    os.replace(src, dst)

            dfn = f"{self.baseFilename}.1"
            if os.path.exists(self.baseFilename):
                os.replace(self.baseFilename, dfn)
                with open(dfn, "rb") as src_file, gzip.open(dfn + ".gz", "wb") as dst_file:
                    shutil.copyfileobj(src_file, dst_file)
                os.remove(dfn)

            self.mode = "a"
            self.stream = self._open()
        except Exception as e:
            LoggerSetup.get_logger(__name__).exception(
                "Error during log rollover",
                extra={"baseFilename": self.baseFilename}
            )
