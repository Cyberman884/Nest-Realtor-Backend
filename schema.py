from pydantic import BaseModel
from typing import List, Optional

class Budget(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None

class AIResolvedQuery(BaseModel):
    lead_type: str
    location: str
    property_type: Optional[str] = "house"
    budget: Budget
    sources: List[str]
