# app/models/destination.py
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID, uuid4
from enum import Enum

class PriceRange(str, Enum):
    BUDGET = "budget"
    MODERATE = "moderate"
    LUXURY = "luxury"
    ULTRA_LUXURY = "ultra_luxury"

class Destination(BaseModel):
    destination_id: UUID = Field(default_factory=uuid4)
    name: str
    location: str
    description: str
    price_range: PriceRange
    availability: bool = True
    
    class Config:
        schema_extra = {
            "example": {
                "destination_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "name": "Paris",
                "location": "France",
                "description": "The City of Light featuring iconic landmarks like the Eiffel Tower and world-class cuisine.",
                "price_range": "moderate",
                "availability": True
            }
        }

class DestinationCreate(BaseModel):
    name: str
    location: str
    description: str
    price_range: PriceRange
    availability: bool = True
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Paris",
                "location": "France",
                "description": "The City of Light featuring iconic landmarks like the Eiffel Tower and world-class cuisine.",
                "price_range": "moderate",
                "availability": True
            }
        }

class DestinationUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    price_range: Optional[PriceRange] = None
    availability: Optional[bool] = None
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Paris",
                "description": "The updated description of the City of Light.",
                "price_range": "luxury"
            }
        }

# Add the PaginatedDestinations model here
class PaginatedDestinations(BaseModel):
    items: List[Destination]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next_page: bool
    has_prev_page: bool
    
    class Config:
        schema_extra = {
            "example": {
                "items": [
                    {
                        "destination_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "name": "Paris",
                        "location": "France",
                        "description": "The City of Light featuring iconic landmarks like the Eiffel Tower and world-class cuisine.",
                        "price_range": "moderate",
                        "availability": True
                    }
                ],
                "total_count": 1,
                "page": 1,
                "page_size": 20,
                "total_pages": 1,
                "has_next_page": False,
                "has_prev_page": False
            }
        }