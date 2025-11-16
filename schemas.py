"""
Database Schemas for WonderLens Chronicles

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# -----------------------------
# Core domain schemas
# -----------------------------

class User(BaseModel):
    display_name: str = Field(..., description="Public display name")
    email: str = Field(..., description="Unique email address")
    auth_provider: Literal["password", "google", "apple", "anonymous"] = "anonymous"
    auth_uid: Optional[str] = Field(None, description="UID from auth provider")
    stage: Literal["Awakening", "Healing", "Embodiment", "Manifestation", "Communion"] = "Awakening"
    locale: Literal["en", "sw", "yo", "am"] = "en"
    avatar_url: Optional[str] = None
    premium_tier: Literal["free", "premium", "master"] = "free"

class JournalEntry(BaseModel):
    user_id: str = Field(..., description="User's id")
    content: str = Field(..., description="Journal text content")
    mood: Optional[str] = Field(None, description="User reported mood")
    audio_url: Optional[str] = Field(None, description="Uploaded voice URL if any")
    sentiment: Optional[str] = Field(None, description="Detected sentiment label")
    theme: Optional[str] = Field(None, description="Detected dominant theme/keyword")

class Mantra(BaseModel):
    user_id: str
    text: str
    meaning: Optional[str] = None
    stage: Optional[str] = None
    mood: Optional[str] = None
    journal_theme: Optional[str] = None
    date: Optional[str] = Field(None, description="YYYY-MM-DD")

class OracleConsult(BaseModel):
    user_id: Optional[str] = None
    prompt: str
    interpretation: Optional[str] = None
    references: Optional[List[str]] = None

class MeditationSession(BaseModel):
    user_id: str
    environment: Literal["forest", "mt_kenya", "desert_temple"] = "forest"
    duration_minutes: int = 10
    started_at: Optional[datetime] = None
    completed: bool = False

class Lesson(BaseModel):
    slug: str
    title: str
    body: str
    badge: Optional[Literal["Initiate", "Seer", "Sage"]] = None

class Payment(BaseModel):
    user_id: str
    provider: Literal["stripe", "mpesa", "paypal"]
    amount_cents: int
    currency: str = "USD"
    status: Literal["pending", "succeeded", "failed"] = "pending"
    reference: Optional[str] = None

# Note: The database helper and viewer will use these models for validation.
