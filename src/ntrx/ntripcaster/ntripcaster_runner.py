#!/usr/bin/env python
import asyncio
from ntrx.vfs.fs import FS
from ntrx.ntripcaster.ntripcaster import NtripCaster
import signal
from ntrx.logger.logger_setup import LoggerSetup

class NtripRunner:
    logger = LoggerSetup.get_logger(__qualname__)

    def __init__(self):
        self.logger.info("Initializing NTRIP server...")
        self.fs = FS()
        self.fs.ensure_directories()
        
        try:
            import json
            with open(self.fs.ntripcaster_config_file, "r") as f:
                config_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            config_data = {}
            
        import os
        has_docker = os.path.exists(self.fs.docker_compose_file)
        
        self.caster = NtripCaster(config=config_data, has_docker_compose=has_docker)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.setup_signal_handlers()

    def shutdown(self) -> None:
        self.caster.logger.info("shutting down server...")
        for task in asyncio.all_tasks(self.loop):
            task.cancel()

    def setup_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(sig, self.shutdown)
    
    def run(self) -> None:
        try:
            self.loop.run_until_complete(self.caster.start_server())
        except asyncio.CancelledError:
            pass
        except (KeyboardInterrupt, SystemExit, RuntimeError):
            pass
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                
            self.loop.close()
            self.caster.logger.info("server shut down successfully")


if __name__ == "__main__":
    runner = NtripRunner()
    runner.run()
