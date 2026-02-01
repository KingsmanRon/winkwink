"""
Indeed Jobs Crawler

Crawler for Indeed job postings using public search pages.
"""

import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
from urllib.parse import urlencode, quote_plus
import logging

from .base import BaseCrawler, JobPosting, CrawlConfig

logger = logging.getLogger(__name__)


class IndeedCrawler(BaseCrawler):
    """
    Indeed Jobs crawler.

    Crawls Indeed job search results and individual job pages.
    Respects robots.txt and implements polite crawling.
    """

    def __init__(self, config: Optional[CrawlConfig] = None, country: str = "com"):
        super().__init__(config or CrawlConfig(rate_limit=1.0))
        self.country = country
        self._base_url = f"https://www.indeed.{country}"

    @property
    def source_name(self) -> str:
        return "indeed"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def search_jobs(
        self,
        keywords: List[str],
        location: Optional[str] = None,
        remote_only: bool = False,
        salary_min: Optional[int] = None,
        job_type: Optional[str] = None,
        posted_within_days: int = 30,
        max_pages: int = 10,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """
        Search Indeed jobs.

        Args:
            keywords: Search keywords
            location: Location filter
            remote_only: Only remote jobs
            salary_min: Minimum salary filter
            job_type: fulltime, parttime, contract, temporary, internship
            posted_within_days: Max job age in days
            max_pages: Maximum pages to crawl

        Yields:
            JobPosting objects
        """
        keyword_str = " ".join(keywords)

        # Build search URL
        params = {
            "q": keyword_str,
            "sort": "date",
        }

        if location:
            params["l"] = location

        if remote_only:
            params["remotejob"] = "032b3046-06a3-4876-8dfd-474eb5e7ed11"

        # Date filter
        if posted_within_days <= 1:
            params["fromage"] = "1"
        elif posted_within_days <= 3:
            params["fromage"] = "3"
        elif posted_within_days <= 7:
            params["fromage"] = "7"
        elif posted_within_days <= 14:
            params["fromage"] = "14"

        # Job type
        job_type_map = {
            "fulltime": "fulltime",
            "parttime": "parttime",
            "contract": "contract",
            "temporary": "temporary",
            "internship": "internship"
        }
        if job_type and job_type in job_type_map:
            params["jt"] = job_type_map[job_type]

        for page in range(max_pages):
            params["start"] = page * 10

            url = f"{self.base_url}/jobs?" + urlencode(params)
            logger.info(f"Crawling Indeed page {page + 1}: {url}")

            html = await self.fetch(url)
            if not html:
                logger.warning(f"Failed to fetch Indeed page {page + 1}")
                break

            jobs = await self.parse_job_listing(html, url)

            if not jobs:
                logger.info("No more jobs found, stopping pagination")
                break

            for job in jobs:
                yield job

            # Polite delay
            await asyncio.sleep(1.5)

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings from Indeed search results."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Indeed job cards
            job_cards = soup.select("div.job_seen_beacon, div.jobsearch-ResultsList > div")

            for card in job_cards:
                try:
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Error parsing job card: {e}")
                    continue

            # Also try to extract from JSON-LD
            script_tags = soup.select('script[type="application/ld+json"]')
            for script in script_tags:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get("@type") == "JobPosting":
                                job = self._parse_json_ld(item)
                                if job:
                                    jobs.append(job)
                    elif data.get("@type") == "JobPosting":
                        job = self._parse_json_ld(data)
                        if job:
                            jobs.append(job)
                except Exception:
                    pass

        except ImportError:
            logger.error("BeautifulSoup required for Indeed parsing: pip install beautifulsoup4")

        # Deduplicate by job_id
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job.job_id not in seen:
                seen.add(job.job_id)
                unique_jobs.append(job)

        return unique_jobs

    def _parse_job_card(self, card) -> Optional[JobPosting]:
        """Parse individual job card."""
        # Title
        title_elem = card.select_one("h2.jobTitle span, a.jcs-JobTitle span")
        if not title_elem:
            title_elem = card.select_one("h2.jobTitle, a.jcs-JobTitle")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)

        # Company
        company_elem = card.select_one("span.companyName, span[data-testid='company-name']")
        company = company_elem.get_text(strip=True) if company_elem else "Unknown"

        # Location
        location_elem = card.select_one("div.companyLocation, div[data-testid='text-location']")
        location = location_elem.get_text(strip=True) if location_elem else ""

        # Salary
        salary_elem = card.select_one("div.salary-snippet-container, span.salary-snippet")
        salary_text = salary_elem.get_text(strip=True) if salary_elem else ""
        salary_info = self.extract_salary(salary_text)

        # URL
        link_elem = card.select_one("a[data-jk], a.jcs-JobTitle")
        job_key = ""
        if link_elem:
            job_key = link_elem.get("data-jk", "")
            if not job_key:
                href = link_elem.get("href", "")
                # Extract job key from URL
                match = re.search(r"jk=([a-f0-9]+)", href)
                if match:
                    job_key = match.group(1)

        job_url = f"{self.base_url}/viewjob?jk={job_key}" if job_key else ""

        # Generate ID
        job_id = job_key if job_key else JobPosting.generate_id(title, company, job_url)

        # Date - Indeed shows relative dates like "3 days ago"
        date_elem = card.select_one("span.date, span[data-testid='myJobsStateDate']")
        posting_date = None
        if date_elem:
            date_text = date_elem.get_text(strip=True).lower()
            posting_date = self._parse_relative_date(date_text)

        # Remote detection
        remote_policy = ""
        location_lower = location.lower()
        if "remote" in location_lower:
            remote_policy = "remote"
        elif "hybrid" in location_lower:
            remote_policy = "hybrid"

        # Job snippet/description
        snippet_elem = card.select_one("div.job-snippet, td.snip")
        description = snippet_elem.get_text(strip=True) if snippet_elem else ""

        return JobPosting(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            remote_policy=remote_policy,
            salary_min=salary_info["min"],
            salary_max=salary_info["max"],
            salary_currency=salary_info["currency"],
            salary_period=salary_info["period"],
            description_full=description,
            application_url=job_url,
            posting_date=posting_date,
            source=self.source_name,
            crawled_at=datetime.now().isoformat(),
            company_type=self.classify_company_type(company, description)
        )

    def _parse_json_ld(self, data: Dict[str, Any]) -> Optional[JobPosting]:
        """Parse job from JSON-LD structured data."""
        title = data.get("title", "")
        if not title:
            return None

        # Company
        hiring_org = data.get("hiringOrganization", {})
        company = hiring_org.get("name", "Unknown") if isinstance(hiring_org, dict) else "Unknown"

        # Location
        job_location = data.get("jobLocation", {})
        location = ""
        if isinstance(job_location, dict):
            address = job_location.get("address", {})
            if isinstance(address, dict):
                city = address.get("addressLocality", "")
                region = address.get("addressRegion", "")
                country = address.get("addressCountry", "")
                location = ", ".join(filter(None, [city, region, country]))

        # Salary
        base_salary = data.get("baseSalary", {})
        salary_min = None
        salary_max = None
        salary_currency = "USD"
        if isinstance(base_salary, dict):
            salary_currency = base_salary.get("currency", "USD")
            value = base_salary.get("value", {})
            if isinstance(value, dict):
                salary_min = value.get("minValue")
                salary_max = value.get("maxValue")

        # Description
        description = data.get("description", "")

        # URL
        job_url = data.get("url", "")

        # Date
        posting_date = data.get("datePosted")

        # Generate ID
        job_id = JobPosting.generate_id(title, company, job_url)

        return JobPosting(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            salary_min=int(salary_min) if salary_min else None,
            salary_max=int(salary_max) if salary_max else None,
            salary_currency=salary_currency,
            description_full=description,
            application_url=job_url,
            posting_date=posting_date,
            source=self.source_name,
            crawled_at=datetime.now().isoformat(),
            company_type=self.classify_company_type(company, description)
        )

    def _parse_relative_date(self, text: str) -> Optional[str]:
        """Convert relative date to ISO format."""
        today = datetime.now()

        if "today" in text or "just posted" in text:
            return today.isoformat()
        elif "yesterday" in text:
            return (today - timedelta(days=1)).isoformat()

        # Match patterns like "3 days ago"
        match = re.search(r"(\d+)\s*(day|hour|week|month)", text)
        if match:
            num = int(match.group(1))
            unit = match.group(2)

            if "hour" in unit:
                return today.isoformat()
            elif "day" in unit:
                return (today - timedelta(days=num)).isoformat()
            elif "week" in unit:
                return (today - timedelta(weeks=num)).isoformat()
            elif "month" in unit:
                return (today - timedelta(days=num * 30)).isoformat()

        return None

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse full job details from individual job page."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_elem = soup.select_one("h1.jobsearch-JobInfoHeader-title")
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)

            # Company
            company_elem = soup.select_one("div[data-company-name] a, div.jobsearch-InlineCompanyRating a")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Location
            location_elem = soup.select_one("div[data-testid='inlineHeader-companyLocation']")
            location = location_elem.get_text(strip=True) if location_elem else ""

            # Description
            desc_elem = soup.select_one("div#jobDescriptionText, div.jobsearch-jobDescriptionText")
            description = desc_elem.get_text("\n", strip=True) if desc_elem else ""

            # Extract requirements
            requirements, nice_to_have = self.extract_requirements(description)

            # Extract salary from page
            salary_elem = soup.select_one("span[data-testid='attribute_snippet_testid']")
            salary_text = salary_elem.get_text(strip=True) if salary_elem else ""
            salary_info = self.extract_salary(salary_text)

            # Job key from URL
            match = re.search(r"jk=([a-f0-9]+)", url)
            job_id = match.group(1) if match else JobPosting.generate_id(title, company, url)

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
                remote_policy=self.extract_remote_policy(description + " " + location),
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
