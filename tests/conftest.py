import pytest
import json
import os
import uuid
import time
import datetime
from unittest import mock
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.destination import Destination
from app.routes import destinations as dest_routes
from app.routes.customers import get_customer_data_manager, CustomerDataManager

# ────────────────────────────────────────────────
# General Test Client
# ────────────────────────────────────────────────

@pytest.fixture
def test_client():
    """Return a TestClient instance for API testing."""
    with TestClient(app) as client:
        yield client

# ────────────────────────────────────────────────
# Destination-Related Fixtures
# ────────────────────────────────────────────────

@pytest.fixture
def temp_data_dir(tmpdir):
    """Create a temporary data directory and clean up after tests."""
    data_dir = tmpdir.mkdir("data")
    yield data_dir

@pytest.fixture
def sample_destination_data():
    """Return sample destination data for testing."""
    return [
        {
            "destination_id": str(uuid.uuid4()),
            "name": "Paris",
            "location": "France",
            "description": "City of Light with iconic landmarks.",
            "price_range": "moderate",
            "availability": True
        },
        {
            "destination_id": str(uuid.uuid4()),
            "name": "Tokyo",
            "location": "Japan",
            "description": "Bustling metropolis with a mix of ultramodern and traditional.",
            "price_range": "luxury",
            "availability": True
        },
        {
            "destination_id": str(uuid.uuid4()),
            "name": "Bali",
            "location": "Indonesia",
            "description": "Beautiful island paradise with beaches and temples.",
            "price_range": "budget",
            "availability": False
        },
        {
            "destination_id": str(uuid.uuid4()),
            "name": "New York",
            "location": "United States",
            "description": "The city that never sleeps with iconic skyline.",
            "price_range": "ultra_luxury",
            "availability": True
        }
    ]

@pytest.fixture
def mock_destination_objects(sample_destination_data):
    """Convert sample data to Destination objects."""
    return [Destination(**dest) for dest in sample_destination_data]

@pytest.fixture
def mock_file_operations(sample_destination_data):
    """Mock file operations to avoid actual file I/O during tests."""
    with mock.patch('os.path.exists', return_value=True) as mock_exists:
        with mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(sample_destination_data))) as mock_open:
            with mock.patch('json.dump') as mock_dump:
                with mock.patch('os.path.getmtime', return_value=12345) as mock_mtime:
                    yield {
                        'exists': mock_exists,
                        'open': mock_open,
                        'dump': mock_dump,
                        'mtime': mock_mtime
                    }

@pytest.fixture
def mock_cache(mock_destination_objects):
    """Mock the destination cache to avoid actual cache operations during tests."""
    dest_routes._cache = dest_routes.IndexedCache()
    with mock.patch.object(dest_routes._cache, 'data', mock_destination_objects):
        with mock.patch.object(dest_routes._cache, 'last_refresh_time', time.time()):
            with mock.patch.object(dest_routes._cache, 'last_modified_time', time.time()):
                dest_routes._cache.build_indexes()
                yield dest_routes._cache

# ────────────────────────────────────────────────
# Customer-Related Fixtures
# ────────────────────────────────────────────────

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

    mock_manager = Mock(spec=CustomerDataManager)

    mock_manager.get_all_customers.return_value = test_customers.copy()
    mock_manager.get_customer_by_id.side_effect = lambda customer_id: next(
        (c for c in test_customers if c["customer_id"] == str(customer_id)), None
    )
    mock_manager.check_email_exists.side_effect = lambda email, exclude_customer_id=None: any(
        c["email"].lower() == email.lower() and
        (not exclude_customer_id or c["customer_id"] != str(exclude_customer_id))
        for c in test_customers
    )
    mock_manager.add_customer.side_effect = lambda customer: test_customers.append(customer) or customer

    def mock_update_customer(customer_id, updated_data):
        for i, customer in enumerate(test_customers):
            if customer["customer_id"] == str(customer_id):
                test_customers[i].update(updated_data)
                return test_customers[i]
        return None
    mock_manager.update_customer.side_effect = mock_update_customer

    mock_manager.hard_delete_customer.side_effect = lambda customer_id: any(
        test_customers.pop(i)
        for i, c in enumerate(test_customers)
        if c["customer_id"] == str(customer_id)
    )

    def mock_soft_delete_customer(customer_id):
        for c in test_customers:
            if c["customer_id"] == str(customer_id):
                c["is_active"] = False
                c["deleted_at"] = str(datetime.datetime.now())
                return True
        return False
    mock_manager.soft_delete_customer.side_effect = mock_soft_delete_customer

    mock_manager.get_customer_bookings.side_effect = lambda customer_id: [
        b for b in test_bookings if b["customer_id"] == str(customer_id)
    ]

    def mock_cascade_delete_customer(customer_id):
        booking_ids = [b["booking_id"] for b in test_bookings if b["customer_id"] == str(customer_id)]
        test_bookings[:] = [b for b in test_bookings if b["customer_id"] != str(customer_id)]
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

    monkeypatch.setattr("app.routes.customers.get_customer_data_manager", lambda: mock_manager)
    return mock_manager
