"""
PM Job Hub - Production Server
Serves both the FastAPI backend and static frontend
"""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Import the backend app
from backend.app import app as api_app

# Create main app
app = FastAPI(title="PM Job Hub")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the backend API at /api
app.mount("/api", api_app)

# Serve frontend
@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
