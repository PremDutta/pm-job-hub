# 🔧 Why Job Scraping Fails & How We Fixed It

## The Problem

When you try to scrape job websites, you often get 0 results. Here's why:

### 1. **Bot Detection** 🤖
Websites detect scrapers using:
- User-Agent headers (they block "python-requests")
- Request patterns (too fast = bot)
- Missing cookies/headers
- IP reputation

**Our Fix:** We rotate User-Agents, add realistic headers, and use random delays.

### 2. **JavaScript-Rendered Content** ⚡
Many sites (like LinkedIn, Indeed) load jobs via JavaScript AFTER the page loads. Simple HTTP requests only see empty HTML.

**Our Fix:** We use their public API endpoints where possible, or parse the initial HTML that contains the data.

### 3. **Rate Limiting** ⏱️
Sites track how many requests you make and block you if it's too many.

**Our Fix:** 
- Random delays between requests (2-5 seconds)
- Limit pages per source
- Occasional longer pauses

### 4. **Changing HTML Structure** 🔄
Websites change their HTML classes/IDs frequently to break scrapers.

**Our Fix:** Multiple fallback selectors for each element:
```python
title = (
    card.find('h3', class_='job-title') or
    card.find('h2', class_='title') or
    card.find('a', class_='job-link')
)
```

### 5. **CAPTCHAs & Login Walls** 🚧
Some sites require login or show CAPTCHAs after a few requests.

**Our Fix:** Focus on public/guest endpoints that don't require authentication.

---

## Sources & Reliability

| Source | Reliability | Notes |
|--------|-------------|-------|
| **Naukri** | ⭐⭐⭐⭐⭐ | Most reliable for India |
| **TimesJobs** | ⭐⭐⭐⭐ | Good for India |
| **LinkedIn** | ⭐⭐⭐ | Public guest API, can be slow |
| **Indeed** | ⭐⭐⭐ | Aggressive bot detection |
| **Foundit** | ⭐⭐⭐ | Has JSON API |
| **Glassdoor** | ⭐⭐ | Heavy JS, limited results |
| **Internshala** | ⭐⭐⭐⭐ | Good for entry-level |
| **Instahyre** | ⭐⭐⭐ | Startup jobs |
| **Wellfound** | ⭐⭐ | Heavy JS rendering |
| **Cutshort** | ⭐⭐⭐ | Tech-focused |

---

## How to Get More Jobs

### Option 1: Run Multiple Times
Run the scraper at different times of day. Some sources work better at off-peak hours.

### Option 2: Use Specific Sources
Instead of "all", select specific sources that work well:
```json
{
  "locations": ["Bangalore", "Mumbai"],
  "sources": ["naukri", "timesjobs", "foundit", "internshala"],
  "pages": 5
}
```

### Option 3: Add More Locations
More locations = more results:
```json
{
  "locations": ["Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai", "India"],
  "sources": ["all"],
  "pages": 3
}
```

### Option 4: Self-Host with Proxy
For production use, consider:
- Rotating proxy services (Bright Data, ScraperAPI)
- VPN rotation
- Cloud instances in different regions

---

## Advanced: Adding New Sources

To add a new job source, add a method to `scraper.py`:

```python
def scrape_newsite(self, query: str, location: str, pages: int = 3) -> List[Dict]:
    jobs = []
    logger.info(f"[NewSite] Scraping: {query} in {location}")
    
    for page in range(pages):
        try:
            url = f"https://newsite.com/jobs?q={quote(query)}&l={quote(location)}&page={page}"
            
            response = self._make_request(url)
            if not response:
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find job cards - use multiple selectors
            cards = (
                soup.find_all('div', class_='job-card') or
                soup.find_all('li', class_='job-listing') or
                soup.find_all('article')
            )
            
            for card in cards:
                try:
                    # Extract title
                    title_elem = card.find('h2') or card.find('h3') or card.find('a', class_='title')
                    if not title_elem:
                        continue
                    
                    title = self._clean(title_elem.text)
                    if not self._is_pm_job(title):
                        continue
                    
                    # Extract other fields...
                    company_elem = card.find('span', class_='company')
                    
                    jobs.append({
                        'title': title,
                        'company': self._clean(company_elem.text) if company_elem else '',
                        'location': location,
                        'url': '',
                        'source': 'NewSite',
                    })
                except:
                    continue
            
            self._smart_delay()
            
        except Exception as e:
            logger.error(f"[NewSite] Error: {e}")
    
    return jobs
```

Then add it to the `available_sources` dict in `scrape_all()`.

---

## Why Some Sites ALWAYS Fail

### LinkedIn
- Heavy bot detection
- Requires authentication for full results
- Public API is limited

### Indeed
- Very aggressive anti-scraping
- Serves different content to bots
- Frequently changes HTML

### Glassdoor
- Most content loaded via JavaScript
- Requires cookies/session
- Login wall after few pages

---

## Production Recommendations

For a real job aggregator, consider:

1. **Use Official APIs** - LinkedIn, Indeed, Glassdoor have partner APIs (paid)
2. **Job Board Aggregators** - Services like Adzuna, The Muse have APIs
3. **Google Jobs API** - Aggregates from many sources
4. **RSS Feeds** - Some company career pages have RSS
5. **Headless Browser** - Playwright/Puppeteer for JS-heavy sites

---

## Quick Debugging

If scraping returns 0 jobs:

1. **Check the logs** - Look for status codes (403 = blocked, 429 = rate limited)
2. **Test the URL manually** - Open in browser, is the data there?
3. **Check HTML structure** - Websites may have changed their layout
4. **Try different location** - Some locations have more jobs
5. **Reduce pages** - Start with 1-2 pages to test
