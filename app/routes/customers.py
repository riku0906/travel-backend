from functools import lru_cache
import json
import os
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Optional
from uuid import UUID, uuid4
import datetime
import re
from enum import Enum
from typing import Optional

from app.models.customer import Customer, CustomerCreate, CustomerUpdate

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    responses={
        404: {"description": "Not found"},
        400: {"description": "Bad Request"}
    },
)

DATA_FILE = os.path.join(os.path.dirname(__file__), "../data/customers.json")

class CustomerDataManager:
    def __init__(self, data_file):
        self.data_file = data_file
        self._ensure_data_file_exists()
        self._customer_index = {}
        self._build_customer_index()
    
    def _ensure_data_file_exists(self):
        if not os.path.exists(self.data_file):
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w") as f:
                json.dump([], f)
    
    def _build_customer_index(self):
        customers = self._load_raw_customers()
        self._customer_index = {
            customer["customer_id"]: customer 
            for customer in customers
        }
    
    def _load_raw_customers(self):
        try:
            with open(self.data_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    
    def get_all_customers(self) -> List[Dict]:
        return list(self._customer_index.values())
    
    def get_customer_by_id(self, customer_id: UUID) -> Optional[Dict]:
        return self._customer_index.get(str(customer_id))
    
    def add_customer(self, customer: Dict):
        customers = self._load_raw_customers()
        customers.append(customer)
        self._save_customers(customers)
        self._customer_index[customer["customer_id"]] = customer
    
    def update_customer(self, customer_id: UUID, updated_data: Dict) -> Optional[Dict]:
        customers = self._load_raw_customers()
        for i, customer in enumerate(customers):
            if customer["customer_id"] == str(customer_id):
                for key, value in updated_data.items():
                    customer[key] = value
                customers[i] = customer
                self._save_customers(customers)
                self._customer_index[str(customer_id)] = customer
                return customer
        return None
    
    def delete_customer(self, customer_id: UUID) -> bool:
        customers = self._load_raw_customers()
        original_count = len(customers)
        customers = [c for c in customers if c["customer_id"] != str(customer_id)]
        if len(customers) == original_count:
            return False
        self._save_customers(customers)
        if str(customer_id) in self._customer_index:
            del self._customer_index[str(customer_id)]
        return True
    
    def check_email_exists(self, email: str, exclude_customer_id: Optional[UUID] = None) -> bool:
        normalized_email = email.lower()
        for customer_id, customer in self._customer_index.items():
            if customer["email"].lower() == normalized_email:
                if exclude_customer_id and str(exclude_customer_id) == customer_id:
                    continue
                return True
        return False

    def _save_customers(self, customers: List[Dict]):
        with open(self.data_file, "w") as f:
            json.dump(customers, f, default=str)

    def get_customer_bookings(self, customer_id: UUID) -> List[Dict]:
        """
        Check if customer has any associated bookings
        
        In a real system, this would query the bookings table/collection.
        For our mock implementation, we'll read from the bookings.json file.
        """
        booking_file = os.path.join(os.path.dirname(self.data_file), "../data/bookings.json")
        
        if not os.path.exists(booking_file):
            return []
            
        try:
            with open(booking_file, "r") as f:
                bookings = json.load(f)
                return [b for b in bookings if b.get("customer_id") == str(customer_id)]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def soft_delete_customer(self, customer_id: UUID) -> bool:
        """Mark a customer as inactive rather than removing them"""
        customer = self.get_customer_by_id(customer_id)
        if not customer:
            return False
            
        # Add inactive flag and record deletion time
        customer["is_active"] = False
        customer["deleted_at"] = str(datetime.datetime.now())
        
        # Update the customer in the database
        return self.update_customer(customer_id, customer) is not None
    
    def hard_delete_customer(self, customer_id: UUID) -> bool:
        """
        Permanently remove customer from database.
        Same as the original delete_customer method.
        """
        customers = self._load_raw_customers()
        original_count = len(customers)
        
        customers = [c for c in customers if c["customer_id"] != str(customer_id)]
        
        if len(customers) == original_count:
            return False
        
        self._save_customers(customers)
        if str(customer_id) in self._customer_index:
            del self._customer_index[str(customer_id)]
        return True
    
    def cascade_delete_customer(self, customer_id: UUID) -> Dict:
        """
        Delete customer and all their associated bookings.
        Returns a summary of what was deleted.
        """
        # Get related bookings
        bookings = self.get_customer_bookings(customer_id)
        
        # If the customer doesn't exist, return early
        if not self.get_customer_by_id(customer_id):
            return {"success": False, "error": "Customer not found"}
            
        # Delete related bookings
        booking_file = os.path.join(os.path.dirname(self.data_file), "../data/bookings.json")
        deleted_bookings = []
        
        if bookings and os.path.exists(booking_file):
            try:
                with open(booking_file, "r") as f:
                    all_bookings = json.load(f)
                
                for booking in bookings:
                    deleted_bookings.append(booking.get("booking_id"))
                
                # Filter out the customer's bookings
                remaining_bookings = [b for b in all_bookings if b.get("customer_id") != str(customer_id)]
                
                # Save updated bookings
                with open(booking_file, "w") as f:
                    json.dump(remaining_bookings, f, default=str)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        # Delete the customer
        success = self.hard_delete_customer(customer_id)
        
        # Return summary
        return {
            "success": success,
            "customer_id": str(customer_id),
            "deleted_bookings": deleted_bookings,
            "booking_count": len(deleted_bookings)
        }

@lru_cache
def get_customer_data_manager():
    return CustomerDataManager(DATA_FILE)

@router.get("/", response_model=List[Customer])
async def get_customers(data_manager: CustomerDataManager = Depends(get_customer_data_manager)):
    return data_manager.get_all_customers()

@router.get("/{customer_id}", response_model=Customer)
async def get_customer(
    customer_id: UUID, 
    data_manager: CustomerDataManager = Depends(get_customer_data_manager)
):
    customer = data_manager.get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found"
        )
    return customer

@router.post("/", response_model=Customer, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer: CustomerCreate,
    data_manager: CustomerDataManager = Depends(get_customer_data_manager)
):
    if data_manager.check_email_exists(customer.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email address '{customer.email}' is already in use (note: email comparison is case-insensitive)"
        )
    
    new_customer = Customer(
        **customer.dict(),
        customer_id=uuid4(),
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now()
    )
    
    data_manager.add_customer(new_customer.dict())
    return new_customer

@router.put("/{customer_id}", response_model=Customer)
async def update_customer(
    customer_id: UUID, 
    customer_update: CustomerUpdate,
    data_manager: CustomerDataManager = Depends(get_customer_data_manager)
):
    existing_customer = data_manager.get_customer_by_id(customer_id)
    if not existing_customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found"
        )
    
    update_data = customer_update.dict(exclude_unset=True)
    if not update_data:
        available_fields = ", ".join(CustomerUpdate.__fields__.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Update request must include at least one field to modify",
                "available_fields": available_fields,
                "provided": "No fields were provided in the request body"
            }
        )
    
    validation_errors = {}

    if "email" in update_data:
        email = update_data["email"]
        if existing_customer["email"].lower() != email.lower():
            if data_manager.check_email_exists(email, exclude_customer_id=customer_id):
                validation_errors["email"] = f"Email address '{email}' is already in use by another customer"

    if "phone" in update_data and update_data["phone"] is not None:
        phone = update_data["phone"]
        phone_pattern = r'^\+?[0-9]{10,15}$'
        if not re.match(phone_pattern, phone):
            validation_errors["phone"] = f"Invalid phone number format: '{phone}'. Must be 10-15 digits with optional + prefix"

    if "name" in update_data and update_data["name"] is not None:
        name = update_data["name"]
        if len(name.strip()) < 1:
            validation_errors["name"] = "Name cannot be empty"
        elif len(name) > 100:
            validation_errors["name"] = f"Name exceeds maximum length of 100 characters (provided: {len(name)})"

    if "address" in update_data and update_data["address"] is not None:
        address = update_data["address"]
        if len(address) > 200:
            validation_errors["address"] = f"Address exceeds maximum length of 200 characters (provided: {len(address)})"

    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Validation error",
                "errors": validation_errors,
                "fields_provided": list(update_data.keys())
            }
        )

    update_data["updated_at"] = str(datetime.datetime.now())
    updated_customer = data_manager.update_customer(customer_id, update_data)
    return updated_customer

class DeleteType(str, Enum):
    SOFT = "soft"
    HARD = "hard"
    CASCADE = "cascade"

@router.delete("/{customer_id}", 
               status_code=status.HTTP_200_OK,  # Changed from 204 to return content
               response_model=Dict)
async def delete_customer(
    customer_id: UUID,
    delete_type: DeleteType = DeleteType.SOFT,  # Default to soft delete
    force: bool = False,                        # Force option to override safety checks
    data_manager: CustomerDataManager = Depends(get_customer_data_manager)
):
    # First check if the customer exists
    customer = data_manager.get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found"
        )
    
    # Check for related bookings
    bookings = data_manager.get_customer_bookings(customer_id)
    
    # Handle based on delete type and whether there are bookings
    if bookings and not force and delete_type != DeleteType.SOFT:
        # The customer has bookings and we're not doing a soft delete or forcing hard delete
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Customer with ID {customer_id} has {len(bookings)} "
                          f"existing bookings. Cannot perform {delete_type} delete.",
                "booking_count": len(bookings),
                "options": [
                    "Use delete_type=soft to mark the customer as inactive but keep records",
                    "Add force=true parameter to override and perform the requested delete type",
                    f"Delete the customer's bookings first, then delete the customer"
                ]
            }
        )
    
    # Execute the appropriate delete operation
    if delete_type == DeleteType.SOFT:
        success = data_manager.soft_delete_customer(customer_id)
        return {
            "success": success,
            "delete_type": "soft",
            "customer_id": str(customer_id),
            "message": "Customer has been marked as inactive"
        }
        
    elif delete_type == DeleteType.CASCADE:
        result = data_manager.cascade_delete_customer(customer_id)
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "Customer could not be deleted")
            )
        return {
            **result,
            "delete_type": "cascade",
            "message": f"Customer and {result['booking_count']} associated bookings have been deleted"
        }
        
    else:  # HARD delete
        success = data_manager.hard_delete_customer(customer_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete customer for unknown reason"
            )
        return {
            "success": True,
            "delete_type": "hard",
            "customer_id": str(customer_id),
            "message": "Customer has been permanently deleted"
        }