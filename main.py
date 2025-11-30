"""
PM Job Hub - Production Server
Serves both the FastAPI backend and static frontend
"""
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import the backend app directly - it already has /api routes
from backend.app import app as api_app, init_db

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

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()

# Include all routes from the backend API
# The backend routes already have /api prefix
for route in api_app.routes:
    app.routes.append(route)

# Serve frontend
@app.get("/")
async def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return JSONResponse({"error": "Frontend not found", "path": frontend_path}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
