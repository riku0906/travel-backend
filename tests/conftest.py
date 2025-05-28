import pytest
import json
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
import datetime

from app.main import app
from app.routes.customers import get_customer_data_manager, CustomerDataManager

@pytest.fixture
def test_client():
    """TestClient fixture for making requests to the FastAPI app."""
    return TestClient(app)

def load_test_data(filename):
    """Load test data from a JSON file if it exists, otherwise return empty list."""
    test_data_path = os.path.join(os.path.dirname(__file__), "test_data", filename)
    print('test_data_path-->', test_data_path)
    try:
        with open(test_data_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: Could not load test data from {test_data_path}")
        return []

@pytest.fixture
def mock_customer_data_manager(monkeypatch):
    """Create a mock CustomerDataManager with predefined test data."""
    
    # Try to load test data from files, or use hardcoded data if files don't exist
    test_customers = load_test_data("customers.json") or [
        {
            "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+12345678901",
            "address": "123 Main St, City, Country",
            "created_at": str(datetime.datetime(2023, 1, 1)),
            "updated_at": str(datetime.datetime(2023, 1, 1)),
            "is_active": True
        },
        {
            "customer_id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
            "name": "Jane Smith",
            "email": "jane.smith@example.com",
            "phone": "+19876543210",
            "address": "456 Oak St, City, Country",
            "created_at": str(datetime.datetime(2023, 1, 2)),
            "updated_at": str(datetime.datetime(2023, 1, 2)),
            "is_active": True
        }
    ]
    
    test_bookings = load_test_data("bookings.json") or [
        {
            "booking_id": "5fa85f64-5717-4562-b3fc-2c963f66afa8",
            "customer_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "destination": "Paris, France",
            "start_date": "2023-06-15",
            "end_date": "2023-06-22",
            "status": "confirmed"
        }
    ]
    
    # Create a mock data manager
    mock_manager = Mock(spec=CustomerDataManager)
    
    # Configure the mock methods
    
    # get_all_customers returns all test customers
    mock_manager.get_all_customers.return_value = test_customers.copy()
    
    # get_customer_by_id returns a specific customer or None
    mock_manager.get_customer_by_id.side_effect = lambda customer_id: next(
        (c for c in test_customers if c["customer_id"] == str(customer_id)), 
        None
    )
    
    # check_email_exists checks if email exists
    mock_manager.check_email_exists.side_effect = lambda email, exclude_customer_id=None: any(
        c["email"].lower() == email.lower() and 
        (not exclude_customer_id or c["customer_id"] != str(exclude_customer_id)) 
        for c in test_customers
    )
    
    # add_customer simulates adding a customer
    def mock_add_customer(customer):
        test_customers.append(customer)
        return customer
    mock_manager.add_customer.side_effect = mock_add_customer
    
    # update_customer simulates updating a customer
    def mock_update_customer(customer_id, updated_data):
        for i, customer in enumerate(test_customers):
            if customer["customer_id"] == str(customer_id):
                for key, value in updated_data.items():
                    test_customers[i][key] = value
                return test_customers[i]
        return None
    mock_manager.update_customer.side_effect = mock_update_customer
    
    # hard_delete_customer simulates deleting a customer
    def mock_hard_delete_customer(customer_id):
        for i, customer in enumerate(test_customers):
            if customer["customer_id"] == str(customer_id):
                del test_customers[i]
                return True
        return False
    mock_manager.hard_delete_customer.side_effect = mock_hard_delete_customer
    
    # soft_delete_customer simulates soft deleting
    def mock_soft_delete_customer(customer_id):
        for i, customer in enumerate(test_customers):
            if customer["customer_id"] == str(customer_id):
                test_customers[i]["is_active"] = False
                test_customers[i]["deleted_at"] = str(datetime.datetime.now())
                return True
        return False
    mock_manager.soft_delete_customer.side_effect = mock_soft_delete_customer
    
    # get_customer_bookings returns bookings for a customer
    mock_manager.get_customer_bookings.side_effect = lambda customer_id: [
        b for b in test_bookings if b["customer_id"] == str(customer_id)
    ]
    
    # cascade_delete_customer simulates cascade delete
    def mock_cascade_delete_customer(customer_id):
        bookings = [b for b in test_bookings if b["customer_id"] == str(customer_id)]
        booking_ids = [b["booking_id"] for b in bookings]
        
        # Remove bookings
        for i in reversed(range(len(test_bookings))):
            if test_bookings[i]["customer_id"] == str(customer_id):
                del test_bookings[i]
        
        # Check if customer exists
        for i, customer in enumerate(test_customers):
            if customer["customer_id"] == str(customer_id):
                del test_customers[i]
                return {
                    "success": True,
                    "customer_id": str(customer_id),
                    "deleted_bookings": booking_ids,
                    "booking_count": len(booking_ids)
                }
                
        return {"success": False, "error": "Customer not found"}
    mock_manager.cascade_delete_customer.side_effect = mock_cascade_delete_customer
    
    # Override the dependency
    monkeypatch.setattr("app.routes.customers.get_customer_data_manager", lambda: mock_manager)
    
    return mock_manager