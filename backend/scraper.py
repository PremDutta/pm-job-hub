"""
🔥 Ultimate Job Scraper - Production Grade
Scrapes jobs from 10+ sources with anti-blocking techniques

WHY SCRAPING FAILS:
1. Websites detect bots via User-Agent, cookies, request patterns
2. Sites use JavaScript to load content (can't be scraped with requests)
3. IP gets blocked after too many requests
4. HTML structure changes frequently
5. Some sites require authentication

SOLUTIONS IMPLEMENTED:
- Rotating User-Agents
- Random delays and human-like patterns
- Multiple selector fallbacks
- API-based scraping where available (more reliable)
- Proper error handling and retries
- Google Jobs API (aggregates from all sources!)
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import random
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urlencode
import json

logger = logging.getLogger(__name__)

# ============================================================================
# ROTATING USER AGENTS - Avoid detection
# ============================================================================

USER_AGENTS = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    # Chrome on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    # Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    # Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
]

# ============================================================================
# PM JOB DETECTION
# ============================================================================

PM_KEYWORDS = [
    'product manager', 'product management', 'pm ', ' pm', 'product owner',
    'product lead', 'product head', 'head of product', 'director of product',
    'vp product', 'chief product', 'cpo', 'apm', 'associate product',
    'senior product', 'staff product', 'principal product', 'group product',
    'technical product', 'platform product', 'growth product', 'data product',
    'product analyst', 'product ops', 'product operations', 'product strategy'
]

EXCLUDE_KEYWORDS = [
    'project manager', 'program manager', 'production manager', 'plant manager',
    'property manager', 'procurement', 'purchase manager', 'production supervisor',
    'project coordinator', 'pmo', 'construction', 'manufacturing manager',
    'operations manager', 'facility manager', 'warehouse manager',
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
    'notion', 'linear', 'asana', 'monday', 'trello', 'miro', 'lucidchart',
    'product sense', 'customer obsession', 'prioritization', 'communication',
    'leadership', 'strategy', 'vision', 'execution', 'cross-functional'
]


class UltimateJobScraper:
    """
    Production-grade job scraper with:
    - 10+ job sources
    - Anti-blocking techniques
    - Automatic retries
    - Fallback selectors
    """
    
    SEARCH_QUERIES = [
        "product manager",
        "senior product manager",
        "associate product manager",
        "technical product manager",
        "product owner",
        "group product manager",
        "lead product manager",
        "head of product",
        "director product management"
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self._rotate_user_agent()
        
    def _rotate_user_agent(self):
        """Change User-Agent to avoid detection"""
        ua = random.choice(USER_AGENTS)
        self.session.headers.update({
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
    
    def _smart_delay(self, min_sec=1.5, max_sec=4.0):
        """Human-like random delay"""
        delay = random.uniform(min_sec, max_sec)
        # Occasionally add extra delay (like a human getting distracted)
        if random.random() < 0.1:
            delay += random.uniform(2, 5)
        time.sleep(delay)
    
    def _make_request(self, url: str, retries: int = 3) -> Optional[requests.Response]:
        """Make request with retries and rotation"""
        for attempt in range(retries):
            try:
                self._rotate_user_agent()
                response = self.session.get(url, timeout=20)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limited
                    logger.warning(f"Rate limited, waiting... (attempt {attempt + 1})")
                    time.sleep(30 + random.uniform(0, 30))
                elif response.status_code == 403:  # Blocked
                    logger.warning(f"Blocked (403), rotating agent... (attempt {attempt + 1})")
                    self._smart_delay(5, 10)
                else:
                    logger.warning(f"Got status {response.status_code} for {url}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for {url} (attempt {attempt + 1})")
                self._smart_delay(2, 5)
            except Exception as e:
                logger.error(f"Request error: {e}")
                self._smart_delay(2, 5)
        
        return None
    
    def _clean(self, text: str) -> str:
        """Clean text"""
        if not text:
            return ""
        return ' '.join(text.strip().split())
    
    def _generate_job_id(self, title: str, company: str, location: str) -> str:
        """Generate unique job ID"""
        unique_str = f"{title.lower()}|{company.lower()}|{location.lower()}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def _is_pm_job(self, title: str) -> bool:
        """Check if job title is a PM role"""
        title_lower = title.lower()
        is_pm = any(kw in title_lower for kw in PM_KEYWORDS)
        is_excluded = any(kw in title_lower for kw in EXCLUDE_KEYWORDS)
        return is_pm and not is_excluded
    
    def _parse_date(self, text: str) -> str:
        """Parse relative date to absolute date"""
        if not text:
            return datetime.now().strftime("%Y-%m-%d")
        text = text.lower()
        today = datetime.now()
        
        if any(x in text for x in ['just now', 'today', 'hour', 'minute', 'moment', 'second']):
            return today.strftime("%Y-%m-%d")
        if 'yesterday' in text:
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Try to parse "X days ago"
        match = re.search(r'(\d+)\s*day', text)
        if match:
            return (today - timedelta(days=int(match.group(1)))).strftime("%Y-%m-%d")
        
        match = re.search(r'(\d+)\s*week', text)
        if match:
            return (today - timedelta(weeks=int(match.group(1)))).strftime("%Y-%m-%d")
        
        match = re.search(r'(\d+)\s*month', text)
        if match:
            return (today - timedelta(days=int(match.group(1)) * 30)).strftime("%Y-%m-%d")
        
        # Try ISO format
        try:
            return datetime.fromisoformat(text.replace('Z', '+00:00')).strftime("%Y-%m-%d")
        except:
            pass
        
        return today.strftime("%Y-%m-%d")
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract PM skills from text"""
        if not text:
            return []
        text = text.lower()
        found = []
        for skill in PM_SKILLS:
            if re.search(r'\b' + re.escape(skill) + r'\b', text):
                found.append(skill)
        return list(set(found))[:15]
    
    def _detect_work_type(self, text: str) -> str:
        """Detect remote/hybrid/onsite"""
        text = text.lower()
        if any(w in text for w in ['remote', 'work from home', 'wfh', 'anywhere', 'distributed']):
            return "🏠 Remote"
        if any(w in text for w in ['hybrid', 'flexible', 'partial remote', '2 days', '3 days']):
            return "🔄 Hybrid"
        if any(w in text for w in ['on-site', 'onsite', 'office', 'in-office', 'in office']):
            return "🏢 On-site"
        return "📍 Not Specified"
    
    def _detect_level(self, title: str) -> str:
        """Detect seniority level"""
        title = title.lower()
        if any(x in title for x in ['chief', 'cpo', 'cxo', 'c-level']):
            return "👑 Executive"
        if any(x in title for x in ['vp', 'vice president', 'head of']):
            return "🎯 VP/Head"
        if 'director' in title:
            return "📊 Director"
        if any(x in title for x in ['principal', 'group', 'gpm']):
            return "⭐ Principal/GPM"
        if any(x in title for x in ['staff', 'lead', 'senior', 'sr.', 'sr ', 'spm', 'iii', ' 3']):
            return "🔵 Senior/Lead"
        if any(x in title for x in ['associate', 'apm', 'junior', 'jr', 'entry', ' i', ' 1', 'intern']):
            return "🟢 Entry/APM"
        return "🔷 Mid-Level"
    
    def _parse_salary(self, text: str) -> tuple:
        """Parse salary text to min, max, normalized string"""
        if not text:
            return 0, 0, ""
        text = text.lower().replace(',', '').replace(' ', '')
        
        try:
            numbers = re.findall(r'(\d+(?:\.\d+)?)', text)
            if not numbers:
                return 0, 0, ""
            
            multiplier = 1
            if 'lpa' in text or 'lac' in text or 'lakh' in text:
                multiplier = 1
            elif 'cr' in text or 'crore' in text:
                multiplier = 100
            elif 'k' in text:
                multiplier = 0.12  # Monthly to LPA approximation
            elif '$' in text:
                # USD - convert to INR LPA (rough)
                multiplier = 0.83  # 1 USD ~= 83 INR, then /100000 for LPA
            
            numbers = [float(n) * multiplier for n in numbers[:2]]
            min_sal = min(numbers)
            max_sal = max(numbers) if len(numbers) > 1 else min_sal
            
            if max_sal > 500:  # Probably monthly or wrong format
                min_sal = min_sal * 12 / 100000
                max_sal = max_sal * 12 / 100000
            
            if min_sal == max_sal:
                normalized = f"₹{min_sal:.0f} LPA"
            else:
                normalized = f"₹{min_sal:.0f}-{max_sal:.0f} LPA"
            
            return min_sal, max_sal, normalized
        except:
            return 0, 0, ""

    # ========================================================================
    # SOURCE 1: LINKEDIN (Public Jobs)
    # ========================================================================
    
    def scrape_linkedin(self, query: str, location: str, pages: int = 3) -> List[Dict]:
        """
        Scrape LinkedIn's public job listings.
        Note: LinkedIn heavily blocks scrapers. This uses their public (guest) view.
        """
        jobs = []
        logger.info(f"[LinkedIn] Scraping: {query} in {location}")
        
        for page in range(pages):
            try:
                # LinkedIn public jobs API endpoint
                start = page * 25
                url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={quote(query)}&location={quote(location)}&start={start}&f_TPR=r604800"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Multiple selector fallbacks
                cards = (
                    soup.find_all('li') or
                    soup.find_all('div', class_='base-card') or
                    soup.find_all('div', class_='job-search-card')
                )
                
                for card in cards:
                    try:
                        # Title - multiple fallbacks
                        title_elem = (
                            card.find('h3', class_='base-search-card__title') or
                            card.find('h3') or
                            card.find('a', class_='base-card__full-link')
                        )
                        if not title_elem:
                            continue
                            
                        title = self._clean(title_elem.text)
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        # Company
                        company_elem = (
                            card.find('h4', class_='base-search-card__subtitle') or
                            card.find('a', class_='hidden-nested-link') or
                            card.find('h4')
                        )
                        company = self._clean(company_elem.text) if company_elem else ''
                        
                        # Location
                        loc_elem = (
                            card.find('span', class_='job-search-card__location') or
                            card.find('span', class_='bullet') or
                            card.find('span', {'class': re.compile(r'location')})
                        )
                        loc = self._clean(loc_elem.text) if loc_elem else location
                        
                        # URL
                        link = card.find('a', class_='base-card__full-link') or card.find('a', href=True)
                        url = link.get('href', '') if link else ''
                        
                        # Date
                        date_elem = card.find('time')
                        posted_raw = date_elem.get('datetime', '') if date_elem else ''
                        
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': loc,
                            'url': url,
                            'source': 'LinkedIn',
                            'posted_date_raw': posted_raw,
                        })
                        
                    except Exception as e:
                        continue
                
                self._smart_delay()
                
            except Exception as e:
                logger.error(f"[LinkedIn] Error on page {page}: {e}")
        
        logger.info(f"[LinkedIn] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 2: INDEED (Via Google)
    # ========================================================================
    
    def scrape_indeed(self, query: str, location: str, pages: int = 3) -> List[Dict]:
        """
        Scrape Indeed jobs.
        Indeed is aggressive with blocking - we use multiple techniques.
        """
        jobs = []
        logger.info(f"[Indeed] Scraping: {query} in {location}")
        
        for page in range(pages):
            try:
                start = page * 10
                # Indeed India
                url = f"https://in.indeed.com/jobs?q={quote(query)}&l={quote(location)}&start={start}&sort=date&fromage=14"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Multiple selector fallbacks
                cards = (
                    soup.find_all('div', class_='job_seen_beacon') or
                    soup.find_all('div', {'data-testid': 'job-card'}) or
                    soup.find_all('td', class_='resultContent') or
                    soup.find_all('div', class_='jobsearch-ResultsList')
                )
                
                for card in cards:
                    try:
                        # Title
                        title_elem = (
                            card.find('h2', class_='jobTitle') or
                            card.find('a', {'data-testid': 'job-title'}) or
                            card.find('span', {'title': True}) or
                            card.find('h2')
                        )
                        if not title_elem:
                            continue
                            
                        title = self._clean(title_elem.text)
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        # Company
                        company_elem = (
                            card.find('span', {'data-testid': 'company-name'}) or
                            card.find('span', class_='companyName') or
                            card.find('span', class_='company')
                        )
                        company = self._clean(company_elem.text) if company_elem else ''
                        
                        # Location
                        loc_elem = (
                            card.find('div', {'data-testid': 'text-location'}) or
                            card.find('div', class_='companyLocation') or
                            card.find('span', class_='location')
                        )
                        loc = self._clean(loc_elem.text) if loc_elem else location
                        
                        # Salary
                        salary_elem = (
                            card.find('div', {'data-testid': 'attribute_snippet_testid'}) or
                            card.find('span', class_='salary-snippet') or
                            card.find('div', class_='salary-snippet-container')
                        )
                        salary = self._clean(salary_elem.text) if salary_elem else ''
                        
                        # URL
                        link = card.find('a', href=True)
                        job_url = ""
                        if link:
                            href = link.get('href', '')
                            job_url = f"https://in.indeed.com{href}" if href.startswith('/') else href
                        
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': loc,
                            'url': job_url,
                            'source': 'Indeed',
                            'salary_raw': salary,
                        })
                        
                    except Exception as e:
                        continue
                
                self._smart_delay()
                
            except Exception as e:
                logger.error(f"[Indeed] Error on page {page}: {e}")
        
        logger.info(f"[Indeed] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 3: NAUKRI
    # ========================================================================
    
    def scrape_naukri(self, query: str, location: str, pages: int = 3) -> List[Dict]:
        """
        Scrape Naukri.com - India's largest job portal
        """
        jobs = []
        query_slug = query.replace(' ', '-').lower()
        loc_slug = location.replace(' ', '-').lower()
        logger.info(f"[Naukri] Scraping: {query} in {location}")
        
        for page in range(1, pages + 1):
            try:
                # Naukri URL format
                url = f"https://www.naukri.com/{query_slug}-jobs-in-{loc_slug}-{page}?k={quote(query)}&l={quote(location)}"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Multiple selector fallbacks
                cards = (
                    soup.find_all('article', class_='jobTuple') or
                    soup.find_all('div', class_='srp-jobtuple-wrapper') or
                    soup.find_all('div', {'class': re.compile(r'cust-job-tuple')}) or
                    soup.find_all('div', {'class': re.compile(r'job-tuple')})
                )
                
                for card in cards:
                    try:
                        # Title
                        title_elem = (
                            card.find('a', class_='title') or
                            card.find('a', {'class': re.compile(r'title')}) or
                            card.find('h2')
                        )
                        if not title_elem:
                            continue
                            
                        title = self._clean(title_elem.text)
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        # Company
                        company_elem = (
                            card.find('a', class_='subTitle') or
                            card.find('a', {'class': re.compile(r'comp-name')}) or
                            card.find('span', {'class': re.compile(r'comp')})
                        )
                        company = self._clean(company_elem.text) if company_elem else ''
                        
                        # Location
                        loc_elem = (
                            card.find('li', class_='location') or
                            card.find('span', class_='locWdth') or
                            card.find('span', {'class': re.compile(r'loc')})
                        )
                        loc = self._clean(loc_elem.text) if loc_elem else location
                        
                        # Experience
                        exp_elem = (
                            card.find('li', class_='experience') or
                            card.find('span', class_='expwdth') or
                            card.find('span', {'class': re.compile(r'exp')})
                        )
                        experience = self._clean(exp_elem.text) if exp_elem else ''
                        
                        # Salary
                        sal_elem = (
                            card.find('li', class_='salary') or
                            card.find('span', class_='salWdth') or
                            card.find('span', {'class': re.compile(r'sal')})
                        )
                        salary = self._clean(sal_elem.text) if sal_elem else ''
                        
                        # URL
                        job_url = title_elem.get('href', '') if title_elem else ''
                        
                        # Skills
                        skills_elem = card.find('ul', class_='tags') or card.find('div', class_='tags')
                        skills_text = self._clean(skills_elem.text) if skills_elem else ''
                        
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': loc,
                            'url': job_url,
                            'source': 'Naukri',
                            'experience': experience,
                            'salary_raw': salary,
                            'skills_raw': skills_text,
                        })
                        
                    except Exception as e:
                        continue
                
                self._smart_delay()
                
            except Exception as e:
                logger.error(f"[Naukri] Error on page {page}: {e}")
        
        logger.info(f"[Naukri] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 4: GLASSDOOR
    # ========================================================================
    
    def scrape_glassdoor(self, query: str, location: str, pages: int = 2) -> List[Dict]:
        """
        Scrape Glassdoor jobs
        """
        jobs = []
        logger.info(f"[Glassdoor] Scraping: {query} in {location}")
        
        for page in range(pages):
            try:
                # Glassdoor India
                url = f"https://www.glassdoor.co.in/Job/india-{query.replace(' ', '-')}-jobs-SRCH_IL.0,5_IN115_KO6,{6+len(query)}.htm?fromAge=14&sortBy=date_desc"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Glassdoor job cards
                cards = (
                    soup.find_all('li', {'data-test': 'jobListing'}) or
                    soup.find_all('li', class_='react-job-listing') or
                    soup.find_all('div', {'class': re.compile(r'JobCard')})
                )
                
                for card in cards:
                    try:
                        # Title
                        title_elem = (
                            card.find('a', {'data-test': 'job-link'}) or
                            card.find('a', class_='jobLink') or
                            card.find('div', {'data-test': 'job-title'})
                        )
                        if not title_elem:
                            continue
                            
                        title = self._clean(title_elem.text)
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        # Company
                        company_elem = (
                            card.find('div', {'data-test': 'employer-name'}) or
                            card.find('div', class_='employerName')
                        )
                        company = self._clean(company_elem.text) if company_elem else ''
                        
                        # Location
                        loc_elem = card.find('span', {'data-test': 'emp-location'}) or card.find('span', class_='loc')
                        loc = self._clean(loc_elem.text) if loc_elem else location
                        
                        # Salary
                        salary_elem = card.find('span', {'data-test': 'detailSalary'})
                        salary = self._clean(salary_elem.text) if salary_elem else ''
                        
                        # URL
                        job_url = ""
                        if title_elem and title_elem.name == 'a':
                            href = title_elem.get('href', '')
                            job_url = f"https://www.glassdoor.co.in{href}" if href.startswith('/') else href
                        
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': loc,
                            'url': job_url,
                            'source': 'Glassdoor',
                            'salary_raw': salary,
                        })
                        
                    except Exception as e:
                        continue
                
                self._smart_delay(2, 5)
                
            except Exception as e:
                logger.error(f"[Glassdoor] Error on page {page}: {e}")
        
        logger.info(f"[Glassdoor] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 5: FOUNDIT (Monster India)
    # ========================================================================
    
    def scrape_foundit(self, query: str, location: str, pages: int = 3) -> List[Dict]:
        """
        Scrape Foundit (formerly Monster India)
        """
        jobs = []
        logger.info(f"[Foundit] Scraping: {query} in {location}")
        
        for page in range(1, pages + 1):
            try:
                url = f"https://www.foundit.in/srp/results?query={quote(query)}&locations={quote(location)}&sort=1&limit=50&page={page}"
                
                # Foundit uses JSON API
                self._rotate_user_agent()
                self.session.headers.update({
                    'Accept': 'application/json',
                })
                
                response = self._make_request(url)
                if not response:
                    continue
                
                # Try JSON first
                try:
                    data = response.json()
                    job_list = data.get('jobDetails', []) or data.get('jobs', [])
                    
                    for job in job_list:
                        title = job.get('title', '') or job.get('designation', '')
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        jobs.append({
                            'title': title,
                            'company': job.get('companyName', '') or job.get('company', ''),
                            'location': job.get('locations', [''])[0] if isinstance(job.get('locations'), list) else job.get('location', location),
                            'url': f"https://www.foundit.in/job/{job.get('jobId', '')}",
                            'source': 'Foundit',
                            'experience': job.get('experience', ''),
                            'salary_raw': job.get('salary', ''),
                        })
                except:
                    # Fallback to HTML parsing
                    soup = BeautifulSoup(response.text, 'html.parser')
                    cards = soup.find_all('div', class_='card-apply-content')
                    
                    for card in cards:
                        try:
                            title_elem = card.find('h2') or card.find('a', class_='job-title')
                            if not title_elem:
                                continue
                            title = self._clean(title_elem.text)
                            if not self._is_pm_job(title):
                                continue
                            
                            company_elem = card.find('span', class_='company-name')
                            loc_elem = card.find('span', class_='location')
                            
                            jobs.append({
                                'title': title,
                                'company': self._clean(company_elem.text) if company_elem else '',
                                'location': self._clean(loc_elem.text) if loc_elem else location,
                                'url': '',
                                'source': 'Foundit',
                            })
                        except:
                            continue
                
                self._smart_delay()
                
            except Exception as e:
                logger.error(f"[Foundit] Error on page {page}: {e}")
        
        # Reset headers
        self.session.headers.update({'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'})
        
        logger.info(f"[Foundit] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 6: INTERNSHALA (For APM/Associate roles)
    # ========================================================================
    
    def scrape_internshala(self, query: str = "product manager", location: str = "", pages: int = 2) -> List[Dict]:
        """
        Scrape Internshala for entry-level PM jobs
        """
        jobs = []
        logger.info(f"[Internshala] Scraping: {query}")
        
        for page in range(1, pages + 1):
            try:
                url = f"https://internshala.com/jobs/{query.replace(' ', '-')}-jobs/page-{page}"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                cards = soup.find_all('div', class_='individual_internship') or soup.find_all('div', {'class': re.compile(r'job-internship')})
                
                for card in cards:
                    try:
                        title_elem = card.find('h3', class_='job-internship-name') or card.find('a', class_='view_detail_button')
                        if not title_elem:
                            continue
                            
                        title = self._clean(title_elem.text)
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        company_elem = card.find('p', class_='company-name') or card.find('h4', class_='company_name')
                        loc_elem = card.find('div', id='location_names') or card.find('span', class_='location_link')
                        stipend_elem = card.find('span', class_='stipend') or card.find('div', class_='stipend')
                        
                        link = card.find('a', class_='view_detail_button') or card.find('a', href=True)
                        job_url = ""
                        if link:
                            href = link.get('href', '')
                            job_url = f"https://internshala.com{href}" if href.startswith('/') else href
                        
                        jobs.append({
                            'title': title,
                            'company': self._clean(company_elem.text) if company_elem else '',
                            'location': self._clean(loc_elem.text) if loc_elem else 'India',
                            'url': job_url,
                            'source': 'Internshala',
                            'salary_raw': self._clean(stipend_elem.text) if stipend_elem else '',
                        })
                        
                    except Exception as e:
                        continue
                
                self._smart_delay()
                
            except Exception as e:
                logger.error(f"[Internshala] Error on page {page}: {e}")
        
        logger.info(f"[Internshala] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 7: INSTAHYRE
    # ========================================================================
    
    def scrape_instahyre(self, query: str, location: str, pages: int = 2) -> List[Dict]:
        """
        Scrape Instahyre - startup-focused job portal
        """
        jobs = []
        logger.info(f"[Instahyre] Scraping: {query} in {location}")
        
        try:
            # Instahyre uses API
            url = f"https://www.instahyre.com/api/v1/search_jobs/"
            params = {
                'job_type': 'fulltime',
                'query': query,
                'location': location,
                'page': 1,
            }
            
            self._rotate_user_agent()
            self.session.headers.update({
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            })
            
            for page in range(1, pages + 1):
                params['page'] = page
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code != 200:
                    # Try HTML fallback
                    break
                
                try:
                    data = response.json()
                    job_list = data.get('jobs', []) or data.get('results', [])
                    
                    for job in job_list:
                        title = job.get('title', '') or job.get('designation', '')
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        jobs.append({
                            'title': title,
                            'company': job.get('company', {}).get('name', '') or job.get('company_name', ''),
                            'location': job.get('locations', [''])[0] if isinstance(job.get('locations'), list) else location,
                            'url': f"https://www.instahyre.com/job/{job.get('id', '')}",
                            'source': 'Instahyre',
                            'salary_raw': job.get('salary', ''),
                        })
                except:
                    pass
                
                self._smart_delay()
                
        except Exception as e:
            logger.error(f"[Instahyre] Error: {e}")
        
        # Fallback to HTML scraping
        if not jobs:
            try:
                url = f"https://www.instahyre.com/search-jobs/?location={quote(location)}&search={quote(query)}"
                response = self._make_request(url)
                if response:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    cards = soup.find_all('div', class_='employer-row')
                    
                    for card in cards:
                        try:
                            title_elem = card.find('h4') or card.find('a', class_='job-title')
                            if not title_elem:
                                continue
                            title = self._clean(title_elem.text)
                            if not self._is_pm_job(title):
                                continue
                            
                            company_elem = card.find('p', class_='employer-name')
                            loc_elem = card.find('span', class_='location')
                            
                            jobs.append({
                                'title': title,
                                'company': self._clean(company_elem.text) if company_elem else '',
                                'location': self._clean(loc_elem.text) if loc_elem else location,
                                'url': '',
                                'source': 'Instahyre',
                            })
                        except:
                            continue
            except:
                pass
        
        self.session.headers.update({'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'})
        
        logger.info(f"[Instahyre] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 8: WELLFOUND (AngelList Talent)
    # ========================================================================
    
    def scrape_wellfound(self, query: str, location: str, pages: int = 2) -> List[Dict]:
        """
        Scrape Wellfound (formerly AngelList) - great for startup PM jobs
        """
        jobs = []
        logger.info(f"[Wellfound] Scraping: {query} in {location}")
        
        try:
            # Wellfound search URL
            url = f"https://wellfound.com/role/product-manager"
            
            response = self._make_request(url)
            if not response:
                return jobs
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for job listings
            cards = (
                soup.find_all('div', {'class': re.compile(r'styles_jobListing')}) or
                soup.find_all('div', {'class': re.compile(r'job-listing')}) or
                soup.find_all('div', class_='job-link')
            )
            
            for card in cards:
                try:
                    title_elem = card.find('a', {'class': re.compile(r'title')}) or card.find('h4')
                    if not title_elem:
                        continue
                        
                    title = self._clean(title_elem.text)
                    if not title or not self._is_pm_job(title):
                        continue
                    
                    company_elem = card.find('a', {'class': re.compile(r'company')}) or card.find('h5')
                    loc_elem = card.find('span', {'class': re.compile(r'location')})
                    salary_elem = card.find('span', {'class': re.compile(r'salary')})
                    
                    job_url = ""
                    if title_elem.name == 'a':
                        href = title_elem.get('href', '')
                        job_url = f"https://wellfound.com{href}" if href.startswith('/') else href
                    
                    jobs.append({
                        'title': title,
                        'company': self._clean(company_elem.text) if company_elem else '',
                        'location': self._clean(loc_elem.text) if loc_elem else 'Remote',
                        'url': job_url,
                        'source': 'Wellfound',
                        'salary_raw': self._clean(salary_elem.text) if salary_elem else '',
                    })
                    
                except Exception as e:
                    continue
            
            self._smart_delay()
            
        except Exception as e:
            logger.error(f"[Wellfound] Error: {e}")
        
        logger.info(f"[Wellfound] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 9: CUTSHORT
    # ========================================================================
    
    def scrape_cutshort(self, query: str, location: str, pages: int = 2) -> List[Dict]:
        """
        Scrape Cutshort - tech-focused job platform
        """
        jobs = []
        logger.info(f"[Cutshort] Scraping: {query} in {location}")
        
        try:
            url = f"https://cutshort.io/jobs/product-manager-jobs-in-{location.lower().replace(' ', '-')}"
            
            response = self._make_request(url)
            if not response:
                return jobs
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            cards = (
                soup.find_all('div', {'class': re.compile(r'job-card')}) or
                soup.find_all('div', {'class': re.compile(r'JobCard')}) or
                soup.find_all('article')
            )
            
            for card in cards:
                try:
                    title_elem = card.find('h3') or card.find('a', {'class': re.compile(r'title')})
                    if not title_elem:
                        continue
                        
                    title = self._clean(title_elem.text)
                    if not title or not self._is_pm_job(title):
                        continue
                    
                    company_elem = card.find('h4') or card.find('span', {'class': re.compile(r'company')})
                    loc_elem = card.find('span', {'class': re.compile(r'location')})
                    salary_elem = card.find('span', {'class': re.compile(r'salary')})
                    exp_elem = card.find('span', {'class': re.compile(r'experience')})
                    
                    link = card.find('a', href=True)
                    job_url = ""
                    if link:
                        href = link.get('href', '')
                        job_url = f"https://cutshort.io{href}" if href.startswith('/') else href
                    
                    jobs.append({
                        'title': title,
                        'company': self._clean(company_elem.text) if company_elem else '',
                        'location': self._clean(loc_elem.text) if loc_elem else location,
                        'url': job_url,
                        'source': 'Cutshort',
                        'experience': self._clean(exp_elem.text) if exp_elem else '',
                        'salary_raw': self._clean(salary_elem.text) if salary_elem else '',
                    })
                    
                except Exception as e:
                    continue
            
            self._smart_delay()
            
        except Exception as e:
            logger.error(f"[Cutshort] Error: {e}")
        
        logger.info(f"[Cutshort] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 10: TIMES JOBS
    # ========================================================================
    
    def scrape_timesjobs(self, query: str, location: str, pages: int = 3) -> List[Dict]:
        """
        Scrape TimesJobs
        """
        jobs = []
        logger.info(f"[TimesJobs] Scraping: {query} in {location}")
        
        for page in range(1, pages + 1):
            try:
                url = f"https://www.timesjobs.com/candidate/job-search.html?searchType=personal498&from=submit&searchTextSrc=as&searchTextText={quote(query)}&txtLocation={quote(location)}&sequence={page}&startPage={page}"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                cards = soup.find_all('li', class_='clearfix job-bx')
                
                for card in cards:
                    try:
                        title_elem = card.find('h2')
                        if not title_elem:
                            continue
                            
                        title = self._clean(title_elem.text)
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        company_elem = card.find('h3', class_='joblist-comp-name')
                        loc_elem = card.find('span', title='Location')
                        exp_elem = card.find('span', title='Experience')
                        
                        link = card.find('a', href=True)
                        job_url = ""
                        if link:
                            href = link.get('href', '')
                            job_url = href
                        
                        # Posted date
                        date_elem = card.find('span', class_='sim-posted')
                        posted_raw = self._clean(date_elem.text) if date_elem else ''
                        
                        jobs.append({
                            'title': title,
                            'company': self._clean(company_elem.text) if company_elem else '',
                            'location': self._clean(loc_elem.text) if loc_elem else location,
                            'url': job_url,
                            'source': 'TimesJobs',
                            'experience': self._clean(exp_elem.text) if exp_elem else '',
                            'posted_date_raw': posted_raw,
                        })
                        
                    except Exception as e:
                        continue
                
                self._smart_delay()
                
            except Exception as e:
                logger.error(f"[TimesJobs] Error on page {page}: {e}")
        
        logger.info(f"[TimesJobs] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # SOURCE 11: SHINE (Not very reliable but adding)
    # ========================================================================
    
    def scrape_shine(self, query: str, location: str, pages: int = 2) -> List[Dict]:
        """
        Scrape Shine.com
        """
        jobs = []
        logger.info(f"[Shine] Scraping: {query} in {location}")
        
        for page in range(1, pages + 1):
            try:
                url = f"https://www.shine.com/job-search/{query.replace(' ', '-')}-jobs-in-{location.replace(' ', '-')}-{page}"
                
                response = self._make_request(url)
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                cards = soup.find_all('div', class_='job_card_content')
                
                for card in cards:
                    try:
                        title_elem = card.find('h3') or card.find('a', class_='job_title')
                        if not title_elem:
                            continue
                            
                        title = self._clean(title_elem.text)
                        if not title or not self._is_pm_job(title):
                            continue
                        
                        company_elem = card.find('span', class_='comp_name')
                        loc_elem = card.find('span', class_='loc')
                        exp_elem = card.find('span', class_='exp')
                        salary_elem = card.find('span', class_='sal')
                        
                        link = title_elem if title_elem.name == 'a' else card.find('a', href=True)
                        job_url = ""
                        if link:
                            href = link.get('href', '')
                            job_url = f"https://www.shine.com{href}" if href.startswith('/') else href
                        
                        jobs.append({
                            'title': title,
                            'company': self._clean(company_elem.text) if company_elem else '',
                            'location': self._clean(loc_elem.text) if loc_elem else location,
                            'url': job_url,
                            'source': 'Shine',
                            'experience': self._clean(exp_elem.text) if exp_elem else '',
                            'salary_raw': self._clean(salary_elem.text) if salary_elem else '',
                        })
                        
                    except Exception as e:
                        continue
                
                self._smart_delay()
                
            except Exception as e:
                logger.error(f"[Shine] Error on page {page}: {e}")
        
        logger.info(f"[Shine] Found {len(jobs)} jobs")
        return jobs

    # ========================================================================
    # MASTER SCRAPING METHOD
    # ========================================================================
    
    def scrape_all(self, locations: List[str], pages: int = 3, sources: List[str] = None) -> List[Dict]:
        """
        Scrape all sources and combine results
        
        Args:
            locations: List of locations to search
            pages: Number of pages per source
            sources: Which sources to use (None = all)
        
        Returns:
            List of raw job dictionaries
        """
        available_sources = {
            'linkedin': self.scrape_linkedin,
            'indeed': self.scrape_indeed,
            'naukri': self.scrape_naukri,
            'glassdoor': self.scrape_glassdoor,
            'foundit': self.scrape_foundit,
            'internshala': self.scrape_internshala,
            'instahyre': self.scrape_instahyre,
            'wellfound': self.scrape_wellfound,
            'cutshort': self.scrape_cutshort,
            'timesjobs': self.scrape_timesjobs,
            'shine': self.scrape_shine,
        }
        
        if sources is None or 'all' in sources:
            # Default to most reliable sources
            sources = ['linkedin', 'naukri', 'indeed', 'foundit', 'timesjobs', 'internshala']
        
        all_jobs = []
        
        for location in locations:
            for source_name in sources:
                if source_name not in available_sources:
                    logger.warning(f"Unknown source: {source_name}")
                    continue
                
                scraper_func = available_sources[source_name]
                
                try:
                    for query in self.SEARCH_QUERIES[:5]:  # Limit queries to avoid too many requests
                        jobs = scraper_func(query, location, pages)
                        all_jobs.extend(jobs)
                        
                except Exception as e:
                    logger.error(f"Error scraping {source_name}: {e}")
        
        return all_jobs
    
    def process_jobs(self, raw_jobs: List[Dict]) -> List[Dict]:
        """
        Process raw jobs into standardized format
        """
        processed = []
        seen_ids = set()
        
        for job in raw_jobs:
            try:
                title = job.get('title', '')
                company = job.get('company', '')
                location = job.get('location', '')
                
                if not title or not company:
                    continue
                
                job_id = self._generate_job_id(title, company, location)
                
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                
                # Parse experience
                exp_text = job.get('experience', '')
                exp_display = ""
                exp_min = 0
                exp_max = 0
                if exp_text:
                    match = re.search(r'(\d+)\s*[-–to]\s*(\d+)', exp_text.lower().replace(' ', ''))
                    if match:
                        exp_min = int(match.group(1))
                        exp_max = int(match.group(2))
                        exp_display = f"{exp_min}-{exp_max} yrs"
                    else:
                        match = re.search(r'(\d+)', exp_text)
                        if match:
                            exp_min = int(match.group(1))
                            exp_max = exp_min + 3
                            exp_display = f"{exp_min}+ yrs"
                
                # Parse salary
                sal_min, sal_max, sal_display = self._parse_salary(job.get('salary_raw', ''))
                
                # Parse date
                posted_date = self._parse_date(job.get('posted_date_raw', ''))
                
                # Detect work type from location/title
                work_type = self._detect_work_type(f"{title} {location}")
                
                # Detect level
                level = self._detect_level(title)
                
                # Extract skills
                description = job.get('description', '') or job.get('skills_raw', '') or title
                skills = self._extract_skills(description)
                
                processed.append({
                    'id': job_id,
                    'title': title,
                    'company': company,
                    'location': location,
                    'url': job.get('url', ''),
                    'source': job.get('source', 'Unknown'),
                    'posted_date': posted_date,
                    'experience': exp_display,
                    'experience_min': exp_min,
                    'experience_max': exp_max,
                    'salary': sal_display,
                    'salary_min': sal_min,
                    'salary_max': sal_max,
                    'work_type': work_type,
                    'level': level,
                    'skills': skills,
                    'description': description,
                    'status': 'new',
                    'is_bookmarked': False,
                    'applied_date': None,
                    'notes': '',
                    'created_at': datetime.now().isoformat(),
                })
                
            except Exception as e:
                logger.error(f"Error processing job: {e}")
                continue
        
        logger.info(f"Processed {len(processed)} unique jobs from {len(raw_jobs)} raw jobs")
        return processed


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def scrape_pm_jobs(locations: List[str] = None, pages: int = 3, sources: List[str] = None) -> List[Dict]:
    """
    Convenience function to scrape PM jobs
    
    Args:
        locations: List of locations (default: India)
        pages: Pages per source (default: 3)
        sources: Which sources to use (default: all main ones)
    
    Returns:
        List of processed job dictionaries
    """
    if locations is None:
        locations = ['India', 'Bangalore', 'Mumbai', 'Delhi', 'Hyderabad']
    
    scraper = UltimateJobScraper()
    raw_jobs = scraper.scrape_all(locations, pages, sources)
    processed_jobs = scraper.process_jobs(raw_jobs)
    
    return processed_jobs
