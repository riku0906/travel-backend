# tests/test_destination_api.py
import pytest
import uuid
import json
from unittest import mock
import time
from app.routes import destinations as dest_routes

# Test cases for CRUD operations
class TestDestinationCRUD:
    
    def test_get_all_destinations(self, test_client, mock_file_operations, mock_cache):
        """Test getting all destinations with default pagination."""
        response = test_client.get("/destinations/")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total_count" in data
        assert "page" in data
        assert data["total_count"] == 4  # Based on our sample data
        assert len(data["items"]) == 4  # All fit in default page size
        
    def test_get_all_destinations_pagination(self, test_client, mock_file_operations, mock_cache):
        """Test pagination of destinations."""
        # Test first page with 2 items
        response = test_client.get("/destinations/?page=1&page_size=2")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2  # With 4 items and page_size=2, we should have 2 pages
        assert data["has_next_page"] == True
        assert data["has_prev_page"] == False
        
        # Test second page
        response = test_client.get("/destinations/?page=2&page_size=2")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 2  # Last 2 items
        assert data["page"] == 2
        assert data["has_next_page"] == False
        assert data["has_prev_page"] == True

    def test_get_destination_by_id(self, test_client, mock_file_operations, mock_cache, sample_destination_data):
        """Test getting a specific destination by ID."""
        destination_id = sample_destination_data[0]["destination_id"]
        response = test_client.get(f"/destinations/{destination_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["destination_id"] == destination_id
        assert data["name"] == sample_destination_data[0]["name"]
        
    def test_get_destination_by_id_not_found(self, test_client, mock_file_operations, mock_cache):
        """Test getting a non-existent destination."""
        non_existent_id = str(uuid.uuid4())
        response = test_client.get(f"/destinations/{non_existent_id}")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "message" in data["detail"]
        assert "requested_id" in data["detail"]
        assert data["detail"]["requested_id"] == non_existent_id
        
    def test_create_destination(self, test_client, mock_file_operations, mock_cache):
        """Test creating a new destination."""
        # We need to mock write_destinations to prevent actual file writes
        with mock.patch.object(dest_routes, 'write_destinations') as mock_write:
            new_destination = {
                "name": "Santorini",
                "location": "Greece",
                "description": "Beautiful island with white buildings and blue domes.",
                "price_range": "luxury",
                "availability": True
            }
            
            response = test_client.post("/destinations/", json=new_destination)
            assert response.status_code == 201
            
            data = response.json()
            assert data["name"] == new_destination["name"]
            assert data["location"] == new_destination["location"]
            assert "destination_id" in data
            
            # Verify write_destinations was called
            mock_write.assert_called_once()
    
    def test_update_destination(self, test_client, mock_file_operations, mock_cache, mock_destination_objects, sample_destination_data):
        """Test updating an existing destination."""
        destination_id = sample_destination_data[1]["destination_id"]
        
        # We need to mock read_destinations and write_destinations
        with mock.patch.object(dest_routes, 'read_destinations', return_value=(mock_destination_objects, len(mock_destination_objects))) as mock_read:
            with mock.patch.object(dest_routes, 'write_destinations') as mock_write:
                update_data = {
                    "name": "Updated Tokyo",
                    "description": "Updated description for Tokyo.",
                    "price_range": "moderate"
                }
                
                response = test_client.put(f"/destinations/{destination_id}", json=update_data)
                assert response.status_code == 200
                
                data = response.json()
                assert data["name"] == update_data["name"]
                assert data["description"] == update_data["description"]
                assert data["price_range"] == update_data["price_range"]
                # Fields not in update_data should remain unchanged
                assert data["location"] == sample_destination_data[1]["location"]
                
                # Verify write_destinations was called
                mock_write.assert_called_once()
    
    def test_update_destination_not_found(self, test_client, mock_file_operations, mock_cache, mock_destination_objects):
        """Test updating a non-existent destination."""
        non_existent_id = str(uuid.uuid4())
        
        # Mock read_destinations to return actual data
        with mock.patch.object(dest_routes, 'read_destinations', return_value=(mock_destination_objects, len(mock_destination_objects))):
            update_data = {"name": "Non-existent Destination"}
            response = test_client.put(f"/destinations/{non_existent_id}", json=update_data)
            assert response.status_code == 404
    
    def test_delete_destination(self, test_client, mock_file_operations, mock_cache, mock_destination_objects, sample_destination_data):
        """Test deleting an existing destination."""
        destination_id = sample_destination_data[2]["destination_id"]
        
        # Mock read_destinations and write_destinations
        with mock.patch.object(dest_routes, 'read_destinations', return_value=(mock_destination_objects, len(mock_destination_objects))):
            with mock.patch.object(dest_routes, 'write_destinations') as mock_write:
                response = test_client.delete(f"/destinations/{destination_id}")
                assert response.status_code == 204
                mock_write.assert_called_once()
    
    def test_delete_destination_not_found(self, test_client, mock_file_operations, mock_cache, mock_destination_objects):
        """Test deleting a non-existent destination."""
        non_existent_id = str(uuid.uuid4())
        
        # Mock read_destinations to return actual data
        with mock.patch.object(dest_routes, 'read_destinations', return_value=(mock_destination_objects, len(mock_destination_objects))):
            response = test_client.delete(f"/destinations/{non_existent_id}")
            assert response.status_code == 404


# Test cases for filtering and advanced features
class TestDestinationFiltering:

    def test_filter_by_name(self, test_client, mock_file_operations, mock_cache):
        """Test filtering destinations by name."""
        response = test_client.get("/destinations/?name=Tok")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Tokyo"
        
    def test_filter_by_location(self, test_client, mock_file_operations, mock_cache):
        """Test filtering destinations by location."""
        response = test_client.get("/destinations/?location=japan")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["location"] == "Japan"
        
    def test_filter_by_price_range(self, test_client, mock_file_operations, mock_cache):
        """Test filtering destinations by price range."""
        response = test_client.get("/destinations/?price_range=budget")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["price_range"] == "budget"
        
    def test_filter_by_availability(self, test_client, mock_file_operations, mock_cache):
        """Test filtering destinations by availability."""
        response = test_client.get("/destinations/?availability=false")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["availability"] == False
        
    def test_multiple_filters(self, test_client, mock_file_operations, mock_cache):
        """Test applying multiple filters simultaneously."""
        response = test_client.get("/destinations/?price_range=moderate&availability=true")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["price_range"] == "moderate"
        assert data["items"][0]["availability"] == True
        
    def test_filter_no_results(self, test_client, mock_file_operations, mock_cache):
        """Test filtering with criteria that match no destinations."""
        response = test_client.get("/destinations/?name=NonExistentPlace")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 0
        assert data["total_count"] == 0


# Test cases for cache behavior
class TestDestinationCache:

    def test_cache_stats_endpoint(self, test_client, mock_file_operations, mock_cache):
        """Test the cache statistics endpoint."""
        response = test_client.get("/destinations/cache-stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "access_count" in data
        assert "hit_count" in data
        assert "miss_count" in data
        assert "hit_rate_percentage" in data
        
    def test_force_refresh(self, test_client, mock_file_operations, mock_cache):
        """Test forcing a cache refresh."""
        # First access to warm up cache
        test_client.get("/destinations/")
        
        # Get current hit count
        stats_response = test_client.get("/destinations/cache-stats")
        initial_stats = stats_response.json()
        
        # Mock the cache miss counting behavior for force refresh
        with mock.patch.object(dest_routes._cache, 'miss_count', initial_stats["miss_count"]):
            # Force refresh and check if miss count increased
            with mock.patch.object(dest_routes, 'refresh_cache') as mock_refresh:
                test_client.get("/destinations/?refresh=true")
                mock_refresh.assert_called_once()


# Test cases for validation and error handling
class TestDestinationValidation:

    def test_create_destination_validation(self, test_client, mock_file_operations, mock_cache):
        """Test validation when creating a destination with missing required fields."""
        with mock.patch.object(dest_routes, 'write_destinations'):
            # Missing required fields
            invalid_destination = {
                "name": "Missing Fields Destination"
                # Missing location, description, price_range
            }
            
            response = test_client.post("/destinations/", json=invalid_destination)
            assert response.status_code == 422  # Unprocessable Entity
            
            data = response.json()
            assert "detail" in data
            # Check that validation errors mention the missing fields
            missing_fields = ["location", "description", "price_range"]
            for field in missing_fields:
                assert any(field in err["loc"] for err in data["detail"])
                