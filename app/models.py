from typing import Literal

from pydantic import BaseModel, Field

class JobDescription(BaseModel): 
    company: str
    title: str
    seniority: Literal["junior", "mid", "senior", "staff", "unknown"] = "unknown"
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    domain: str = ""