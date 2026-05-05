import os
from pydantic import BaseModel, Field

class NtripClientConfig(BaseModel):
    caster_host: str = Field(default_factory=lambda: os.getenv("NTRIPCLIENT_CASTER_HOST", "127.0.0.1"))
    caster_port: int = Field(default_factory=lambda: int(os.getenv("NTRIPCLIENT_CASTER_PORT", "2101")))
    mountpoint: str = Field(default_factory=lambda: os.getenv("NTRIPCLIENT_MOUNTPOINT", "TESTMOUNT"))
    username: str = Field(default_factory=lambda: os.getenv("NTRIPCLIENT_USERNAME", "test3"))
    password: str = Field(default_factory=lambda: os.getenv("NTRIPCLIENT_PASSWORD", "*"))
    serial_port: str = Field(default_factory=lambda: os.getenv("NTRIPCLIENT_SERIAL_PORT", "/dev/ttyACM0"))
    baudrate: int = Field(default_factory=lambda: int(os.getenv("NTRIPCLIENT_BAUDRATE", "115200")))
    user_agent: str = Field(default_factory=lambda: os.getenv("NTRIPCLIENT_USER_AGENT", "NTRX-DevClient/1.0"))
    reconnect_delay: int = Field(default_factory=lambda: int(os.getenv("NTRIPCLIENT_RECONNECT_DELAY", "5")))
