from pydantic import BaseModel
from typing import List, Dict, Optional

class FinancialGoalsUpdateRequest(BaseModel):
    goals: Dict

class FinancialTrendItem(BaseModel):
    month: str
    income: float
    expenses: float
    savings: float
    top_category: Optional[str]

class FinancialTrendsResponse(BaseModel):
    user_id: str
    trends: List[FinancialTrendItem]

class GoalsPayload(BaseModel):
    goals: dict