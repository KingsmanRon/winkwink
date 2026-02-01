"""
Base Crawler Module

Abstract base class for job crawlers with common functionality for polite crawling,
rate limiting, and result parsing.
"""

import asyncio
import hashlib
import random
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator
from urllib.parse import urlparse, urljoin
from pathlib import Path
import re

import aiohttp

logger = logging.getLogger(__name__)


# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@dataclass
class JobPosting:
    """Structured job posting data."""

    job_id: str
    title: str
    company: str
    company_type: str = ""
    location: str = ""
    remote_policy: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    salary_period: str = "yearly"
    requirements: List[str] = field(default_factory=list)
    nice_to_have: List[str] = field(default_factory=list)
    description_full: str = ""
    application_url: str = ""
    posting_date: Optional[str] = None
    source: str = ""
    crawled_at: Optional[str] = None
    match_score: Optional[float] = None
    status: str = "new"
    applied_date: Optional[str] = None
    next_action: str = ""
    notes: str = ""
    contacts: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @staticmethod
    def generate_id(title: str, company: str, url: str = "") -> str:
        """Generate unique job ID."""
        content = f"{title.lower().strip()}|{company.lower().strip()}|{url}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class CrawlConfig:
    """Configuration for crawler behavior."""

    rate_limit: float = 1.0  # Requests per second
    max_retries: int = 3
    timeout: int = 30
    respect_robots_txt: bool = True
    max_pages: int = 10
    headers: Dict[str, str] = field(default_factory=dict)


class RateLimiter:
    """Rate limiter for polite crawling."""

    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait for rate limit before allowing request."""
        async with self._lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


class BaseCrawler(ABC):
    """Abstract base class for job crawlers."""

    def __init__(self, config: Optional[CrawlConfig] = None):
        self.config = config or CrawlConfig()
        self.rate_limiter = RateLimiter(self.config.rate_limit)
        self._session: Optional[aiohttp.ClientSession] = None
        self._robots_cache: Dict[str, Dict] = {}

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of this job source."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for this job source."""
        pass

    @abstractmethod
    async def search_jobs(
        self,
        keywords: List[str],
        location: Optional[str] = None,
        remote_only: bool = False,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """
        Search for jobs matching criteria.

        Args:
            keywords: Search keywords
            location: Location filter
            remote_only: Only return remote jobs

        Yields:
            JobPosting objects
        """
        pass

    @abstractmethod
    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings from page HTML."""
        pass

    @abstractmethod
    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse job details from individual job page."""
        pass

    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(USER_AGENTS)

    def get_headers(self) -> Dict[str, str]:
        """Get request headers with random user agent."""
        headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        headers.update(self.config.headers)
        return headers

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch(self, url: str, retry: int = 0) -> Optional[str]:
        """
        Fetch URL content with rate limiting and retries.

        Args:
            url: URL to fetch
            retry: Current retry count

        Returns:
            HTML content or None on failure
        """
        # Check robots.txt first
        if self.config.respect_robots_txt:
            if not await self._can_fetch(url):
                logger.warning(f"Blocked by robots.txt: {url}")
                return None

        # Rate limit
        await self.rate_limiter.acquire()

        try:
            session = await self.get_session()
            async with session.get(url, headers=self.get_headers()) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:  # Rate limited
                    if retry < self.config.max_retries:
                        wait_time = 2 ** retry + random.uniform(0, 1)
                        logger.warning(f"Rate limited, waiting {wait_time:.1f}s before retry")
                        await asyncio.sleep(wait_time)
                        return await self.fetch(url, retry + 1)
                elif response.status >= 500:  # Server error
                    if retry < self.config.max_retries:
                        wait_time = 2 ** retry
                        logger.warning(f"Server error {response.status}, retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        return await self.fetch(url, retry + 1)
                else:
                    logger.error(f"HTTP {response.status} for {url}")

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
            if retry < self.config.max_retries:
                return await self.fetch(url, retry + 1)
        except aiohttp.ClientError as e:
            logger.error(f"Client error fetching {url}: {e}")
            if retry < self.config.max_retries:
                return await self.fetch(url, retry + 1)

        return None

    async def fetch_json(self, url: str, retry: int = 0) -> Optional[Dict[str, Any]]:
        """Fetch and parse JSON from URL."""
        await self.rate_limiter.acquire()

        try:
            session = await self.get_session()
            headers = self.get_headers()
            headers["Accept"] = "application/json"

            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429 and retry < self.config.max_retries:
                    wait_time = 2 ** retry + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)
                    return await self.fetch_json(url, retry + 1)

        except Exception as e:
            logger.error(f"Error fetching JSON from {url}: {e}")

        return None

    async def _can_fetch(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._robots_cache:
            robots_url = urljoin(domain, "/robots.txt")
            try:
                session = await self.get_session()
                async with session.get(robots_url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        self._robots_cache[domain] = self._parse_robots(content)
                    else:
                        self._robots_cache[domain] = {"allow_all": True}
            except Exception:
                self._robots_cache[domain] = {"allow_all": True}

        robots = self._robots_cache.get(domain, {"allow_all": True})

        if robots.get("allow_all"):
            return True

        path = parsed.path
        for disallow in robots.get("disallow", []):
            if path.startswith(disallow):
                return False

        return True

    def _parse_robots(self, content: str) -> Dict:
        """Simple robots.txt parser."""
        result = {"disallow": [], "allow_all": False}
        current_agent = None

        for line in content.split("\n"):
            line = line.strip().lower()

            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                current_agent = agent

            elif line.startswith("disallow:") and current_agent in ["*", None]:
                path = line.split(":", 1)[1].strip()
                if path:
                    result["disallow"].append(path)

        if not result["disallow"]:
            result["allow_all"] = True

        return result

    def extract_salary(self, text: str) -> Dict[str, Optional[int]]:
        """
        Extract salary information from text.

        Returns:
            Dict with 'min', 'max', 'currency', 'period'
        """
        result = {
            "min": None,
            "max": None,
            "currency": "USD",
            "period": "yearly"
        }

        # Normalize text
        text = text.lower().replace(",", "").replace(" ", "")

        # Currency detection
        if "€" in text or "eur" in text:
            result["currency"] = "EUR"
        elif "£" in text or "gbp" in text:
            result["currency"] = "GBP"
        elif "$" in text or "usd" in text:
            result["currency"] = "USD"

        # Period detection
        if any(x in text for x in ["hour", "/hr", "perhour"]):
            result["period"] = "hourly"
        elif any(x in text for x in ["month", "/mo", "permonth"]):
            result["period"] = "monthly"
        else:
            result["period"] = "yearly"

        # Extract salary numbers
        patterns = [
            r"(\d{3,})k?\s*[-–to]+\s*(\d{3,})k?",  # Range: 150-200 or 150k-200k
            r"(\d{3,})k",  # Single with k: 150k
            r"\$(\d{3,})",  # Dollar amount: $150000
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) >= 2 and groups[1]:
                    min_val = int(groups[0])
                    max_val = int(groups[1])
                    if min_val < 1000:
                        min_val *= 1000
                    if max_val < 1000:
                        max_val *= 1000
                    result["min"] = min_val
                    result["max"] = max_val
                elif len(groups) >= 1:
                    val = int(groups[0])
                    if val < 1000:
                        val *= 1000
                    result["min"] = val
                    result["max"] = val
                break

        return result

    def extract_remote_policy(self, text: str) -> str:
        """Extract remote work policy from text."""
        text_lower = text.lower()

        if any(x in text_lower for x in ["fully remote", "100% remote", "work from anywhere", "remote only"]):
            return "remote"
        elif any(x in text_lower for x in ["hybrid", "flexible", "2-3 days", "part remote"]):
            return "hybrid"
        elif any(x in text_lower for x in ["on-site", "onsite", "in-office", "office-based"]):
            return "onsite"
        elif "remote" in text_lower:
            return "remote"

        return ""

    def extract_requirements(self, text: str) -> tuple[List[str], List[str]]:
        """
        Extract requirements and nice-to-haves from job description.

        Returns:
            Tuple of (required skills, nice-to-have skills)
        """
        requirements = []
        nice_to_have = []

        lines = text.split("\n")
        current_section = None

        for line in lines:
            line_lower = line.lower().strip()

            # Detect section headers
            if any(x in line_lower for x in ["requirements", "qualifications", "must have", "required"]):
                current_section = "required"
                continue
            elif any(x in line_lower for x in ["nice to have", "preferred", "bonus", "plus", "ideal"]):
                current_section = "nice_to_have"
                continue

            # Extract bullet points
            if line.strip().startswith(("-", "•", "*", "·")):
                item = line.strip()[1:].strip()
                if len(item) > 10 and len(item) < 200:
                    if current_section == "nice_to_have":
                        nice_to_have.append(item)
                    elif current_section == "required":
                        requirements.append(item)

        return requirements, nice_to_have

    def classify_company_type(self, company: str, description: str = "") -> str:
        """Classify company into predefined categories."""
        company_lower = company.lower()
        desc_lower = description.lower()

        # Fintech
        fintech_companies = ["stripe", "plaid", "revolut", "wise", "adyen", "square", "block",
                           "coinbase", "kraken", "robinhood", "affirm", "klarna", "nubank"]
        if any(c in company_lower for c in fintech_companies):
            return "fintech"

        # Quant
        quant_companies = ["jane street", "two sigma", "citadel", "de shaw", "jump trading",
                         "hudson river", "optiver", "imc", "virtu", "tower research"]
        if any(c in company_lower for c in quant_companies):
            return "quant"

        # AI companies
        ai_companies = ["anthropic", "openai", "nvidia", "deepmind", "cohere", "databricks",
                       "scale ai", "hugging face", "stability", "inflection", "mistral"]
        if any(c in company_lower for c in ai_companies):
            return "ai_native"

        # Big tech
        big_tech = ["google", "microsoft", "amazon", "meta", "apple", "netflix", "uber", "airbnb", "spotify"]
        if any(c in company_lower for c in big_tech):
            return "big_tech"

        # Cloud vendors
        cloud_vendors = ["aws", "azure", "hashicorp", "snowflake", "datadog", "mongodb",
                        "confluent", "elastic", "cloudflare", "vercel"]
        if any(c in company_lower for c in cloud_vendors):
            return "cloud_vendor"

        # Consulting
        consulting = ["deloitte", "accenture", "mckinsey", "bcg", "slalom", "thoughtworks", "epam"]
        if any(c in company_lower for c in consulting):
            return "consulting"

        # Check description for hints
        if any(x in desc_lower for x in ["trading", "quant", "hedge fund"]):
            return "quant"
        if any(x in desc_lower for x in ["ai", "machine learning", "llm"]):
            return "ai_native"
        if any(x in desc_lower for x in ["fintech", "payments", "banking"]):
            return "fintech"

        return ""

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
