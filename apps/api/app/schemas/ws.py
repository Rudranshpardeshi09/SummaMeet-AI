from pydantic import BaseModel

class TicketResponse(BaseModel):
    ticket: str
    expires_in: int
