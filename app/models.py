from datetime import datetime
from pydantic import BaseModel
from pydantic import Field


class NewsArticle(BaseModel):
    score: int = 0
    title: str
    url: str
    summary: str
    published: datetime
    source: str
    category: str = "general"
    hebrew_title: str = ""
    hebrew_source: str = ""
    hebrew_summary: str = ""
    actionable_takeaway_he: str = ""
    term_explanations: dict[str, str] = Field(default_factory=dict)