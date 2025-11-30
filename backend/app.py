"""
🚀 PM Job Scraper Pro - Enhanced Backend API
Version 3.0 - The Ultimate Product Manager Job Hunting Tool

Features:
- Multi-source job scraping (LinkedIn, Indeed, Naukri, Instahyre, Cutshort)
- Application tracking pipeline (Kanban-style stages)
- Company intelligence (funding, type, size)
- Salary benchmarking
- Skills gap analysis
- Interview preparation
- AI-powered job matching
- Notes & follow-up tracking
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import sqlite3
import json
import hashlib
import requests
from bs4 import BeautifulSoup
import re
import csv
import io
import logging
import time
import random
import threading
from collections import Counter

# ============================================================================
# CONFIGURATION
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "pm_jobs_pro.db")

# ============================================================================
# FRESHNESS CALCULATION HELPERS
# ============================================================================

def calculate_freshness(posted_date: str, created_at: str) -> Dict[str, Any]:
    """Calculate job freshness based on posted date or created date"""
    today = datetime.now().date()
    
    # Try to parse posted_date first, fall back to created_at
    job_date = None
    date_to_use = posted_date or created_at
    
    if date_to_use:
        try:
            if 'T' in date_to_use:
                job_date = datetime.fromisoformat(date_to_use.replace('Z', '+00:00')).date()
            else:
                job_date = datetime.strptime(date_to_use[:10], "%Y-%m-%d").date()
        except:
            job_date = today
    else:
        job_date = today
    
    days_ago = (today - job_date).days
    
    # Determine freshness category and label
    if days_ago == 0:
        freshness = "today"
        freshness_label = "🔥 Posted Today"
        is_new = True
        is_urgent = True
    elif days_ago == 1:
        freshness = "yesterday"
        freshness_label = "Yesterday"
        is_new = True
        is_urgent = True
    elif days_ago <= 3:
        freshness = "this_week"
        freshness_label = f"🕐 {days_ago} days ago"
        is_new = True
        is_urgent = False
    elif days_ago <= 7:
        freshness = "this_week"
        freshness_label = f"{days_ago} days ago"
        is_new = False
        is_urgent = False
    elif days_ago <= 14:
        freshness = "last_two_weeks"
        freshness_label = f"{days_ago} days ago"
        is_new = False
        is_urgent = False
    elif days_ago <= 30:
        freshness = "this_month"
        freshness_label = f"{days_ago // 7} weeks ago"
        is_new = False
        is_urgent = False
    else:
        freshness = "older"
        freshness_label = f"{days_ago // 30}+ months ago"
        is_new = False
        is_urgent = False
    
    return {
        "freshness": freshness,
        "freshness_label": freshness_label,
        "days_ago": days_ago,
        "is_new": is_new,
        "is_urgent": is_urgent
    }

# ============================================================================
# DATABASE - Enhanced Schema
# ============================================================================

def get_db():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Jobs table - Enhanced
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT,
            company_slug TEXT,
            location TEXT,
            work_type TEXT,
            job_level TEXT,
            experience TEXT,
            experience_min INTEGER DEFAULT 0,
            experience_max INTEGER DEFAULT 0,
            salary_raw TEXT,
            salary_min REAL DEFAULT 0,
            salary_max REAL DEFAULT 0,
            salary_normalized TEXT,
            description TEXT,
            requirements TEXT,
            skills TEXT,
            benefits TEXT,
            company_type TEXT,
            company_size TEXT,
            company_funding TEXT,
            company_industry TEXT,
            company_rating REAL,
            company_reviews_count INTEGER,
            posted_date TEXT,
            posted_date_raw TEXT,
            application_deadline TEXT,
            source TEXT,
            url TEXT,
            url_hash TEXT,
            relevance_score INTEGER DEFAULT 50,
            match_score INTEGER DEFAULT 0,
            
            -- Application Tracking
            status TEXT DEFAULT 'new',
            applied_date TEXT,
            interview_date TEXT,
            follow_up_date TEXT,
            offer_amount TEXT,
            rejection_reason TEXT,
            
            -- User Actions
            is_bookmarked INTEGER DEFAULT 0,
            is_hidden INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0,
            notes TEXT,
            tags TEXT,
            
            -- Timestamps
            created_at TEXT,
            updated_at TEXT,
            last_viewed_at TEXT
        )
    """)
    
    # User Profile table for job matching
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            current_role TEXT,
            experience_years INTEGER,
            current_salary REAL,
            expected_salary_min REAL,
            expected_salary_max REAL,
            preferred_locations TEXT,
            preferred_work_types TEXT,
            preferred_company_types TEXT,
            skills TEXT,
            education TEXT,
            resume_text TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    # Company Intelligence table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE,
            slug TEXT,
            type TEXT,
            size TEXT,
            funding_stage TEXT,
            funding_amount TEXT,
            industry TEXT,
            headquarters TEXT,
            founded_year INTEGER,
            website TEXT,
            linkedin_url TEXT,
            glassdoor_rating REAL,
            glassdoor_reviews INTEGER,
            ambitionbox_rating REAL,
            description TEXT,
            tech_stack TEXT,
            culture_tags TEXT,
            interview_difficulty TEXT,
            avg_interview_duration TEXT,
            common_interview_questions TEXT,
            pros TEXT,
            cons TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    # Application Events/Activity Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            event_type TEXT,
            event_data TEXT,
            created_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    
    # Interview Prep Notes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_prep (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            company_research TEXT,
            role_preparation TEXT,
            questions_to_ask TEXT,
            key_talking_points TEXT,
            practice_answers TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    
    # Reminders
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            reminder_type TEXT,
            reminder_date TEXT,
            message TEXT,
            is_completed INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    
    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_bookmarked ON jobs(is_bookmarked)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# ============================================================================
# MODELS
# ============================================================================

class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    location: str
    work_type: str
    job_level: str
    experience: str
    experience_min: int
    experience_max: int
    salary_raw: str
    salary_min: float
    salary_max: float
    salary_normalized: str
    description: str
    requirements: str
    skills: List[str]
    benefits: List[str]
    company_type: str
    company_size: str
    company_funding: str
    company_industry: str
    company_rating: Optional[float]
    posted_date: str
    application_deadline: str
    source: str
    url: str
    relevance_score: int
    match_score: int
    status: str
    applied_date: str
    interview_date: str
    follow_up_date: str
    is_bookmarked: bool
    priority: int
    notes: str
    tags: List[str]
    created_at: str
    # New freshness fields
    freshness: str  # "today", "yesterday", "this_week", "older"
    freshness_label: str  # "🔥 Posted Today", "Yesterday", "3 days ago"
    days_ago: int
    is_new: bool  # Posted within 24 hours
    is_urgent: bool  # Closing soon or very fresh

class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

class StatsResponse(BaseModel):
    total_jobs: int
    new_today: int
    yesterday: int
    last_3_days: int
    last_7_days: int
    last_14_days: int
    bookmarked: int
    applied: int
    interviews: int
    offers: int
    by_source: Dict[str, int]
    by_level: Dict[str, int]
    by_work_type: Dict[str, int]
    by_location: Dict[str, int]
    by_status: Dict[str, int]
    by_company_type: Dict[str, int]
    by_freshness: Dict[str, int]
    salary_distribution: Dict[str, int]
    top_skills: Dict[str, int]
    application_funnel: Dict[str, int]
    weekly_activity: List[Dict[str, Any]]

class PipelineResponse(BaseModel):
    new: List[JobResponse]
    bookmarked: List[JobResponse]
    applied: List[JobResponse]
    interviewing: List[JobResponse]
    offered: List[JobResponse]
    rejected: List[JobResponse]

class UpdateJobRequest(BaseModel):
    is_bookmarked: Optional[bool] = None
    is_hidden: Optional[bool] = None
    status: Optional[str] = None
    applied_date: Optional[str] = None
    interview_date: Optional[str] = None
    follow_up_date: Optional[str] = None
    offer_amount: Optional[str] = None
    rejection_reason: Optional[str] = None
    priority: Optional[int] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None

class UserProfileRequest(BaseModel):
    name: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[int] = None
    current_salary: Optional[float] = None
    expected_salary_min: Optional[float] = None
    expected_salary_max: Optional[float] = None
    preferred_locations: Optional[List[str]] = None
    preferred_work_types: Optional[List[str]] = None
    preferred_company_types: Optional[List[str]] = None
    skills: Optional[List[str]] = None

class ScrapeRequest(BaseModel):
    locations: List[str] = ["India"]
    days: int = 14
    pages: int = 5
    sources: List[str] = ["all"]

class CompanyResponse(BaseModel):
    id: str
    name: str
    type: str
    size: str
    funding_stage: str
    industry: str
    glassdoor_rating: Optional[float]
    description: str
    pros: str
    cons: str
    interview_difficulty: str

class InterviewPrepRequest(BaseModel):
    job_id: str
    company_research: Optional[str] = None
    role_preparation: Optional[str] = None
    questions_to_ask: Optional[str] = None
    key_talking_points: Optional[str] = None
    practice_answers: Optional[str] = None

class ReminderRequest(BaseModel):
    job_id: str
    reminder_type: str
    reminder_date: str
    message: str

# ============================================================================
# COMPANY INTELLIGENCE
# ============================================================================

COMPANY_DATABASE = {
    # Major Tech Companies
    'google': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'Technology'},
    'microsoft': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'Technology'},
    'amazon': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'E-commerce/Cloud'},
    'meta': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'Technology'},
    'apple': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'Technology'},
    'netflix': {'type': '🏢 MNC', 'size': '5000-10000', 'funding': 'Public', 'industry': 'Entertainment'},
    'uber': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'Mobility'},
    'salesforce': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'SaaS'},
    'adobe': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'Software'},
    'oracle': {'type': '🏢 MNC', 'size': '10000+', 'funding': 'Public', 'industry': 'Enterprise'},
    
    # Indian Unicorns
    'flipkart': {'type': '🦄 Unicorn', 'size': '10000+', 'funding': 'Series H+', 'industry': 'E-commerce'},
    'swiggy': {'type': '🦄 Unicorn', 'size': '5000-10000', 'funding': 'Series J', 'industry': 'Food Delivery'},
    'zomato': {'type': '🦄 Unicorn', 'size': '5000-10000', 'funding': 'Public', 'industry': 'Food Delivery'},
    'razorpay': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Series F', 'industry': 'Fintech'},
    'cred': {'type': '🦄 Unicorn', 'size': '500-1000', 'funding': 'Series E', 'industry': 'Fintech'},
    'phonepe': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Series D', 'industry': 'Fintech'},
    'byju': {'type': '🦄 Unicorn', 'size': '10000+', 'funding': 'Series F', 'industry': 'EdTech'},
    'ola': {'type': '🦄 Unicorn', 'size': '5000-10000', 'funding': 'Series J', 'industry': 'Mobility'},
    'paytm': {'type': '🦄 Unicorn', 'size': '10000+', 'funding': 'Public', 'industry': 'Fintech'},
    'zerodha': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Bootstrapped', 'industry': 'Fintech'},
    'dream11': {'type': '🦄 Unicorn', 'size': '500-1000', 'funding': 'Series E', 'industry': 'Gaming'},
    'meesho': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Series F', 'industry': 'E-commerce'},
    'groww': {'type': '🦄 Unicorn', 'size': '500-1000', 'funding': 'Series E', 'industry': 'Fintech'},
    'unacademy': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Series H', 'industry': 'EdTech'},
    'lenskart': {'type': '🦄 Unicorn', 'size': '5000-10000', 'funding': 'Series G', 'industry': 'E-commerce'},
    'nykaa': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Public', 'industry': 'E-commerce'},
    'freshworks': {'type': '🦄 Unicorn', 'size': '5000-10000', 'funding': 'Public', 'industry': 'SaaS'},
    'zoho': {'type': '🏢 Enterprise', 'size': '10000+', 'funding': 'Bootstrapped', 'industry': 'SaaS'},
    'postman': {'type': '🦄 Unicorn', 'size': '500-1000', 'funding': 'Series D', 'industry': 'Developer Tools'},
    'browserstack': {'type': '🦄 Unicorn', 'size': '500-1000', 'funding': 'Series B', 'industry': 'Developer Tools'},
    'chargebee': {'type': '🦄 Unicorn', 'size': '500-1000', 'funding': 'Series G', 'industry': 'SaaS'},
    'druva': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Series H', 'industry': 'Cloud'},
    'icertis': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Series F', 'industry': 'Enterprise'},
    
    # Well-funded Startups
    'slice': {'type': '🚀 Startup', 'size': '500-1000', 'funding': 'Series B', 'industry': 'Fintech'},
    'jupiter': {'type': '🚀 Startup', 'size': '200-500', 'funding': 'Series C', 'industry': 'Fintech'},
    'fi': {'type': '🚀 Startup', 'size': '200-500', 'funding': 'Series C', 'industry': 'Fintech'},
    'smallcase': {'type': '🚀 Startup', 'size': '200-500', 'funding': 'Series C', 'industry': 'Fintech'},
    'cleartax': {'type': '🚀 Startup', 'size': '500-1000', 'funding': 'Series C', 'industry': 'Fintech'},
    'healthifyme': {'type': '🚀 Startup', 'size': '200-500', 'funding': 'Series C', 'industry': 'HealthTech'},
    'spinny': {'type': '🚀 Startup', 'size': '1000-5000', 'funding': 'Series E', 'industry': 'Automotive'},
    'cars24': {'type': '🦄 Unicorn', 'size': '5000-10000', 'funding': 'Series F', 'industry': 'Automotive'},
    'urban company': {'type': '🦄 Unicorn', 'size': '1000-5000', 'funding': 'Series F', 'industry': 'Services'},
    'dunzo': {'type': '🚀 Startup', 'size': '1000-5000', 'funding': 'Series E', 'industry': 'Delivery'},
    'khatabook': {'type': '🚀 Startup', 'size': '200-500', 'funding': 'Series C', 'industry': 'Fintech'},
    'zepto': {'type': '🚀 Startup', 'size': '1000-5000', 'funding': 'Series E', 'industry': 'Quick Commerce'},
    'blinkit': {'type': '🦄 Unicorn', 'size': '5000-10000', 'funding': 'Acquired', 'industry': 'Quick Commerce'},
    
    # Consulting & Services
    'mckinsey': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Private', 'industry': 'Consulting'},
    'bcg': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Private', 'industry': 'Consulting'},
    'bain': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Private', 'industry': 'Consulting'},
    'deloitte': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Private', 'industry': 'Consulting'},
    'accenture': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Public', 'industry': 'Consulting'},
    'kpmg': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Private', 'industry': 'Consulting'},
    'pwc': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Private', 'industry': 'Consulting'},
    'ey': {'type': '🏢 Consulting', 'size': '10000+', 'funding': 'Private', 'industry': 'Consulting'},
    
    # Banks & Financial Services
    'hdfc': {'type': '🏦 BFSI', 'size': '10000+', 'funding': 'Public', 'industry': 'Banking'},
    'icici': {'type': '🏦 BFSI', 'size': '10000+', 'funding': 'Public', 'industry': 'Banking'},
    'axis': {'type': '🏦 BFSI', 'size': '10000+', 'funding': 'Public', 'industry': 'Banking'},
    'kotak': {'type': '🏦 BFSI', 'size': '10000+', 'funding': 'Public', 'industry': 'Banking'},
    'bajaj': {'type': '🏦 BFSI', 'size': '10000+', 'funding': 'Public', 'industry': 'Financial Services'},
}

def get_company_intelligence(company_name: str) -> Dict:
    """Get company intelligence from our database"""
    if not company_name:
        return {}
    
    company_lower = company_name.lower().strip()
    
    # Direct match
    for key, data in COMPANY_DATABASE.items():
        if key in company_lower or company_lower in key:
            return data
    
    # Fuzzy match
    for key, data in COMPANY_DATABASE.items():
        if any(word in company_lower for word in key.split()):
            return data
    
    # Default classification based on keywords
    if any(word in company_lower for word in ['technologies', 'tech', 'software', 'labs', 'ai', 'io']):
        return {'type': '🚀 Startup', 'size': 'Unknown', 'funding': 'Unknown', 'industry': 'Technology'}
    elif any(word in company_lower for word in ['bank', 'finance', 'capital', 'fund']):
        return {'type': '🏦 BFSI', 'size': 'Unknown', 'funding': 'Unknown', 'industry': 'Financial Services'}
    elif any(word in company_lower for word in ['consulting', 'solutions', 'services']):
        return {'type': '🏢 Enterprise', 'size': 'Unknown', 'funding': 'Unknown', 'industry': 'Services'}
    
    return {'type': 'Unknown', 'size': 'Unknown', 'funding': 'Unknown', 'industry': 'Unknown'}

# ============================================================================
# JOB SCRAPER - Enhanced
# ============================================================================

class JobScraper:
    PM_KEYWORDS = [
        'product manager', 'product management', 'senior product manager',
        'lead product manager', 'principal product manager', 'associate product manager',
        'group product manager', 'director of product', 'vp product', 'head of product',
        'chief product officer', 'product owner', 'technical product manager',
        'pm ', 'spm', 'gpm', 'apm'
    ]
    
    EXCLUDE_KEYWORDS = [
        'production manager', 'project manager', 'program manager',
        'product designer', 'product analyst', 'product marketing',
        'manufacturing', 'assembly', 'warehouse'
    ]
    
    SEARCH_QUERIES = [
        "product manager",
        "senior product manager", 
        "lead product manager",
        "associate product manager",
        "technical product manager",
        "product owner",
        "group product manager",
        "director product",
        "head of product"
    ]
    
    PM_SKILLS = [
        'sql', 'python', 'analytics', 'a/b testing', 'agile', 'scrum', 'jira',
        'roadmap', 'user research', 'data analysis', 'metrics', 'kpi', 'okr',
        'stakeholder management', 'go-to-market', 'gtm', 'b2b', 'b2c', 'saas', 
        'api', 'mobile', 'web', 'ux', 'ui', 'figma', 'product strategy',
        'market research', 'competitive analysis', 'customer interviews',
        'wireframing', 'prototyping', 'mvp', 'sprint planning', 'backlog',
        'user stories', 'prd', 'prfaq', 'specification', 'requirements',
        'revenue', 'growth', 'retention', 'activation', 'engagement',
        'funnel', 'conversion', 'monetization', 'pricing', 'experimentation',
        'machine learning', 'ml', 'ai', 'data science', 'tableau', 'amplitude',
        'mixpanel', 'google analytics', 'segment', 'heap', 'hotjar', 'confluence',
        'notion', 'linear', 'asana', 'monday', 'trello', 'miro', 'lucidchart'
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def clean(self, text):
        if not text:
            return ""
        return ' '.join(text.strip().split())
    
    def delay(self):
        time.sleep(random.uniform(2.0, 4.0))
    
    def generate_job_id(self, title, company, location):
        unique_str = f"{title.lower()}|{company.lower()}|{location.lower()}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def parse_date(self, text):
        if not text:
            return ""
        text = text.lower()
        today = datetime.now()
        
        if any(x in text for x in ['just now', 'today', 'hour', 'minute', 'moments']):
            return today.strftime("%Y-%m-%d")
        if 'yesterday' in text:
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        match = re.search(r'(\d+)\s*day', text)
        if match:
            return (today - timedelta(days=int(match.group(1)))).strftime("%Y-%m-%d")
        
        match = re.search(r'(\d+)\s*week', text)
        if match:
            return (today - timedelta(weeks=int(match.group(1)))).strftime("%Y-%m-%d")
        
        match = re.search(r'(\d+)\s*month', text)
        if match:
            return (today - timedelta(days=int(match.group(1)) * 30)).strftime("%Y-%m-%d")
        
        return today.strftime("%Y-%m-%d")
    
    def detect_work_type(self, text):
        text = text.lower()
        if any(w in text for w in ['remote', 'work from home', 'wfh', 'anywhere']):
            return "🏠 Remote"
        if any(w in text for w in ['hybrid', 'flexible', 'partial remote']):
            return "🔄 Hybrid"
        if any(w in text for w in ['on-site', 'onsite', 'office', 'in-office']):
            return "🏢 On-site"
        return "📍 Not Specified"
    
    def detect_level(self, title):
        title = title.lower()
        if any(x in title for x in ['chief', 'cpo', 'cxo']):
            return "👑 Executive"
        if any(x in title for x in ['vp', 'vice president', 'head of']):
            return "🎯 VP/Head"
        if 'director' in title:
            return "📊 Director"
        if any(x in title for x in ['principal', 'group', 'gpm']):
            return "⭐ Principal/GPM"
        if any(x in title for x in ['staff', 'lead', 'senior', 'sr.', 'sr ', 'spm']):
            return "🔵 Senior/Lead"
        if any(x in title for x in ['associate', 'apm', 'junior', 'jr', 'entry']):
            return "🟢 Entry/APM"
        return "🔷 Mid-Level"
    
    def parse_experience(self, text):
        if not text:
            return "", 0, 0
        text = text.lower().replace(',', '').replace(' ', '')
        
        # Try to find range like "3-5 years"
        match = re.search(r'(\d+)\s*[-–to]\s*(\d+)', text)
        if match:
            min_exp = int(match.group(1))
            max_exp = int(match.group(2))
            return f"{min_exp}-{max_exp} yrs", min_exp, max_exp
        
        # Single number
        match = re.search(r'(\d+)\s*(?:year|yr|yrs|\+)', text)
        if match:
            exp = int(match.group(1))
            return f"{exp}+ yrs", exp, exp + 3
        
        return "", 0, 0
    
    def parse_salary(self, text):
        if not text:
            return 0, 0, ""
        text = text.lower().replace(',', '').replace(' ', '')
        
        try:
            numbers = re.findall(r'(\d+(?:\.\d+)?)', text)
            if not numbers:
                return 0, 0, ""
            
            multiplier = 1
            if 'lpa' in text or 'lac' in text or 'lakh' in text or 'l' in text:
                multiplier = 1
            elif 'cr' in text or 'crore' in text:
                multiplier = 100
            elif 'k' in text:
                multiplier = 0.12  # Monthly to LPA approximation
            
            numbers = [float(n) * multiplier for n in numbers[:2]]
            min_sal = min(numbers)
            max_sal = max(numbers) if len(numbers) > 1 else min_sal
            
            if max_sal > 200:  # Probably monthly, convert to LPA
                min_sal = min_sal * 12 / 100000
                max_sal = max_sal * 12 / 100000
            
            if min_sal == max_sal:
                normalized = f"₹{min_sal:.0f} LPA"
            else:
                normalized = f"₹{min_sal:.0f}-{max_sal:.0f} LPA"
            
            return min_sal, max_sal, normalized
        except:
            return 0, 0, ""
    
    def extract_skills(self, text):
        if not text:
            return []
        text = text.lower()
        found_skills = []
        for skill in self.PM_SKILLS:
            # Use word boundary matching for more accurate detection
            if re.search(r'\b' + re.escape(skill) + r'\b', text):
                found_skills.append(skill)
        return list(set(found_skills))[:15]
    
    def is_pm_job(self, title):
        title_lower = title.lower()
        is_pm = any(kw in title_lower for kw in self.PM_KEYWORDS)
        is_excluded = any(kw in title_lower for kw in self.EXCLUDE_KEYWORDS)
        return is_pm and not is_excluded
    
    def calculate_match_score(self, job: Dict, profile: Dict = None) -> int:
        """Calculate how well a job matches user preferences"""
        score = 50  # Base score
        
        # Boost for having salary info
        if job.get('salary_max', 0) > 0:
            score += 10
        
        # Boost for recent postings
        if job.get('posted_date'):
            try:
                posted = datetime.strptime(job['posted_date'], "%Y-%m-%d")
                days_old = (datetime.now() - posted).days
                if days_old <= 3:
                    score += 15
                elif days_old <= 7:
                    score += 10
                elif days_old <= 14:
                    score += 5
            except:
                pass
        
        # Boost for skill matches
        skills = job.get('skills', [])
        if isinstance(skills, str):
            skills = json.loads(skills) if skills else []
        if len(skills) >= 5:
            score += 10
        elif len(skills) >= 3:
            score += 5
        
        # Company reputation boost
        company_info = get_company_intelligence(job.get('company', ''))
        if company_info.get('type') in ['🦄 Unicorn', '🏢 MNC']:
            score += 10
        elif company_info.get('type') == '🚀 Startup':
            score += 5
        
        return min(100, score)
    
    def scrape_linkedin(self, query, location, pages):
        jobs = []
        logger.info(f"[LinkedIn] Scraping: {query} in {location}")
        
        for page in range(pages):
            try:
                url = f"https://www.linkedin.com/jobs/search?keywords={query}&location={location}&start={page*25}&f_TPR=r604800"
                response = self.session.get(url, timeout=15)
                if response.status_code != 200:
                    logger.warning(f"[LinkedIn] Got status {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                cards = soup.find_all('div', class_='base-card') or soup.find_all('li', class_='jobs-search-results__list-item')
                
                for card in cards:
                    try:
                        title_elem = card.find('h3', class_='base-search-card__title') or card.find('h3')
                        if not title_elem:
                            continue
                        title = self.clean(title_elem.text)
                        if not self.is_pm_job(title):
                            continue
                        
                        company_elem = card.find('h4', class_='base-search-card__subtitle') or card.find('h4')
                        loc_elem = card.find('span', class_='job-search-card__location')
                        link = card.find('a', class_='base-card__full-link') or card.find('a')
                        date_elem = card.find('time')
                        
                        jobs.append({
                            'title': title,
                            'company': self.clean(company_elem.text) if company_elem else '',
                            'location': self.clean(loc_elem.text) if loc_elem else location,
                            'url': link.get('href', '') if link else '',
                            'source': 'LinkedIn',
                            'posted_date_raw': date_elem.get('datetime', '') if date_elem else ''
                        })
                    except Exception as e:
                        continue
                
                self.delay()
            except Exception as e:
                logger.error(f"[LinkedIn] Error: {e}")
        
        logger.info(f"[LinkedIn] Found {len(jobs)} jobs")
        return jobs
    
    def scrape_indeed(self, query, location, pages):
        jobs = []
        logger.info(f"[Indeed] Scraping: {query} in {location}")
        
        for page in range(pages):
            try:
                url = f"https://in.indeed.com/jobs?q={query}&l={location}&start={page*10}&sort=date&fromage=14"
                response = self.session.get(url, timeout=15)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                cards = soup.find_all('div', class_='job_seen_beacon') or soup.find_all('div', {'data-testid': 'job-card'})
                
                for card in cards:
                    try:
                        title_elem = card.find('h2', class_='jobTitle') or card.find('h2')
                        if not title_elem:
                            continue
                        title = self.clean(title_elem.text)
                        if not self.is_pm_job(title):
                            continue
                        
                        company_elem = card.find('span', {'data-testid': 'company-name'}) or card.find('span', class_='companyName')
                        loc_elem = card.find('div', {'data-testid': 'text-location'}) or card.find('div', class_='companyLocation')
                        salary_elem = card.find('div', {'data-testid': 'attribute_snippet_testid'})
                        link = card.find('a', {'data-jk': True}) or card.find('a', class_='jcs-JobTitle')
                        
                        job_url = ""
                        if link:
                            href = link.get('href', '')
                            job_url = f"https://in.indeed.com{href}" if href.startswith('/') else href
                        
                        jobs.append({
                            'title': title,
                            'company': self.clean(company_elem.text) if company_elem else '',
                            'location': self.clean(loc_elem.text) if loc_elem else location,
                            'url': job_url,
                            'source': 'Indeed',
                            'salary_raw': self.clean(salary_elem.text) if salary_elem else '',
                            'posted_date_raw': ''
                        })
                    except:
                        continue
                
                self.delay()
            except Exception as e:
                logger.error(f"[Indeed] Error: {e}")
        
        logger.info(f"[Indeed] Found {len(jobs)} jobs")
        return jobs
    
    def scrape_naukri(self, query, location, pages):
        jobs = []
        query_slug = query.replace(' ', '-')
        loc_slug = location.lower().replace(' ', '-')
        logger.info(f"[Naukri] Scraping: {query} in {location}")
        
        for page in range(1, pages + 1):
            try:
                url = f"https://www.naukri.com/{query_slug}-jobs-in-{loc_slug}-{page}"
                response = self.session.get(url, timeout=15)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                cards = soup.find_all('article', class_='jobTuple') or soup.find_all('div', {'class': re.compile(r'srp-jobtuple|cust-job-tuple')})
                
                for card in cards:
                    try:
                        title_elem = card.find('a', class_='title') or card.find('a', {'class': re.compile(r'title')})
                        if not title_elem:
                            continue
                        title = self.clean(title_elem.text)
                        if not self.is_pm_job(title):
                            continue
                        
                        company_elem = card.find('a', class_='subTitle') or card.find('a', {'class': re.compile(r'comp-name')})
                        loc_elem = card.find('li', class_='location') or card.find('span', {'class': re.compile(r'loc')})
                        exp_elem = card.find('li', class_='experience') or card.find('span', {'class': re.compile(r'exp')})
                        sal_elem = card.find('li', class_='salary') or card.find('span', {'class': re.compile(r'sal')})
                        
                        jobs.append({
                            'title': title,
                            'company': self.clean(company_elem.text) if company_elem else '',
                            'location': self.clean(loc_elem.text) if loc_elem else location,
                            'url': title_elem.get('href', '') if title_elem else '',
                            'source': 'Naukri',
                            'experience': self.clean(exp_elem.text) if exp_elem else '',
                            'salary_raw': self.clean(sal_elem.text) if sal_elem else '',
                            'posted_date_raw': ''
                        })
                    except:
                        continue
                
                self.delay()
            except Exception as e:
                logger.error(f"[Naukri] Error: {e}")
        
        logger.info(f"[Naukri] Found {len(jobs)} jobs")
        return jobs
    
    def scrape_all(self, locations, pages=5, sources=None):
        if sources is None or 'all' in sources:
            sources = ['linkedin', 'indeed', 'naukri']
        
        all_jobs = []
        for location in locations:
            for query in self.SEARCH_QUERIES:
                if 'linkedin' in sources:
                    all_jobs.extend(self.scrape_linkedin(query, location, pages))
                if 'indeed' in sources:
                    all_jobs.extend(self.scrape_indeed(query, location, pages))
                if 'naukri' in sources:
                    all_jobs.extend(self.scrape_naukri(query, location, pages))
        return all_jobs
    
    def process_jobs(self, raw_jobs):
        processed = []
        seen_ids = set()
        
        for job in raw_jobs:
            try:
                job_id = self.generate_job_id(
                    job.get('title', ''),
                    job.get('company', ''),
                    job.get('location', '')
                )
                
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                
                title = job.get('title', '')
                company = job.get('company', '')
                description = job.get('description', '')
                full_text = f"{title} {job.get('location', '')} {description}"
                
                salary_min, salary_max, salary_norm = self.parse_salary(job.get('salary_raw', ''))
                exp_text, exp_min, exp_max = self.parse_experience(job.get('experience', ''))
                company_info = get_company_intelligence(company)
                
                job_data = {
                    'id': job_id,
                    'title': title,
                    'company': company,
                    'company_slug': company.lower().replace(' ', '-') if company else '',
                    'location': job.get('location', ''),
                    'work_type': self.detect_work_type(full_text),
                    'job_level': self.detect_level(title),
                    'experience': exp_text or job.get('experience', ''),
                    'experience_min': exp_min,
                    'experience_max': exp_max,
                    'salary_raw': job.get('salary_raw', ''),
                    'salary_min': salary_min,
                    'salary_max': salary_max,
                    'salary_normalized': salary_norm,
                    'description': description,
                    'requirements': '',
                    'skills': json.dumps(self.extract_skills(full_text)),
                    'benefits': '[]',
                    'company_type': company_info.get('type', ''),
                    'company_size': company_info.get('size', ''),
                    'company_funding': company_info.get('funding', ''),
                    'company_industry': company_info.get('industry', ''),
                    'company_rating': None,
                    'company_reviews_count': None,
                    'posted_date': self.parse_date(job.get('posted_date_raw', '')),
                    'posted_date_raw': job.get('posted_date_raw', ''),
                    'application_deadline': '',
                    'source': job.get('source', ''),
                    'url': job.get('url', ''),
                    'url_hash': hashlib.md5(job.get('url', '').encode()).hexdigest()[:12],
                    'relevance_score': 50,
                    'match_score': 0,
                    'status': 'new',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                
                job_data['match_score'] = self.calculate_match_score(job_data)
                processed.append(job_data)
                
            except Exception as e:
                logger.error(f"Error processing job: {e}")
        
        return processed

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="PM Job Scraper Pro API",
    version="3.0.0",
    description="The Ultimate Product Manager Job Hunting Tool"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()

scraper_status = {
    "is_running": False,
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "total_found": 0,
    "new_jobs": 0,
    "duplicates": 0,
    "current_source": "",
    "progress": 0
}
status_lock = threading.Lock()

# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/")
async def root():
    return {
        "message": "PM Job Scraper Pro API",
        "version": "3.0.0",
        "features": [
            "Multi-source scraping",
            "Application tracking pipeline",
            "Company intelligence",
            "Skills analysis",
            "Interview preparation"
        ]
    }

def row_to_job_response(row) -> JobResponse:
    # Calculate freshness
    freshness_data = calculate_freshness(row['posted_date'], row['created_at'])
    
    return JobResponse(
        id=row['id'],
        title=row['title'],
        company=row['company'] or '',
        location=row['location'] or '',
        work_type=row['work_type'] or '',
        job_level=row['job_level'] or '',
        experience=row['experience'] or '',
        experience_min=row['experience_min'] or 0,
        experience_max=row['experience_max'] or 0,
        salary_raw=row['salary_raw'] or '',
        salary_min=row['salary_min'] or 0,
        salary_max=row['salary_max'] or 0,
        salary_normalized=row['salary_normalized'] or '',
        description=row['description'] or '',
        requirements=row['requirements'] or '',
        skills=json.loads(row['skills']) if row['skills'] else [],
        benefits=json.loads(row['benefits']) if row['benefits'] else [],
        company_type=row['company_type'] or '',
        company_size=row['company_size'] or '',
        company_funding=row['company_funding'] or '',
        company_industry=row['company_industry'] or '',
        company_rating=row['company_rating'],
        posted_date=row['posted_date'] or '',
        application_deadline=row['application_deadline'] or '',
        source=row['source'] or '',
        url=row['url'] or '',
        relevance_score=row['relevance_score'] or 50,
        match_score=row['match_score'] or 0,
        status=row['status'] or 'new',
        applied_date=row['applied_date'] or '',
        interview_date=row['interview_date'] or '',
        follow_up_date=row['follow_up_date'] or '',
        is_bookmarked=bool(row['is_bookmarked']),
        priority=row['priority'] or 0,
        notes=row['notes'] or '',
        tags=json.loads(row['tags']) if row['tags'] else [],
        created_at=row['created_at'] or '',
        # Freshness fields
        freshness=freshness_data['freshness'],
        freshness_label=freshness_data['freshness_label'],
        days_ago=freshness_data['days_ago'],
        is_new=freshness_data['is_new'],
        is_urgent=freshness_data['is_urgent']
    )

@app.get("/api/jobs", response_model=JobListResponse)
async def get_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    source: Optional[str] = None,
    work_type: Optional[str] = None,
    level: Optional[str] = None,
    location: Optional[str] = None,
    company_type: Optional[str] = None,
    min_salary: Optional[float] = None,
    max_salary: Optional[float] = None,
    min_experience: Optional[int] = None,
    max_experience: Optional[int] = None,
    days: Optional[int] = None,
    status: Optional[str] = None,
    bookmarked_only: bool = False,
    sort_by: str = "match_score",
    sort_order: str = "desc"
):
    conn = get_db()
    cursor = conn.cursor()
    
    where_clauses = ["is_hidden = 0"]
    params = []
    
    if search:
        where_clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if source:
        where_clauses.append("source = ?")
        params.append(source)
    if work_type and work_type != "all":
        where_clauses.append("work_type LIKE ?")
        params.append(f"%{work_type}%")
    if level and level != "all":
        where_clauses.append("job_level LIKE ?")
        params.append(f"%{level}%")
    if location:
        where_clauses.append("location LIKE ?")
        params.append(f"%{location}%")
    if company_type:
        where_clauses.append("company_type LIKE ?")
        params.append(f"%{company_type}%")
    if min_salary:
        where_clauses.append("salary_max >= ?")
        params.append(min_salary)
    if max_salary:
        where_clauses.append("salary_min <= ?")
        params.append(max_salary)
    if min_experience is not None:
        where_clauses.append("experience_max >= ?")
        params.append(min_experience)
    if max_experience is not None:
        where_clauses.append("experience_min <= ?")
        params.append(max_experience)
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        where_clauses.append("posted_date >= ?")
        params.append(cutoff)
    if status and status != 'all':
        where_clauses.append("status = ?")
        params.append(status)
    if bookmarked_only:
        where_clauses.append("is_bookmarked = 1")
    
    where_sql = " AND ".join(where_clauses)
    
    cursor.execute(f"SELECT COUNT(*) FROM jobs WHERE {where_sql}", params)
    total = cursor.fetchone()[0]
    
    # Validate sort column
    valid_sort_columns = ['created_at', 'posted_date', 'match_score', 'salary_max', 'company', 'title']
    if sort_by not in valid_sort_columns:
        sort_by = 'match_score'
    
    order = "DESC" if sort_order == "desc" else "ASC"
    offset = (page - 1) * per_page
    
    cursor.execute(f"""
        SELECT * FROM jobs WHERE {where_sql}
        ORDER BY {sort_by} {order}
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])
    
    rows = cursor.fetchall()
    conn.close()
    
    jobs = [row_to_job_response(row) for row in rows]
    
    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total + per_page - 1) // per_page)
    )

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return row_to_job_response(row)

@app.patch("/api/jobs/{job_id}")
async def update_job(job_id: str, update: UpdateJobRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if update.is_bookmarked is not None:
        updates.append("is_bookmarked = ?")
        params.append(1 if update.is_bookmarked else 0)
    if update.is_hidden is not None:
        updates.append("is_hidden = ?")
        params.append(1 if update.is_hidden else 0)
    if update.status is not None:
        updates.append("status = ?")
        params.append(update.status)
    if update.applied_date is not None:
        updates.append("applied_date = ?")
        params.append(update.applied_date)
    if update.interview_date is not None:
        updates.append("interview_date = ?")
        params.append(update.interview_date)
    if update.follow_up_date is not None:
        updates.append("follow_up_date = ?")
        params.append(update.follow_up_date)
    if update.offer_amount is not None:
        updates.append("offer_amount = ?")
        params.append(update.offer_amount)
    if update.rejection_reason is not None:
        updates.append("rejection_reason = ?")
        params.append(update.rejection_reason)
    if update.priority is not None:
        updates.append("priority = ?")
        params.append(update.priority)
    if update.notes is not None:
        updates.append("notes = ?")
        params.append(update.notes)
    if update.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(update.tags))
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(job_id)
        cursor.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", params)
        
        # Log the activity
        cursor.execute("""
            INSERT INTO activity_log (job_id, event_type, event_data, created_at)
            VALUES (?, ?, ?, ?)
        """, (job_id, 'update', json.dumps(update.dict(exclude_none=True)), datetime.now().isoformat()))
        
        conn.commit()
    
    conn.close()
    return {"success": True}

@app.post("/api/jobs/{job_id}/status")
async def change_job_status(job_id: str, status: str = Query(...)):
    """Quick status change endpoint"""
    conn = get_db()
    cursor = conn.cursor()
    
    valid_statuses = ['new', 'bookmarked', 'applied', 'interviewing', 'offered', 'rejected', 'withdrawn']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    updates = {"status": status, "updated_at": datetime.now().isoformat()}
    
    if status == 'applied':
        updates["applied_date"] = datetime.now().strftime("%Y-%m-%d")
    elif status == 'bookmarked':
        updates["is_bookmarked"] = 1
    
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    cursor.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", list(updates.values()) + [job_id])
    
    # Log activity
    cursor.execute("""
        INSERT INTO activity_log (job_id, event_type, event_data, created_at)
        VALUES (?, ?, ?, ?)
    """, (job_id, 'status_change', json.dumps({"new_status": status}), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "new_status": status}

@app.get("/api/pipeline", response_model=PipelineResponse)
async def get_pipeline():
    """Get jobs organized by pipeline stage for Kanban view"""
    conn = get_db()
    cursor = conn.cursor()
    
    pipeline = {
        'new': [],
        'bookmarked': [],
        'applied': [],
        'interviewing': [],
        'offered': [],
        'rejected': []
    }
    
    for status in pipeline.keys():
        if status == 'bookmarked':
            cursor.execute("""
                SELECT * FROM jobs 
                WHERE is_bookmarked = 1 AND status = 'new' AND is_hidden = 0
                ORDER BY match_score DESC, created_at DESC
                LIMIT 50
            """)
        else:
            cursor.execute("""
                SELECT * FROM jobs 
                WHERE status = ? AND is_hidden = 0
                ORDER BY match_score DESC, created_at DESC
                LIMIT 50
            """, (status,))
        
        rows = cursor.fetchall()
        pipeline[status] = [row_to_job_response(row) for row in rows]
    
    conn.close()
    return PipelineResponse(**pipeline)

@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    # Basic counts
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_hidden = 0")
    total = cursor.fetchone()[0]
    
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    fourteen_days_ago = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    
    # Freshness counts based on posted_date (or created_at as fallback)
    cursor.execute("""
        SELECT COUNT(*) FROM jobs WHERE is_hidden = 0 
        AND (posted_date = ? OR (posted_date IS NULL AND created_at LIKE ?))
    """, (today, f"{today}%"))
    new_today = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM jobs WHERE is_hidden = 0 
        AND (posted_date = ? OR (posted_date IS NULL AND created_at LIKE ?))
    """, (yesterday, f"{yesterday}%"))
    new_yesterday = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM jobs WHERE is_hidden = 0 
        AND (posted_date >= ? OR (posted_date IS NULL AND created_at >= ?))
    """, (three_days_ago, three_days_ago))
    last_3_days = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM jobs WHERE is_hidden = 0 
        AND (posted_date >= ? OR (posted_date IS NULL AND created_at >= ?))
    """, (seven_days_ago, seven_days_ago))
    last_7_days = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM jobs WHERE is_hidden = 0 
        AND (posted_date >= ? OR (posted_date IS NULL AND created_at >= ?))
    """, (fourteen_days_ago, fourteen_days_ago))
    last_14_days = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_bookmarked = 1")
    bookmarked = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'applied'")
    applied = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'interviewing'")
    interviews = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'offered'")
    offers = cursor.fetchone()[0]
    
    # By dimensions
    cursor.execute("SELECT source, COUNT(*) FROM jobs WHERE is_hidden = 0 AND source != '' GROUP BY source")
    by_source = {r[0]: r[1] for r in cursor.fetchall()}
    
    cursor.execute("SELECT job_level, COUNT(*) FROM jobs WHERE is_hidden = 0 AND job_level != '' GROUP BY job_level")
    by_level = {r[0]: r[1] for r in cursor.fetchall()}
    
    cursor.execute("SELECT work_type, COUNT(*) FROM jobs WHERE is_hidden = 0 GROUP BY work_type")
    by_work_type = {r[0] or 'Not Specified': r[1] for r in cursor.fetchall()}
    
    cursor.execute("SELECT location, COUNT(*) FROM jobs WHERE is_hidden = 0 AND location != '' GROUP BY location ORDER BY COUNT(*) DESC LIMIT 10")
    by_location = {r[0]: r[1] for r in cursor.fetchall()}
    
    cursor.execute("SELECT status, COUNT(*) FROM jobs WHERE is_hidden = 0 GROUP BY status")
    by_status = {r[0] or 'new': r[1] for r in cursor.fetchall()}
    
    cursor.execute("SELECT company_type, COUNT(*) FROM jobs WHERE is_hidden = 0 AND company_type != '' GROUP BY company_type ORDER BY COUNT(*) DESC")
    by_company_type = {r[0]: r[1] for r in cursor.fetchall()}
    
    # Freshness distribution
    by_freshness = {
        '🔥 Today': new_today,
        'Yesterday': new_yesterday,
        'Last 3 Days': last_3_days,
        'Last 7 Days': last_7_days,
        'Last 14 Days': last_14_days,
        'Older': total - last_14_days
    }
    
    # Salary distribution
    cursor.execute("""
        SELECT CASE 
            WHEN salary_max = 0 THEN 'Not Disclosed'
            WHEN salary_max < 15 THEN '0-15 LPA'
            WHEN salary_max < 25 THEN '15-25 LPA'
            WHEN salary_max < 40 THEN '25-40 LPA'
            WHEN salary_max < 60 THEN '40-60 LPA'
            ELSE '60+ LPA' END, COUNT(*)
        FROM jobs WHERE is_hidden = 0 GROUP BY 1
    """)
    salary_dist = {r[0]: r[1] for r in cursor.fetchall()}
    
    # Top skills
    cursor.execute("SELECT skills FROM jobs WHERE is_hidden = 0 AND skills != '[]'")
    all_skills = []
    for row in cursor.fetchall():
        try:
            skills = json.loads(row[0])
            all_skills.extend(skills)
        except:
            pass
    top_skills = dict(Counter(all_skills).most_common(15))
    
    # Application funnel
    application_funnel = {
        'Total Jobs': total,
        'Bookmarked': bookmarked,
        'Applied': applied,
        'Interviewing': interviews,
        'Offers': offers
    }
    
    # Weekly activity (last 7 days)
    weekly_activity = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE created_at LIKE ?", (f"{date}%",))
        count = cursor.fetchone()[0]
        weekly_activity.append({"date": date, "count": count})
    
    conn.close()
    
    return StatsResponse(
        total_jobs=total,
        new_today=new_today,
        yesterday=new_yesterday,
        last_3_days=last_3_days,
        last_7_days=last_7_days,
        last_14_days=last_14_days,
        bookmarked=bookmarked,
        applied=applied,
        interviews=interviews,
        offers=offers,
        by_source=by_source,
        by_level=by_level,
        by_work_type=by_work_type,
        by_location=by_location,
        by_status=by_status,
        by_company_type=by_company_type,
        by_freshness=by_freshness,
        salary_distribution=salary_dist,
        top_skills=top_skills,
        application_funnel=application_funnel,
        weekly_activity=weekly_activity
    )

@app.get("/api/insights")
async def get_insights():
    """Get AI-powered insights about the job market"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Average salary by level
    cursor.execute("""
        SELECT job_level, AVG(salary_max) as avg_salary, COUNT(*) as count
        FROM jobs 
        WHERE salary_max > 0 AND is_hidden = 0
        GROUP BY job_level
        ORDER BY avg_salary DESC
    """)
    salary_by_level = [{"level": r[0], "avg_salary": round(r[1], 1), "count": r[2]} for r in cursor.fetchall()]
    
    # Hot companies (most listings)
    cursor.execute("""
        SELECT company, company_type, COUNT(*) as jobs_count
        FROM jobs 
        WHERE is_hidden = 0 AND company != ''
        GROUP BY company
        ORDER BY jobs_count DESC
        LIMIT 15
    """)
    hot_companies = [{"company": r[0], "type": r[1], "jobs": r[2]} for r in cursor.fetchall()]
    
    # Trending skills
    cursor.execute("SELECT skills FROM jobs WHERE created_at >= ? AND skills != '[]'", 
                   ((datetime.now() - timedelta(days=7)).isoformat(),))
    recent_skills = []
    for row in cursor.fetchall():
        try:
            skills = json.loads(row[0])
            recent_skills.extend(skills)
        except:
            pass
    trending_skills = dict(Counter(recent_skills).most_common(10))
    
    # Remote vs On-site trend
    cursor.execute("""
        SELECT work_type, COUNT(*) 
        FROM jobs WHERE is_hidden = 0
        GROUP BY work_type
    """)
    work_type_dist = {r[0] or 'Unknown': r[1] for r in cursor.fetchall()}
    
    # Experience requirements
    cursor.execute("""
        SELECT 
            CASE 
                WHEN experience_max <= 2 THEN '0-2 years'
                WHEN experience_max <= 5 THEN '3-5 years'
                WHEN experience_max <= 8 THEN '5-8 years'
                WHEN experience_max <= 12 THEN '8-12 years'
                ELSE '12+ years'
            END as exp_range,
            COUNT(*) as count
        FROM jobs 
        WHERE is_hidden = 0 AND experience_max > 0
        GROUP BY exp_range
        ORDER BY MIN(experience_max)
    """)
    experience_dist = {r[0]: r[1] for r in cursor.fetchall()}
    
    conn.close()
    
    return {
        "salary_by_level": salary_by_level,
        "hot_companies": hot_companies,
        "trending_skills": trending_skills,
        "work_type_distribution": work_type_dist,
        "experience_distribution": experience_dist,
        "insights": [
            f"🔥 {hot_companies[0]['company']} is hiring the most PMs right now" if hot_companies else "",
            f"💰 {salary_by_level[0]['level']} roles have the highest average salary" if salary_by_level else "",
            f"🏠 {work_type_dist.get('🏠 Remote', 0)} remote positions available",
            f"📈 {list(trending_skills.keys())[0]} is the most in-demand skill" if trending_skills else ""
        ]
    }

@app.get("/api/company/{company_name}")
async def get_company_info(company_name: str):
    """Get detailed company information"""
    company_info = get_company_intelligence(company_name)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get jobs from this company
    cursor.execute("""
        SELECT COUNT(*) as job_count, 
               AVG(salary_max) as avg_salary,
               GROUP_CONCAT(DISTINCT job_level) as levels
        FROM jobs 
        WHERE company LIKE ? AND is_hidden = 0
    """, (f"%{company_name}%",))
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        "name": company_name,
        **company_info,
        "jobs_count": row[0] if row else 0,
        "avg_salary": round(row[1], 1) if row and row[1] else None,
        "hiring_for": row[2].split(',') if row and row[2] else []
    }

# Scraper endpoints
def run_scraper_task(locations, days, pages, sources):
    global scraper_status
    
    try:
        scraper = JobScraper()
        
        with status_lock:
            scraper_status["current_source"] = "Starting..."
            scraper_status["progress"] = 0
        
        raw_jobs = scraper.scrape_all(locations, pages, sources)
        
        with status_lock:
            scraper_status["total_found"] = len(raw_jobs)
            scraper_status["current_source"] = "Processing..."
            scraper_status["progress"] = 50
        
        processed_jobs = scraper.process_jobs(raw_jobs)
        
        conn = get_db()
        cursor = conn.cursor()
        
        new_count = 0
        dup_count = 0
        
        for job in processed_jobs:
            cursor.execute("SELECT id FROM jobs WHERE id = ?", (job['id'],))
            if cursor.fetchone():
                dup_count += 1
                continue
            
            columns = ', '.join(job.keys())
            placeholders = ', '.join(['?' for _ in job])
            cursor.execute(f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", list(job.values()))
            new_count += 1
        
        conn.commit()
        conn.close()
        
        with status_lock:
            scraper_status.update({
                "new_jobs": new_count,
                "duplicates": dup_count,
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "is_running": False,
                "progress": 100,
                "current_source": "Done!"
            })
        
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        with status_lock:
            scraper_status.update({
                "status": f"error: {str(e)}",
                "is_running": False
            })

@app.post("/api/scrape")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    global scraper_status
    
    with status_lock:
        if scraper_status["is_running"]:
            raise HTTPException(status_code=400, detail="Scraper already running")
        
        scraper_status.update({
            "is_running": True,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "total_found": 0,
            "new_jobs": 0,
            "duplicates": 0,
            "current_source": "",
            "progress": 0
        })
    
    background_tasks.add_task(run_scraper_task, request.locations, request.days, request.pages, request.sources)
    return {"message": "Scraping started", "status": scraper_status}

@app.get("/api/scrape/status")
async def get_scrape_status():
    return scraper_status

# User Profile
@app.get("/api/profile")
async def get_profile():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profile ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"exists": False}
    
    return {
        "exists": True,
        "name": row['name'],
        "current_role": row['current_role'],
        "experience_years": row['experience_years'],
        "current_salary": row['current_salary'],
        "expected_salary_min": row['expected_salary_min'],
        "expected_salary_max": row['expected_salary_max'],
        "preferred_locations": json.loads(row['preferred_locations']) if row['preferred_locations'] else [],
        "preferred_work_types": json.loads(row['preferred_work_types']) if row['preferred_work_types'] else [],
        "preferred_company_types": json.loads(row['preferred_company_types']) if row['preferred_company_types'] else [],
        "skills": json.loads(row['skills']) if row['skills'] else []
    }

@app.post("/api/profile")
async def save_profile(profile: UserProfileRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO user_profile (name, current_role, experience_years, current_salary,
            expected_salary_min, expected_salary_max, preferred_locations, preferred_work_types,
            preferred_company_types, skills, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        profile.name, profile.current_role, profile.experience_years, profile.current_salary,
        profile.expected_salary_min, profile.expected_salary_max,
        json.dumps(profile.preferred_locations) if profile.preferred_locations else '[]',
        json.dumps(profile.preferred_work_types) if profile.preferred_work_types else '[]',
        json.dumps(profile.preferred_company_types) if profile.preferred_company_types else '[]',
        json.dumps(profile.skills) if profile.skills else '[]',
        datetime.now().isoformat(), datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()
    
    return {"success": True}

# Interview Prep
@app.get("/api/interview-prep/{job_id}")
async def get_interview_prep(job_id: str):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM interview_prep WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
    row = cursor.fetchone()
    
    if not row:
        # Also get the job info
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        conn.close()
        
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "job_id": job_id,
            "job_title": job_row['title'],
            "company": job_row['company'],
            "company_research": "",
            "role_preparation": "",
            "questions_to_ask": "",
            "key_talking_points": "",
            "practice_answers": ""
        }
    
    conn.close()
    return dict(row)

@app.post("/api/interview-prep")
async def save_interview_prep(prep: InterviewPrepRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO interview_prep (job_id, company_research, role_preparation, 
            questions_to_ask, key_talking_points, practice_answers, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prep.job_id, prep.company_research, prep.role_preparation,
        prep.questions_to_ask, prep.key_talking_points, prep.practice_answers,
        datetime.now().isoformat(), datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()
    
    return {"success": True}

# Reminders
@app.get("/api/reminders")
async def get_reminders(include_completed: bool = False):
    conn = get_db()
    cursor = conn.cursor()
    
    if include_completed:
        cursor.execute("""
            SELECT r.*, j.title, j.company 
            FROM reminders r
            JOIN jobs j ON r.job_id = j.id
            ORDER BY r.reminder_date ASC
        """)
    else:
        cursor.execute("""
            SELECT r.*, j.title, j.company 
            FROM reminders r
            JOIN jobs j ON r.job_id = j.id
            WHERE r.is_completed = 0
            ORDER BY r.reminder_date ASC
        """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.post("/api/reminders")
async def create_reminder(reminder: ReminderRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO reminders (job_id, reminder_type, reminder_date, message, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (reminder.job_id, reminder.reminder_type, reminder.reminder_date, 
          reminder.message, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return {"success": True}

@app.patch("/api/reminders/{reminder_id}")
async def complete_reminder(reminder_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET is_completed = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# Export
@app.get("/api/export/csv")
async def export_csv(status: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs WHERE is_hidden = 0"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Company', 'Location', 'Work Type', 'Level', 'Experience', 
                     'Salary', 'Company Type', 'Status', 'Applied Date', 'Source', 'URL', 'Notes'])
    
    for row in rows:
        writer.writerow([
            row['title'], row['company'], row['location'], row['work_type'],
            row['job_level'], row['experience'], row['salary_normalized'] or row['salary_raw'],
            row['company_type'], row['status'], row['applied_date'],
            row['source'], row['url'], row['notes']
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pm_jobs_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

# Helper endpoints
@app.get("/api/sources")
async def get_sources():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT source FROM jobs WHERE source != ''")
    sources = [r[0] for r in cursor.fetchall()]
    conn.close()
    return sources

@app.get("/api/locations")
async def get_locations():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT location FROM jobs WHERE location != '' GROUP BY location ORDER BY COUNT(*) DESC LIMIT 50")
    locations = [r[0] for r in cursor.fetchall()]
    conn.close()
    return locations

@app.get("/api/companies")
async def get_companies():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT company FROM jobs WHERE company != '' GROUP BY company ORDER BY COUNT(*) DESC LIMIT 100")
    companies = [r[0] for r in cursor.fetchall()]
    conn.close()
    return companies

# Bulk operations
@app.post("/api/jobs/bulk-update")
async def bulk_update_jobs(job_ids: List[str], update: UpdateJobRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if update.status is not None:
        updates.append("status = ?")
        params.append(update.status)
    if update.is_bookmarked is not None:
        updates.append("is_bookmarked = ?")
        params.append(1 if update.is_bookmarked else 0)
    if update.is_hidden is not None:
        updates.append("is_hidden = ?")
        params.append(1 if update.is_hidden else 0)
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        
        placeholders = ','.join(['?' for _ in job_ids])
        cursor.execute(f"""
            UPDATE jobs SET {', '.join(updates)} 
            WHERE id IN ({placeholders})
        """, params + job_ids)
        conn.commit()
    
    conn.close()
    return {"success": True, "updated": len(job_ids)}

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 PM Job Scraper Pro Backend running at http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
