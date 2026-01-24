from pydantic import BaseModel, Field
from typing import Dict, List
from ntrx.models.agent_data import AgentData

class CasterState(BaseModel):
    """
    Represents the complete state of the NTRIP Caster at a point in time.
    Stored in 'ntripcaster_state' Redis key.
    """
    sources: Dict[str, AgentData] = Field(..., description="Active sources keyed by mountpoint")
    clients: Dict[str, List[AgentData]] = Field(..., description="Active clients keyed by mountpoint")
