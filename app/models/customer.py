# app/models/customer.py
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
import re

class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Customer's full name")
    email: EmailStr = Field(..., description="Customer's email address")
    phone: Optional[str] = Field(None, description="Customer's phone number")
    address: Optional[str] = Field(None, max_length=200, description="Customer's address")
    
    @validator('phone')
    def phone_validation(cls, v):
        if v is None:
            return v
        # Basic phone validation - can be adjusted based on requirements
        pattern = r'^\+?[0-9]{10,15}$'
        if not re.match(pattern, v):
            raise ValueError('Phone number must be 10-15 digits, with optional + prefix')
        return v

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    
    @validator('phone')
    def phone_validation(cls, v):
        if v is None:
            return v
        # Basic phone validation - can be adjusted based on requirements
        pattern = r'^\+?[0-9]{10,15}$'
        if not re.match(pattern, v):
            raise ValueError('Phone number must be 10-15 digits, with optional + prefix')
        return v

class Customer(CustomerBase):
    customer_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the customer")
    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp when customer was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="Timestamp when customer was last updated")

    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "+12345678901",
                "address": "123 Main St, City, Country",
                "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00"
            }
        }
        orm_mode = True