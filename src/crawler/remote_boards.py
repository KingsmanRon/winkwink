"""
Remote Job Boards Crawler

Crawler for remote-first job boards like WeWorkRemotely, RemoteOK, etc.
"""

import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
from urllib.parse import urlencode
import logging

from .base import BaseCrawler, JobPosting, CrawlConfig

logger = logging.getLogger(__name__)


class RemoteOKCrawler(BaseCrawler):
    """Crawler for RemoteOK.io job board."""

    def __init__(self, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=1.0))

    @property
    def source_name(self) -> str:
        return "remoteok"

    @property
    def base_url(self) -> str:
        return "https://remoteok.io"

    @property
    def api_url(self) -> str:
        return "https://remoteok.io/api"

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """
        Fetch jobs from RemoteOK.

        Args:
            keywords: Search keywords to filter by
            tags: Category tags (e.g., 'devops', 'cloud', 'engineer')

        Yields:
            JobPosting objects
        """
        # RemoteOK provides a simple JSON API
        json_data = await self.fetch_json(self.api_url)

        if not json_data:
            logger.warning("Failed to fetch RemoteOK jobs")
            return

        # First item is legal info, skip it
        if isinstance(json_data, list) and len(json_data) > 0:
            jobs_data = json_data[1:] if isinstance(json_data[0], dict) and "legal" in str(json_data[0]) else json_data
        else:
            jobs_data = []

        for job_data in jobs_data:
            if not isinstance(job_data, dict):
                continue

            job = self._parse_job(job_data)
            if not job:
                continue

            # Filter by keywords
            if keywords:
                job_text = f"{job.title} {job.description_full}".lower()
                if not any(kw.lower() in job_text for kw in keywords):
                    continue

            # Filter by tags
            if tags:
                job_tags = job_data.get("tags", [])
                if isinstance(job_tags, list):
                    job_tags_lower = [t.lower() for t in job_tags]
                    if not any(tag.lower() in job_tags_lower for tag in tags):
                        continue

            yield job

    def _parse_job(self, data: Dict[str, Any]) -> Optional[JobPosting]:
        """Parse job from RemoteOK API response."""
        position = data.get("position", "")
        if not position:
            return None

        job_id = str(data.get("id", ""))
        company = data.get("company", "Unknown")
        location = data.get("location", "Remote")

        # Description
        description = data.get("description", "")

        # Salary
        salary_min = data.get("salary_min")
        salary_max = data.get("salary_max")

        # URL
        url = data.get("url", "")
        if not url.startswith("http"):
            url = f"{self.base_url}/@{data.get('slug', job_id)}"

        # Date
        date_str = data.get("date")

        # Tags
        tags = data.get("tags", [])

        return JobPosting(
            job_id=job_id,
            title=position,
            company=company,
            location=location,
            remote_policy="remote",
            salary_min=int(salary_min) if salary_min else None,
            salary_max=int(salary_max) if salary_max else None,
            salary_currency="USD",
            salary_period="yearly",
            description_full=description,
            application_url=url,
            posting_date=date_str,
            source=self.source_name,
            crawled_at=datetime.now().isoformat(),
            company_type=self.classify_company_type(company, description)
        )

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Not used for API-based crawler."""
        return []

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Not used for API-based crawler."""
        return None


class WeWorkRemotelyCrawler(BaseCrawler):
    """Crawler for WeWorkRemotely job board."""

    def __init__(self, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=1.0))

    @property
    def source_name(self) -> str:
        return "weworkremotely"

    @property
    def base_url(self) -> str:
        return "https://weworkremotely.com"

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """
        Fetch jobs from WeWorkRemotely.

        Args:
            keywords: Search keywords to filter by
            category: Job category (devops-sysadmin, programming, etc.)

        Yields:
            JobPosting objects
        """
        # Categories to crawl
        categories = {
            "devops-sysadmin": "/categories/devops-sysadmin/jobs",
            "programming": "/categories/remote-programming-jobs",
            "full-stack": "/categories/remote-full-stack-programming-jobs",
            "back-end": "/categories/remote-back-end-programming-jobs",
        }

        urls_to_crawl = []
        if category and category in categories:
            urls_to_crawl.append(categories[category])
        else:
            urls_to_crawl = list(categories.values())

        for path in urls_to_crawl:
            url = f"{self.base_url}{path}"
            logger.info(f"Crawling WeWorkRemotely: {url}")

            html = await self.fetch(url)
            if not html:
                continue

            jobs = await self.parse_job_listing(html, url)

            for job in jobs:
                if keywords:
                    job_text = f"{job.title} {job.company}".lower()
                    if not any(kw.lower() in job_text for kw in keywords):
                        continue
                yield job

            await asyncio.sleep(1)

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings from WeWorkRemotely page."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            job_items = soup.select("li.feature, li.new, section.jobs > article > ul > li")

            for item in job_items:
                link = item.select_one("a")
                if not link:
                    continue

                href = link.get("href", "")
                if not href or "categories" in href:
                    continue

                # Title
                title_elem = item.select_one("span.title")
                title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)

                if not title or len(title) < 5:
                    continue

                # Company
                company_elem = item.select_one("span.company")
                company = company_elem.get_text(strip=True) if company_elem else "Unknown"

                # Make absolute URL
                job_url = href if href.startswith("http") else f"{self.base_url}{href}"

                # Region
                region_elem = item.select_one("span.region")
                location = region_elem.get_text(strip=True) if region_elem else "Remote"

                job_id = JobPosting.generate_id(title, company, job_url)

                jobs.append(JobPosting(
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    remote_policy="remote",
                    application_url=job_url,
                    source=self.source_name,
                    crawled_at=datetime.now().isoformat(),
                    company_type=self.classify_company_type(company)
                ))

        except ImportError:
            logger.error("BeautifulSoup required: pip install beautifulsoup4")

        return jobs

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse job detail page."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_elem = soup.select_one("h1.listing-header-container")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Company
            company_elem = soup.select_one("h2.company-name, a.company-name")
            company = company_elem.get_text(strip=True) if company_elem else ""

            # Description
            desc_elem = soup.select_one("div.listing-container")
            description = desc_elem.get_text("\n", strip=True) if desc_elem else ""

            requirements, nice_to_have = self.extract_requirements(description)

            return JobPosting(
                job_id=JobPosting.generate_id(title, company, url),
                title=title,
                company=company,
                remote_policy="remote",
                description_full=description,
                requirements=requirements,
                nice_to_have=nice_to_have,
                application_url=url,
                source=self.source_name,
                crawled_at=datetime.now().isoformat(),
                company_type=self.classify_company_type(company, description)
            )

        except ImportError:
            pass

        return None


class WellfoundCrawler(BaseCrawler):
    """Crawler for Wellfound (formerly AngelList) job board."""

    def __init__(self, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=0.5))

    @property
    def source_name(self) -> str:
        return "wellfound"

    @property
    def base_url(self) -> str:
        return "https://wellfound.com"

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        role: Optional[str] = None,
        remote_only: bool = True,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """
        Search Wellfound jobs.

        Note: Wellfound uses heavy JavaScript rendering, so results may be limited.
        """
        # Build search URL
        role_slug = role.lower().replace(" ", "-") if role else "devops-engineer"
        url = f"{self.base_url}/role/{role_slug}"

        if remote_only:
            url += "?remote=true"

        logger.info(f"Crawling Wellfound: {url}")

        html = await self.fetch(url)
        if not html:
            logger.warning("Failed to fetch Wellfound jobs")
            return

        jobs = await self.parse_job_listing(html, url)

        for job in jobs:
            if keywords:
                job_text = f"{job.title} {job.company}".lower()
                if not any(kw.lower() in job_text for kw in keywords):
                    continue
            yield job

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings from Wellfound page."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Wellfound uses React, so we look for any job-related elements
            job_cards = soup.select("div[data-test='StartupResult'], div.job-listing")

            for card in job_cards:
                title_elem = card.select_one("h3, a.job-title")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                company_elem = card.select_one("h2, span.company-name")
                company = company_elem.get_text(strip=True) if company_elem else "Unknown"

                link = card.select_one("a[href*='/jobs/']")
                job_url = link.get("href", "") if link else ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"{self.base_url}{job_url}"

                salary_elem = card.select_one("span.salary, div.compensation")
                salary_text = salary_elem.get_text(strip=True) if salary_elem else ""
                salary_info = self.extract_salary(salary_text)

                job_id = JobPosting.generate_id(title, company, job_url)

                jobs.append(JobPosting(
                    job_id=job_id,
                    title=title,
                    company=company,
                    salary_min=salary_info["min"],
                    salary_max=salary_info["max"],
                    salary_currency=salary_info["currency"],
                    application_url=job_url,
                    source=self.source_name,
                    crawled_at=datetime.now().isoformat(),
                    company_type=self.classify_company_type(company)
                ))

        except ImportError:
            logger.error("BeautifulSoup required: pip install beautifulsoup4")

        return jobs

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse job detail page."""
        return None  # Wellfound is heavily JS-rendered


class LevelsFYICrawler(BaseCrawler):
    """Crawler for Levels.fyi job board with salary data."""

    def __init__(self, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=1.0))

    @property
    def source_name(self) -> str:
        return "levelsfyi"

    @property
    def base_url(self) -> str:
        return "https://www.levels.fyi"

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        min_salary: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """Search Levels.fyi jobs."""
        url = f"{self.base_url}/jobs"

        logger.info(f"Crawling Levels.fyi: {url}")

        html = await self.fetch(url)
        if not html:
            logger.warning("Failed to fetch Levels.fyi jobs")
            return

        jobs = await self.parse_job_listing(html, url)

        for job in jobs:
            if keywords:
                job_text = f"{job.title} {job.company}".lower()
                if not any(kw.lower() in job_text for kw in keywords):
                    continue

            if min_salary and job.salary_min and job.salary_min < min_salary:
                continue

            yield job

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings from Levels.fyi."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Look for job cards
            job_cards = soup.select("div.job-card, tr.job-row, div[data-job-id]")

            for card in job_cards:
                title_elem = card.select_one("h3, a.job-title, span.title")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                company_elem = card.select_one("span.company, a.company-link")
                company = company_elem.get_text(strip=True) if company_elem else "Unknown"

                salary_elem = card.select_one("span.salary, div.compensation")
                salary_text = salary_elem.get_text(strip=True) if salary_elem else ""
                salary_info = self.extract_salary(salary_text)

                location_elem = card.select_one("span.location")
                location = location_elem.get_text(strip=True) if location_elem else ""

                link = card.select_one("a[href*='/jobs/']")
                job_url = link.get("href", "") if link else ""
                if job_url and not job_url.startswith("http"):
                    job_url = f"{self.base_url}{job_url}"

                job_id = JobPosting.generate_id(title, company, job_url)

                jobs.append(JobPosting(
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    salary_min=salary_info["min"],
                    salary_max=salary_info["max"],
                    salary_currency=salary_info["currency"],
                    salary_period=salary_info["period"],
                    application_url=job_url,
                    source=self.source_name,
                    crawled_at=datetime.now().isoformat(),
                    company_type=self.classify_company_type(company)
                ))

        except ImportError:
            logger.error("BeautifulSoup required: pip install beautifulsoup4")

        return jobs

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse job detail page."""
        return None
