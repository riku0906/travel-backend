from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from uuid import UUID
import json
import os
import time
from datetime import datetime
from collections import defaultdict
import re
from app.models.destination import (
    Destination, 
    DestinationCreate, 
    DestinationUpdate, 
    PriceRange,
    PaginatedDestinations
)

router = APIRouter(
    prefix="/destinations",
    tags=["destinations"],
    responses={
        404: {"description": "Destination not found"},
        500: {"description": "Internal server error"}
    }
)

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "destinations.json")
CACHE_TTL = 60  # seconds

# Enhanced indexed cache
class IndexedCache:
    def __init__(self):
        self.data = None
        self.last_refresh_time = 0
        self.is_refreshing = False
        self.last_modified_time = 0
        self.access_count = 0
        self.hit_count = 0
        self.miss_count = 0

        # Indexes
        self.name_index = defaultdict(list)
        self.location_index = defaultdict(list)
        self.price_range_index = defaultdict(list)
        self.availability_index = {True: [], False: []}

    def build_indexes(self):
        if not self.data:
            return
        self.name_index.clear()
        self.location_index.clear()
        self.price_range_index.clear()
        self.availability_index[True] = []
        self.availability_index[False] = []

        for i, destination in enumerate(self.data):
            for word in re.findall(r'\w+', destination.name.lower()):
                if len(word) > 2:
                    self.name_index[word].append(i)
            self.location_index[destination.location.lower()].append(i)
            self.price_range_index[destination.price_range].append(i)
            self.availability_index[destination.availability].append(i)

_cache = IndexedCache()

def is_cache_valid():
    current_time = time.time()
    if current_time - _cache.last_refresh_time > CACHE_TTL:
        return False
    if os.path.exists(DATA_FILE):
        file_mod_time = os.path.getmtime(DATA_FILE)
        if file_mod_time > _cache.last_modified_time:
            return False
    return _cache.data is not None

def get_cache_stats():
    hit_rate = (_cache.hit_count / _cache.access_count) * 100 if _cache.access_count else 0
    return {
        "access_count": _cache.access_count,
        "hit_count": _cache.hit_count,
        "miss_count": _cache.miss_count,
        "hit_rate_percentage": hit_rate,
        "last_refresh": datetime.fromtimestamp(_cache.last_refresh_time).isoformat() if _cache.last_refresh_time > 0 else None,
        "age_seconds": time.time() - _cache.last_refresh_time if _cache.last_refresh_time > 0 else None
    }

async def refresh_cache_async(background_tasks: BackgroundTasks):
    if not _cache.is_refreshing:
        background_tasks.add_task(refresh_cache)

def refresh_cache():
    if _cache.is_refreshing:
        return
    try:
        _cache.is_refreshing = True
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump([], f)
            _cache.data = []
        else:
            with open(DATA_FILE, "r") as f:
                _cache.data = [Destination(**dest) for dest in json.load(f)]
        _cache.build_indexes()
        _cache.last_refresh_time = time.time()
        _cache.last_modified_time = os.path.getmtime(DATA_FILE)
    except Exception as e:
        _cache.data = None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read destinations: {str(e)}"
        )
    finally:
        _cache.is_refreshing = False

def invalidate_cache():
    _cache.data = None
    _cache.last_refresh_time = 0
    _cache.last_modified_time = 0

def read_destinations(
    skip: int = 0, 
    limit: int = 100,
    name_filter: Optional[str] = None,
    location_filter: Optional[str] = None,
    price_range_filter: Optional[PriceRange] = None,
    availability_filter: Optional[bool] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    force_refresh: bool = False
):
    _cache.access_count += 1
    if force_refresh or not is_cache_valid():
        _cache.miss_count += 1
        refresh_cache()
    else:
        _cache.hit_count += 1
        if background_tasks and time.time() - _cache.last_refresh_time > CACHE_TTL * 0.8:
            background_tasks.add_task(refresh_cache)

    if _cache.data is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load destination data"
        )

    result_indexes = set(range(len(_cache.data)))

    if name_filter:
        name_matches = set()
        for word in re.findall(r'\w+', name_filter.lower()):
            if len(word) > 2:
                name_matches.update(_cache.name_index.get(word, []))
        if not name_matches:
            name_matches = {i for i, dest in enumerate(_cache.data) if name_filter.lower() in dest.name.lower()}
        result_indexes &= name_matches

    if location_filter:
        key = location_filter.lower()
        location_matches = set(_cache.location_index.get(key, []))
        if not location_matches:
            location_matches = {i for i, dest in enumerate(_cache.data) if key in dest.location.lower()}
        result_indexes &= location_matches

    if price_range_filter:
        result_indexes &= set(_cache.price_range_index.get(price_range_filter, []))

    if availability_filter is not None:
        result_indexes &= set(_cache.availability_index.get(availability_filter, []))

    filtered_destinations = [_cache.data[i] for i in result_indexes]
    filtered_destinations.sort(key=lambda x: x.name)

    total_count = len(filtered_destinations)
    paginated = filtered_destinations[skip:skip + limit]

    return paginated, total_count

def write_destinations(destinations: List[Destination]):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump([dest.dict() for dest in destinations], f, default=str)
        invalidate_cache()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write destinations: {str(e)}"
        )

@router.get("/cache-stats", response_model=Dict[str, Any])
async def get_destinations_cache_stats():
    return get_cache_stats()

@router.get("/", response_model=PaginatedDestinations)
async def get_all_destinations(
    background_tasks: BackgroundTasks,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    name: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    price_range: Optional[PriceRange] = Query(None),
    availability: Optional[bool] = Query(None),
    refresh: bool = Query(False)
):
    skip = (page - 1) * page_size
    destinations, total_count = read_destinations(
        skip=skip,
        limit=page_size,
        name_filter=name,
        location_filter=location,
        price_range_filter=price_range,
        availability_filter=availability,
        background_tasks=background_tasks,
        force_refresh=refresh
    )
    total_pages = (total_count + page_size - 1) // page_size
    return PaginatedDestinations(
        items=destinations,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next_page=(page < total_pages),
        has_prev_page=(page > 1)
    )

@router.get("/{destination_id}", response_model=Destination)
async def get_destination(destination_id: UUID, background_tasks: BackgroundTasks):
    destinations, _ = read_destinations(background_tasks=background_tasks)
    for destination in destinations:
        if destination.destination_id == destination_id:
            return destination
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "message": f"Destination with ID {destination_id} not found",
            "requested_id": str(destination_id),
            "suggestion": "Verify the destination ID or use GET /destinations/"
        }
    )

@router.post("/", response_model=Destination, status_code=status.HTTP_201_CREATED)
async def create_destination(destination: DestinationCreate):
    all_destinations, _ = read_destinations(force_refresh=True)
    new_destination = Destination(**destination.dict())
    all_destinations.append(new_destination)
    write_destinations(all_destinations)
    return new_destination

@router.put("/{destination_id}", response_model=Destination)
async def update_destination(destination_id: UUID, destination_update: DestinationUpdate):
    destinations, _ = read_destinations(force_refresh=True)
    for i, destination in enumerate(destinations):
        if destination.destination_id == destination_id:
            updated_data = destination_update.dict(exclude_unset=True)
            updated_destination = destination.copy(update=updated_data)
            destinations[i] = updated_destination
            write_destinations(destinations)
            return updated_destination
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": f"Destination with ID {destination_id} not found"}
    )

@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_destination(destination_id: UUID):
    destinations, _ = read_destinations(force_refresh=True)
    for i, destination in enumerate(destinations):
        if destination.destination_id == destination_id:
            del destinations[i]
            write_destinations(destinations)
            return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": f"Destination with ID {destination_id} not found"}
    )
