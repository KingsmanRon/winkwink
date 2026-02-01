"""
LinkedIn Jobs Crawler

Crawler for LinkedIn job postings.
Note: LinkedIn heavily restricts scraping. This module provides both
API-based access (requires authentication) and a basic scraping fallback.
"""

import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
from urllib.parse import urlencode, quote_plus
import logging

from .base import BaseCrawler, JobPosting, CrawlConfig

logger = logging.getLogger(__name__)


class LinkedInCrawler(BaseCrawler):
    """
    LinkedIn Jobs crawler.

    LinkedIn has aggressive anti-scraping measures. This crawler:
    1. Uses public job search pages (may be blocked)
    2. Respects rate limits strictly
    3. Provides fallback to job search API if credentials provided

    For production use, consider LinkedIn's official Hiring API.
    """

    def __init__(self, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=0.5))  # Very conservative
        self._api_token: Optional[str] = None

    @property
    def source_name(self) -> str:
        return "linkedin"

    @property
    def base_url(self) -> str:
        return "https://www.linkedin.com"

    def set_api_token(self, token: str):
        """Set LinkedIn API token for authenticated access."""
        self._api_token = token

    async def search_jobs(
        self,
        keywords: List[str],
        location: Optional[str] = None,
        remote_only: bool = False,
        job_type: Optional[str] = None,
        experience_level: Optional[str] = None,
        max_pages: int = 5,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """
        Search LinkedIn jobs.

        Args:
            keywords: Search keywords
            location: Location filter
            remote_only: Only remote jobs
            job_type: fulltime, contract, etc.
            experience_level: entry, mid, senior, director
            max_pages: Maximum pages to crawl

        Yields:
            JobPosting objects
        """
        keyword_str = " ".join(keywords)

        # Build search URL
        params = {
            "keywords": keyword_str,
            "trk": "public_jobs_jobs-search-bar_search-submit",
            "position": 1,
            "pageNum": 0,
        }

        if location:
            params["location"] = location

        if remote_only:
            params["f_WT"] = "2"  # Remote filter

        # Experience level filter
        exp_map = {
            "entry": "1",
            "associate": "2",
            "mid": "3",
            "senior": "4",
            "director": "5",
            "executive": "6"
        }
        if experience_level and experience_level in exp_map:
            params["f_E"] = exp_map[experience_level]

        for page in range(max_pages):
            params["start"] = page * 25

            url = f"{self.base_url}/jobs/search?" + urlencode(params)
            logger.info(f"Crawling LinkedIn page {page + 1}: {url}")

            html = await self.fetch(url)
            if not html:
                logger.warning(f"Failed to fetch LinkedIn page {page + 1}")
                break

            jobs = await self.parse_job_listing(html, url)

            if not jobs:
                logger.info("No more jobs found, stopping pagination")
                break

            for job in jobs:
                yield job

            # Extra delay for LinkedIn
            await asyncio.sleep(2)

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings from LinkedIn search results."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # LinkedIn job cards have various class patterns
            job_cards = soup.select("div.base-card, div.job-card-container, li.jobs-search-results__list-item")

            for card in job_cards:
                try:
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Error parsing job card: {e}")
                    continue

        except ImportError:
            logger.error("BeautifulSoup required for LinkedIn parsing: pip install beautifulsoup4")

        return jobs

    def _parse_job_card(self, card) -> Optional[JobPosting]:
        """Parse individual job card."""
        # Title
        title_elem = card.select_one("h3.base-search-card__title, a.job-card-list__title")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)

        # Company
        company_elem = card.select_one("h4.base-search-card__subtitle, a.job-card-container__company-name")
        company = company_elem.get_text(strip=True) if company_elem else "Unknown"

        # Location
        location_elem = card.select_one("span.job-search-card__location")
        location = location_elem.get_text(strip=True) if location_elem else ""

        # URL
        link_elem = card.select_one("a.base-card__full-link, a.job-card-list__title")
        job_url = link_elem.get("href", "") if link_elem else ""
        if job_url and not job_url.startswith("http"):
            job_url = self.base_url + job_url

        # Date
        date_elem = card.select_one("time.job-search-card__listdate")
        posting_date = None
        if date_elem:
            datetime_str = date_elem.get("datetime")
            if datetime_str:
                posting_date = datetime_str

        # Generate ID
        job_id = JobPosting.generate_id(title, company, job_url)

        # Detect remote
        remote_policy = ""
        if "remote" in location.lower():
            remote_policy = "remote"
        elif "hybrid" in location.lower():
            remote_policy = "hybrid"

        return JobPosting(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            remote_policy=remote_policy,
            application_url=job_url,
            posting_date=posting_date,
            source=self.source_name,
            crawled_at=datetime.now().isoformat(),
            company_type=self.classify_company_type(company)
        )

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse full job details from individual job page."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_elem = soup.select_one("h1.top-card-layout__title, h2.top-card-layout__title")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Company
            company_elem = soup.select_one("a.topcard__org-name-link, span.topcard__flavor")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Location
            location_elem = soup.select_one("span.topcard__flavor--bullet")
            location = location_elem.get_text(strip=True) if location_elem else ""

            # Description
            desc_elem = soup.select_one("div.show-more-less-html__markup, div.description__text")
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Extract requirements
            requirements, nice_to_have = self.extract_requirements(description)

            # Extract salary
            salary_info = self.extract_salary(str(soup))

            # Generate ID
            job_id = JobPosting.generate_id(title, company, url)

            return JobPosting(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                description_full=description,
                requirements=requirements,
                nice_to_have=nice_to_have,
                salary_min=salary_info["min"],
                salary_max=salary_info["max"],
                salary_currency=salary_info["currency"],
                salary_period=salary_info["period"],
                remote_policy=self.extract_remote_policy(description),
                application_url=url,
                source=self.source_name,
                crawled_at=datetime.now().isoformat(),
                company_type=self.classify_company_type(company, description)
            )

        except ImportError:
            logger.error("BeautifulSoup required: pip install beautifulsoup4")

        return None

    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """Fetch and parse full job details."""
        html = await self.fetch(job_url)
        if html:
            return await self.parse_job_detail(html, job_url)
        return None

    async def search_by_company(
        self,
        company_name: str,
        keywords: Optional[List[str]] = None,
        max_pages: int = 3
    ) -> AsyncGenerator[JobPosting, None]:
        """Search jobs at a specific company."""
        search_keywords = [company_name]
        if keywords:
            search_keywords.extend(keywords)

        async for job in self.search_jobs(
            keywords=search_keywords,
            max_pages=max_pages
        ):
            if company_name.lower() in job.company.lower():
                yield job
