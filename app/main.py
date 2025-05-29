from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers (to be created)
from app.routes import customers, destinations

app = FastAPI(
    title="Travel Service Backend",
    description="Backend system for managing travel services including customer profiles, bookings, and destinations",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, in production restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(customers.router, prefix="/api/v1")
app.include_router(destinations.router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Travel Service Backend API",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
