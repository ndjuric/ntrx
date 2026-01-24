from pydantic import BaseModel, Field

class ClientPosition(BaseModel):
    """
    Represents a client's geographical position update.
    Published to 'ntrip:positions' Redis channel.
    """
    username: str = Field(..., description="The username of the client")
    nmea: str = Field(..., description="The raw NMEA GPGGA string")
    timestamp: float = Field(..., description="Unix timestamp of the position receipt")
