import asyncio
from ntrx.logger.logger_setup import LoggerSetup
from ntrx.vfs.fs import FS
from ntrx.ntripclient.config import NtripClientConfig
from ntrx.ntripclient.ntrip_client import NtripClient

class ClientRunner:
    logger = LoggerSetup.get_logger(__qualname__)

    def __init__(self):
        self.fs = FS()

    def run(self) -> None:
        try:
            config = NtripClientConfig()
            client = NtripClient(config=config)
            asyncio.run(client.run())
        except KeyboardInterrupt:
            self.logger.info("NtripClient stopped by user.")
        except Exception as e:
            self.logger.error(f"NtripClient failed: {e}")
