#!/usr/bin/env python
import asyncio
from ntrx.vfs.fs import FS
from ntrx.ntrip.ntrip_caster import NtripCaster
import signal
from ntrx.logger.logger_setup import LoggerSetup

class NtripRunner:
    def __init__(self):
        self.logger = LoggerSetup.get_logger(__name__)
        self.logger.info("Initializing NTRIP server...")
        self.fs = FS()
        self.fs.ensure_directories()
        self.caster = NtripCaster(self.fs.ntripcaster_config_file)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.setup_signal_handlers()

    def shutdown(self) -> None:
        self.caster.logger.info("shutting down server...")
        for task in asyncio.all_tasks(self.loop):
            task.cancel()
        self.loop.stop()

    def setup_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(sig, self.shutdown)
    
    def run(self) -> None:
        try:
            self.loop.run_until_complete(self.caster.start_server())
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.loop.close()
            self.caster.logger.info("server shut down successfully")


if __name__ == "__main__":
    runner = NtripRunner()
    runner.run()
