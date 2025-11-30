"""
PM Job Hub - Production Server
Serves both the FastAPI backend and static frontend
"""
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Import the backend app directly - it already has /api routes
from backend.app import app as api_app, init_db

# Get the directory where this file is located
BASE_DIR = Path(__file__).resolve().parent

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

# Include all routes from the backend API EXCEPT the root "/" route
for route in api_app.routes:
    # Skip the backend's root route - we want our frontend there
    if hasattr(route, 'path') and route.path == "/":
        continue
    app.routes.append(route)

# Serve frontend at root
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    frontend_path = BASE_DIR / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    # Fallback: return inline HTML with error message
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head><title>PM Job Hub</title></head>
    <body style="font-family: sans-serif; padding: 40px; text-align: center;">
        <h1>🚀 PM Job Hub</h1>
        <p>Frontend file not found at: {frontend_path}</p>
        <p>But the API is working! Try: <a href="/api/sources">/api/sources</a></p>
    </body>
    </html>
    """, status_code=200)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
