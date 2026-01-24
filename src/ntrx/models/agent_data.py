from pydantic import BaseModel, Field
from typing import Optional

class AgentData(BaseModel):
    """
    Represents the serializable state of an active Agent (Source or Client).
    """
    mountpoint: str = Field(..., description="The mountpoint this agent is connected to")
    real_ip: str = Field(..., description="The IP address of the agent")
    user_agent: str = Field("Unknown", description="User-Agent string")
    connected_at: float = Field(..., description="Timestamp of connection start")
    bytes_in: int = Field(0, description="Total bytes received")
    bytes_out: int = Field(0, description="Total bytes sent")
    bps_in: int = Field(0, description="Current incoming bits per second")
    bps_out: int = Field(0, description="Current outgoing bits per second")
    username: Optional[str] = Field(None, description="Username if authenticated")
