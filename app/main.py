import os
import atexit

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.routes.ai_routes import router as ai_router
from app.routes.auth_routes import router as auth_router

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(ai_router)
app.include_router(auth_router)



@app.get("/")
async def root():
    return {"message": "Hello, World!"}

# Function to ping the root endpoint
def ping_root():
    """Ping the root endpoint to keep the worker alive"""
    try:
        # Get the base URL from environment variable or use localhost
        # Render provides RENDER_EXTERNAL_URL, but you can also set RENDER_SERVICE_URL
        base_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("RENDER_SERVICE_URL") or "http://localhost:8000"
        url = f"{base_url}/"
        
        # Make a GET request to the root endpoint
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            print(f"Pinged {url} - Status: {response.status_code}")
    except Exception as e:
        print(f"Error pinging root endpoint: {e}")

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=ping_root,
    trigger=IntervalTrigger(seconds=15),
    id='ping_root_job',
    name='Ping root endpoint every 15 seconds',
    replace_existing=True
)

# Start scheduler when app starts
@app.on_event("startup")
async def startup_event():
    scheduler.start()
    print("Scheduler started - will ping root endpoint every 15 seconds")

# Shutdown scheduler when app stops
@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    print("Scheduler stopped")

# Also register shutdown handler for cleanup
atexit.register(lambda: scheduler.shutdown())