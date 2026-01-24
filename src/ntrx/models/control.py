from pydantic import BaseModel, Field
from typing import Literal

class ControlCommand(BaseModel):
    """
    Represents an administrative control command.
    Received from 'ntrip:control' Redis channel.
    """
    action: Literal["kill"] = Field(..., description="The action to perform")
    username: str = Field(..., description="The target username for the action")
