import pytest
from fastapi import status
from uuid import uuid4

# TEST: GET /api/v1/customers/
def test_get_all_customers(test_client, mock_customer_data_manager):
    """Test retrieving all customers"""
    response = test_client.get("/api/v1/customers/")
    
    assert response.status_code == status.HTTP_200_OK
    customers = response.json()
    assert len(customers) >= 2  # We have at least our two test customers
    assert "John Doe" in [customer["name"] for customer in customers]
    assert "Jane Smith" in [customer["name"] for customer in customers]

# TEST: GET /api/v1/customers/{customer_id}
def test_get_customer_by_id(test_client, mock_customer_data_manager):
    """Test retrieving a specific customer by ID"""
    # Test existing customer
    response = test_client.get("/api/v1/customers/3fa85f64-5717-4562-b3fc-2c963f66afa6")
    
    assert response.status_code == status.HTTP_200_OK
    customer = response.json()
    assert customer["name"] == "John Doe"
    assert customer["email"] == "john.doe@example.com"

def test_get_customer_by_id_not_found(test_client, mock_customer_data_manager):
    """Test retrieving a non-existent customer"""
    # Generate a random UUID that won't exist
    non_existent_id = str(uuid4())
    response = test_client.get(f"/api/v1/customers/{non_existent_id}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

# TEST: POST /api/v1/customers/
def test_create_customer(test_client, mock_customer_data_manager):
    """Test creating a new customer"""
    new_customer = {
        "name": "Alice Johnson",
        "email": "alice.johnson@example.com",
        "phone": "+11234567890",
        "address": "789 Pine St, City, Country"
    }
    
    response = test_client.post("/api/v1/customers/", json=new_customer)
    
    assert response.status_code == status.HTTP_201_CREATED
    created_customer = response.json()
    assert created_customer["name"] == new_customer["name"]
    assert created_customer["email"] == new_customer["email"]
    assert "customer_id" in created_customer
    assert "created_at" in created_customer

def test_create_customer_duplicate_email(test_client, mock_customer_data_manager):
    """Test creating a customer with a duplicate email"""
    duplicate_customer = {
        "name": "John Duplicate",
        "email": "john.doe@example.com",  # This email already exists
        "phone": "+19999999999",
        "address": "999 Duplicate St, City, Country"
    }
    
    response = test_client.post("/api/v1/customers/", json=duplicate_customer)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already in use" in response.json()["detail"].lower()

def test_create_customer_invalid_phone(test_client, mock_customer_data_manager):
    """Test creating a customer with an invalid phone number"""
    invalid_customer = {
        "name": "Invalid Phone",
        "email": "valid.email@example.com",
        "phone": "not-a-phone-number",  # Invalid phone format
        "address": "123 Test St, City, Country"
    }
    
    response = test_client.post("/api/v1/customers/", json=invalid_customer)

    # This could come from Pydantic validation or our custom validation
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

# TEST: PUT /api/v1/customers/{customer_id}
def test_update_customer(test_client, mock_customer_data_manager):
    """Test updating an existing customer"""
    update_data = {
        "name": "John Doe Updated",
        "address": "New Address, City, Country"
    }
    
    response = test_client.put(
        "/api/v1/customers/3fa85f64-5717-4562-b3fc-2c963f66afa6", 
        json=update_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    updated_customer = response.json()
    assert updated_customer["name"] == update_data["name"]
    assert updated_customer["address"] == update_data["address"]
    # Email should remain unchanged
    assert updated_customer["email"] == "john.doe@example.com"

def test_update_customer_not_found(test_client, mock_customer_data_manager):
    """Test updating a non-existent customer"""
    non_existent_id = str(uuid4())
    update_data = {"name": "Nobody"}
    
    response = test_client.put(f"/api/v1/customers/{non_existent_id}", json=update_data)
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

def test_update_customer_duplicate_email(test_client, mock_customer_data_manager):
    """Test updating a customer with an email that's already in use"""
    update_data = {
        "email": "jane.smith@example.com"  # This email belongs to Jane
    }
    
    response = test_client.put(
        "/api/v1/customers/3fa85f64-5717-4562-b3fc-2c963f66afa6",  # John's ID
        json=update_data
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already in use" in response.json()["detail"]["errors"]["email"].lower()

def test_update_customer_no_fields(test_client, mock_customer_data_manager):
    """Test updating a customer without providing any fields"""
    response = test_client.put(
        "/api/v1/customers/3fa85f64-5717-4562-b3fc-2c963f66afa6",
        json={}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "must include at least one field" in response.json()["detail"]["message"].lower()

# TEST: DELETE /api/v1/customers/{customer_id}
def test_soft_delete_customer(test_client, mock_customer_data_manager):
    """Test soft deleting a customer"""
    response = test_client.delete(
        "/api/v1/customers/4fa85f64-5717-4562-b3fc-2c963f66afa7?delete_type=soft"
    )
    
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["success"] is True
    assert result["delete_type"] == "soft"
    assert "inactive" in result["message"].lower()

def test_hard_delete_customer(test_client, mock_customer_data_manager):
    """Test hard deleting a customer with no bookings"""
    # Jane has no bookings, so we can hard delete
    response = test_client.delete(
        "/api/v1/customers/4fa85f64-5717-4562-b3fc-2c963f66afa7?delete_type=hard"
    )
    
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["success"] is True
    assert result["delete_type"] == "hard"

def test_hard_delete_customer_with_bookings(test_client, mock_customer_data_manager):
    """Test hard deleting a customer who has bookings (should fail without force)"""
    # John has bookings, so hard delete should fail
    response = test_client.delete(
        "/api/v1/customers/3fa85f64-5717-4562-b3fc-2c963f66afa6?delete_type=hard"
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    result = response.json()
    assert "existing bookings" in result["detail"]["message"].lower()
    assert "options" in result["detail"]

def test_hard_delete_customer_with_bookings_forced(test_client, mock_customer_data_manager):
    """Test force hard deleting a customer who has bookings"""
    response = test_client.delete(
        "/api/v1/customers/3fa85f64-5717-4562-b3fc-2c963f66afa6?delete_type=hard&force=true"
    )
    
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["success"] is True
    assert result["delete_type"] == "hard"

def test_cascade_delete_customer(test_client, mock_customer_data_manager):
    """Test cascade deleting a customer and their bookings"""
    response = test_client.delete(
        "/api/v1/customers/7fa85f64-5717-4562-b3fc-2c963f66afaa?delete_type=cascade"
    )
    
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["success"] is True
    assert result["delete_type"] == "cascade"

def test_delete_customer_not_found(test_client, mock_customer_data_manager):
    """Test deleting a non-existent customer"""
    non_existent_id = str(uuid4())
    response = test_client.delete(f"/api/v1/customers/{non_existent_id}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()