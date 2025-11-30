# 🚀 PM Job Hub

A powerful Product Manager job aggregator that scrapes jobs from multiple sources.

## Features

- Multi-source job scraping (LinkedIn, Indeed, Naukri, Instahyre, Cutshort)
- Application tracking with Kanban-style stages
- Job filtering by location, experience, salary
- Bookmark and track applications
- Dark mode support

## Quick Start (Local Development)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/pm-job-hub.git
cd pm-job-hub

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
uvicorn main:app --reload --port 8000
```

Visit `http://localhost:8000` in your browser.

---

## 🌐 Deploy to Render (Free Hosting)

### Step 1: Push to GitHub

1. Create a GitHub account at https://github.com if you don't have one
2. Click the **+** icon → **New repository**
3. Name it `pm-job-hub` (or any name you like)
4. Keep it **Public** (required for free hosting)
5. Don't add README (we already have one)
6. Click **Create repository**

Then push your code:

```bash
cd pm-job-hub

# Initialize git
git init
git add .
git commit -m "Initial commit"

# Add your GitHub repo (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/pm-job-hub.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to https://render.com and sign up (use GitHub for easy login)
2. Click **New +** → **Web Service**
3. Connect your GitHub account if prompted
4. Select your `pm-job-hub` repository
5. Configure the service:
   - **Name**: `pm-job-hub` (or anything)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Select **Free** plan
7. Click **Create Web Service**

Wait 2-3 minutes for deployment. Your app will be live at:
`https://pm-job-hub.onrender.com` (or similar)

---

## 🚀 Alternative: Deploy to Railway

1. Go to https://railway.app and sign up with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Railway auto-detects Python and deploys!
5. Click **Generate Domain** to get your URL

---

## Project Structure

```
pm-job-hub/
├── main.py              # Main entry point (serves both API + frontend)
├── requirements.txt     # Python dependencies
├── render.yaml          # Render deployment config
├── backend/
│   ├── app.py          # FastAPI backend with all routes
│   └── pm_jobs_pro.db  # SQLite database (auto-created)
└── frontend/
    └── index.html      # React frontend (single file)
```

## API Endpoints

- `GET /api/jobs` - List all jobs with filters
- `GET /api/stats` - Dashboard statistics
- `POST /api/scrape` - Start job scraping
- `GET /api/scrape/status` - Check scrape progress
- `PATCH /api/jobs/{id}` - Update job details
- `POST /api/jobs/{id}/status` - Change job status

## License

MIT
