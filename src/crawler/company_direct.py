"""
Company Direct Crawler

Crawler for company career pages, including Greenhouse and Lever boards.
"""

import re
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator
from urllib.parse import urljoin, urlparse
import logging

from .base import BaseCrawler, JobPosting, CrawlConfig

logger = logging.getLogger(__name__)


# Known company career page patterns
COMPANY_CAREER_URLS = {
    # AI Companies
    "anthropic": "https://www.anthropic.com/careers#open-roles",
    "openai": "https://openai.com/careers#open-roles",
    "nvidia": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
    "deepmind": "https://www.deepmind.com/careers",
    "cohere": "https://jobs.lever.co/cohere",
    "databricks": "https://www.databricks.com/company/careers/open-positions",
    "scale_ai": "https://scale.com/careers",
    "hugging_face": "https://apply.workable.com/huggingface/",
    "stability_ai": "https://stability.ai/careers",
    "mistral_ai": "https://mistral.ai/careers/",
    "perplexity": "https://www.perplexity.ai/hub/careers",
    "together_ai": "https://www.together.ai/careers",
    "anyscale": "https://www.anyscale.com/careers#jobs",
    "modal": "https://modal.com/careers",
    "replicate": "https://replicate.com/about#careers",

    # Quant/Trading
    "jane_street": "https://www.janestreet.com/join-jane-street/open-roles/",
    "two_sigma": "https://www.twosigma.com/careers/",
    "citadel": "https://www.citadel.com/careers/open-positions/",
    "de_shaw": "https://www.deshaw.com/careers",
    "jump_trading": "https://www.jumptrading.com/careers/",
    "hudson_river": "https://www.hudsonrivertrading.com/careers/",
    "optiver": "https://optiver.com/working-at-optiver/career-opportunities/",
    "imc_trading": "https://careers.imc.com/",
    "akuna_capital": "https://akunacapital.com/careers",
    "drw": "https://drw.com/careers/",

    # Fintech
    "stripe": "https://stripe.com/jobs/search",
    "plaid": "https://plaid.com/careers/",
    "revolut": "https://www.revolut.com/careers/",
    "wise": "https://www.wise.jobs/search/",
    "adyen": "https://careers.adyen.com/vacancies",
    "coinbase": "https://www.coinbase.com/careers/positions",
    "robinhood": "https://robinhood.com/us/en/careers/openings/",
    "affirm": "https://boards.greenhouse.io/affirm",
    "klarna": "https://jobs.lever.co/klarna",

    # Big Tech
    "google": "https://careers.google.com/jobs/results/",
    "microsoft": "https://careers.microsoft.com/us/en/search-results",
    "amazon": "https://www.amazon.jobs/en/search",
    "meta": "https://www.metacareers.com/jobs/",
    "apple": "https://jobs.apple.com/en-us/search",
    "netflix": "https://jobs.netflix.com/search",
    "uber": "https://www.uber.com/careers/list/",
    "airbnb": "https://careers.airbnb.com/positions/",
    "spotify": "https://www.lifeatspotify.com/jobs",
    "salesforce": "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site",

    # Cloud Vendors
    "hashicorp": "https://www.hashicorp.com/careers/open-positions",
    "snowflake": "https://careers.snowflake.com/us/en/search-results",
    "datadog": "https://careers.datadoghq.com/all-jobs/",
    "mongodb": "https://www.mongodb.com/careers",
    "confluent": "https://careers.confluent.io/search/",
    "elastic": "https://www.elastic.co/careers/jobs",
    "cloudflare": "https://www.cloudflare.com/careers/jobs/",
    "vercel": "https://vercel.com/careers",
    "supabase": "https://supabase.com/careers",
}


class GreenhouseCrawler(BaseCrawler):
    """Crawler for Greenhouse job boards."""

    def __init__(self, company_name: str, board_token: str, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=2.0))
        self.company_name = company_name
        self.board_token = board_token

    @property
    def source_name(self) -> str:
        return f"greenhouse_{self.company_name}"

    @property
    def base_url(self) -> str:
        return f"https://boards.greenhouse.io/{self.board_token}"

    @property
    def api_url(self) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs"

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        department: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """Fetch all jobs from Greenhouse board."""
        # Use Greenhouse API
        json_data = await self.fetch_json(self.api_url)

        if not json_data:
            logger.warning(f"Failed to fetch Greenhouse jobs for {self.company_name}")
            return

        jobs = json_data.get("jobs", [])

        for job_data in jobs:
            job = self._parse_job(job_data)
            if job:
                # Filter by keywords if provided
                if keywords:
                    title_lower = job.title.lower()
                    if not any(kw.lower() in title_lower for kw in keywords):
                        continue

                # Filter by department if provided
                if department and department.lower() not in job.location.lower():
                    continue

                yield job

    def _parse_job(self, data: Dict[str, Any]) -> Optional[JobPosting]:
        """Parse job from Greenhouse API response."""
        title = data.get("title", "")
        if not title:
            return None

        job_id = str(data.get("id", ""))

        # Location
        location_data = data.get("location", {})
        location = location_data.get("name", "") if isinstance(location_data, dict) else str(location_data)

        # Department
        departments = data.get("departments", [])
        department = departments[0].get("name", "") if departments else ""

        # URL
        absolute_url = data.get("absolute_url", "")

        # Updated date
        updated_at = data.get("updated_at", "")

        return JobPosting(
            job_id=job_id,
            title=title,
            company=self.company_name,
            location=location,
            application_url=absolute_url,
            posting_date=updated_at,
            source=self.source_name,
            crawled_at=datetime.now().isoformat(),
            company_type=self.classify_company_type(self.company_name)
        )

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings (not used for API)."""
        return []

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse job details from page."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_elem = soup.select_one("h1.app-title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Description
            desc_elem = soup.select_one("div#content")
            description = desc_elem.get_text("\n", strip=True) if desc_elem else ""

            # Location
            location_elem = soup.select_one("div.location")
            location = location_elem.get_text(strip=True) if location_elem else ""

            requirements, nice_to_have = self.extract_requirements(description)

            return JobPosting(
                job_id=JobPosting.generate_id(title, self.company_name, url),
                title=title,
                company=self.company_name,
                location=location,
                description_full=description,
                requirements=requirements,
                nice_to_have=nice_to_have,
                remote_policy=self.extract_remote_policy(description + location),
                application_url=url,
                source=self.source_name,
                crawled_at=datetime.now().isoformat(),
                company_type=self.classify_company_type(self.company_name, description)
            )

        except ImportError:
            pass

        return None


class LeverCrawler(BaseCrawler):
    """Crawler for Lever job boards."""

    def __init__(self, company_name: str, lever_id: str, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=2.0))
        self.company_name = company_name
        self.lever_id = lever_id

    @property
    def source_name(self) -> str:
        return f"lever_{self.company_name}"

    @property
    def base_url(self) -> str:
        return f"https://jobs.lever.co/{self.lever_id}"

    @property
    def api_url(self) -> str:
        return f"https://api.lever.co/v0/postings/{self.lever_id}"

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        team: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """Fetch all jobs from Lever board."""
        json_data = await self.fetch_json(self.api_url)

        if not json_data:
            logger.warning(f"Failed to fetch Lever jobs for {self.company_name}")
            return

        if not isinstance(json_data, list):
            json_data = [json_data]

        for job_data in json_data:
            job = self._parse_job(job_data)
            if job:
                # Filter by keywords if provided
                if keywords:
                    title_lower = job.title.lower()
                    if not any(kw.lower() in title_lower for kw in keywords):
                        continue

                yield job

    def _parse_job(self, data: Dict[str, Any]) -> Optional[JobPosting]:
        """Parse job from Lever API response."""
        title = data.get("text", "")
        if not title:
            return None

        job_id = data.get("id", "")

        # Categories
        categories = data.get("categories", {})
        location = categories.get("location", "")
        team = categories.get("team", "")
        commitment = categories.get("commitment", "")

        # URL
        hosted_url = data.get("hostedUrl", "")
        apply_url = data.get("applyUrl", "")

        # Created date
        created_at = data.get("createdAt")
        posting_date = None
        if created_at:
            try:
                posting_date = datetime.fromtimestamp(created_at / 1000).isoformat()
            except Exception:
                pass

        # Description
        description_plain = data.get("descriptionPlain", "")

        # Lists (requirements, etc.)
        lists = data.get("lists", [])
        requirements = []
        nice_to_have = []
        for lst in lists:
            list_text = lst.get("text", "").lower()
            content = lst.get("content", "")

            # Extract items from HTML content
            items = re.findall(r"<li>(.*?)</li>", content, re.DOTALL)
            clean_items = [re.sub(r"<[^>]+>", "", item).strip() for item in items]

            if any(x in list_text for x in ["require", "must", "qualif"]):
                requirements.extend(clean_items)
            elif any(x in list_text for x in ["nice", "prefer", "bonus"]):
                nice_to_have.extend(clean_items)

        # Remote detection
        remote_policy = ""
        if "remote" in location.lower():
            remote_policy = "remote"
        elif "hybrid" in location.lower():
            remote_policy = "hybrid"

        return JobPosting(
            job_id=job_id,
            title=title,
            company=self.company_name,
            location=location,
            remote_policy=remote_policy,
            description_full=description_plain,
            requirements=requirements[:10],
            nice_to_have=nice_to_have[:5],
            application_url=hosted_url or apply_url,
            posting_date=posting_date,
            source=self.source_name,
            crawled_at=datetime.now().isoformat(),
            company_type=self.classify_company_type(self.company_name, description_plain)
        )

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Parse job listings from Lever page."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            postings = soup.select("div.posting")

            for posting in postings:
                title_elem = posting.select_one("h5[data-qa='posting-name']")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                location_elem = posting.select_one("span.location")
                location = location_elem.get_text(strip=True) if location_elem else ""

                link_elem = posting.select_one("a.posting-btn-submit")
                job_url = link_elem.get("href", "") if link_elem else ""

                job_id = JobPosting.generate_id(title, self.company_name, job_url)

                jobs.append(JobPosting(
                    job_id=job_id,
                    title=title,
                    company=self.company_name,
                    location=location,
                    application_url=job_url,
                    source=self.source_name,
                    crawled_at=datetime.now().isoformat()
                ))

        except ImportError:
            pass

        return jobs

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse job detail page."""
        return None  # Lever API provides all needed info


class CompanyDirectCrawler(BaseCrawler):
    """Generic crawler for company career pages."""

    def __init__(self, company_name: str, career_url: str, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=1.0))
        self.company_name = company_name
        self.career_url = career_url
        self._base_url = career_url

    @property
    def source_name(self) -> str:
        return f"direct_{self.company_name.lower().replace(' ', '_')}"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """Crawl company career page."""
        html = await self.fetch(self.career_url)
        if not html:
            logger.warning(f"Failed to fetch career page for {self.company_name}")
            return

        jobs = await self.parse_job_listing(html, self.career_url)

        for job in jobs:
            if keywords:
                title_lower = job.title.lower()
                if not any(kw.lower() in title_lower for kw in keywords):
                    continue
            yield job

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Generic job listing parser."""
        jobs = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Try common job listing patterns
            # Pattern 1: Links with job-related text
            job_links = soup.select("a[href*='job'], a[href*='career'], a[href*='position'], a[href*='opening']")

            for link in job_links:
                text = link.get_text(strip=True)
                href = link.get("href", "")

                # Skip navigation/menu items
                if len(text) < 10 or len(text) > 200:
                    continue

                # Make absolute URL
                if href and not href.startswith("http"):
                    href = urljoin(url, href)

                job_id = JobPosting.generate_id(text, self.company_name, href)

                jobs.append(JobPosting(
                    job_id=job_id,
                    title=text,
                    company=self.company_name,
                    application_url=href,
                    source=self.source_name,
                    crawled_at=datetime.now().isoformat(),
                    company_type=self.classify_company_type(self.company_name)
                ))

            # Pattern 2: Job cards with structured data
            job_cards = soup.select("div.job, div.opening, article.job-posting, li.job-listing")

            for card in job_cards:
                title_elem = card.select_one("h2, h3, h4, a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = card.select_one("a")
                href = link.get("href", "") if link else ""

                if href and not href.startswith("http"):
                    href = urljoin(url, href)

                location_elem = card.select_one(".location, .job-location")
                location = location_elem.get_text(strip=True) if location_elem else ""

                job_id = JobPosting.generate_id(title, self.company_name, href)

                jobs.append(JobPosting(
                    job_id=job_id,
                    title=title,
                    company=self.company_name,
                    location=location,
                    application_url=href,
                    source=self.source_name,
                    crawled_at=datetime.now().isoformat(),
                    company_type=self.classify_company_type(self.company_name)
                ))

        except ImportError:
            logger.error("BeautifulSoup required: pip install beautifulsoup4")

        # Deduplicate
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job.job_id not in seen:
                seen.add(job.job_id)
                unique_jobs.append(job)

        return unique_jobs

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Parse job detail page."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Try to find title
            title_elem = soup.select_one("h1, h2.job-title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Find description
            desc_elem = soup.select_one("div.job-description, div.description, article")
            description = desc_elem.get_text("\n", strip=True) if desc_elem else ""

            requirements, nice_to_have = self.extract_requirements(description)

            return JobPosting(
                job_id=JobPosting.generate_id(title, self.company_name, url),
                title=title,
                company=self.company_name,
                description_full=description,
                requirements=requirements,
                nice_to_have=nice_to_have,
                remote_policy=self.extract_remote_policy(description),
                application_url=url,
                source=self.source_name,
                crawled_at=datetime.now().isoformat(),
                company_type=self.classify_company_type(self.company_name, description)
            )

        except ImportError:
            pass

        return None


class AshbyCrawler(BaseCrawler):
    """Crawler for Ashby job boards (used by Perplexity, Mistral, etc.)."""

    def __init__(self, company_name: str, ashby_id: str, config: Optional[CrawlConfig] = None):
        super().__init__(config or CrawlConfig(rate_limit=2.0))
        self.company_name = company_name
        self.ashby_id = ashby_id

    @property
    def source_name(self) -> str:
        return f"ashby_{self.company_name}"

    @property
    def base_url(self) -> str:
        return f"https://jobs.ashbyhq.com/{self.ashby_id}"

    @property
    def api_url(self) -> str:
        return f"https://api.ashbyhq.com/posting-api/job-board/{self.ashby_id}"

    async def search_jobs(
        self,
        keywords: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncGenerator[JobPosting, None]:
        """Fetch all jobs from Ashby board."""
        json_data = await self.fetch_json(self.api_url)

        if not json_data:
            logger.warning(f"Failed to fetch Ashby jobs for {self.company_name}")
            return

        jobs = json_data.get("jobs", [])

        for job_data in jobs:
            job = self._parse_job(job_data)
            if job:
                if keywords:
                    title_lower = job.title.lower()
                    if not any(kw.lower() in title_lower for kw in keywords):
                        continue
                yield job

    def _parse_job(self, data: Dict[str, Any]) -> Optional[JobPosting]:
        """Parse job from Ashby API response."""
        title = data.get("title", "")
        if not title:
            return None

        job_id = data.get("id", "")

        # Location
        location = data.get("location", "")
        if isinstance(location, dict):
            location = location.get("name", "")

        # Department
        department = data.get("department", "")

        # Employment type
        employment_type = data.get("employmentType", "")

        # URL
        job_url = data.get("jobUrl", f"{self.base_url}/{job_id}")

        # Posted date
        published_at = data.get("publishedAt", "")

        # Remote detection
        remote_policy = ""
        location_lower = str(location).lower()
        if "remote" in location_lower:
            remote_policy = "remote"
        elif "hybrid" in location_lower:
            remote_policy = "hybrid"

        return JobPosting(
            job_id=str(job_id),
            title=title,
            company=self.company_name,
            location=location,
            remote_policy=remote_policy,
            application_url=job_url,
            posting_date=published_at,
            source=self.source_name,
            crawled_at=datetime.now().isoformat(),
            company_type=self.classify_company_type(self.company_name)
        )

    async def parse_job_listing(self, html: str, url: str) -> List[JobPosting]:
        """Not used for API-based crawler."""
        return []

    async def parse_job_detail(self, html: str, url: str) -> Optional[JobPosting]:
        """Not used for API-based crawler."""
        return None


def get_company_crawler(company_key: str, config: Optional[CrawlConfig] = None) -> Optional[BaseCrawler]:
    """
    Get appropriate crawler for a company.

    Args:
        company_key: Company identifier (e.g., 'anthropic', 'stripe')
        config: Optional crawler configuration

    Returns:
        Appropriate crawler instance or None
    """
    company_key = company_key.lower().replace(" ", "_").replace("-", "_")

    # Known Greenhouse boards - Top 50 high-paying companies
    greenhouse_boards = {
        # AI Labs
        "anthropic": ("Anthropic", "anthropic"),
        "openai": ("OpenAI", "openai"),
        "scale_ai": ("Scale AI", "scaleai"),
        "cohere": ("Cohere", "cohere"),
        "hugging_face": ("Hugging Face", "huggingface"),

        # AI Compute Infrastructure
        "anyscale": ("Anyscale", "anyscale"),
        "modal": ("Modal", "modal"),
        "replicate": ("Replicate", "replicate"),
        "together_ai": ("Together AI", "togetherai"),
        "coreweave": ("CoreWeave", "coreweave"),
        "lambda_labs": ("Lambda Labs", "lambda"),

        # Fintech
        "stripe": ("Stripe", "stripe"),
        "coinbase": ("Coinbase", "coinbase"),
        "plaid": ("Plaid", "plaid"),
        "ramp": ("Ramp", "ramp"),
        "brex": ("Brex", "brex"),
        "affirm": ("Affirm", "affirm"),
        "kraken": ("Kraken", "kraken"),

        # Big Tech
        "databricks": ("Databricks", "databricks"),
        "airbnb": ("Airbnb", "airbnb"),
        "pinterest": ("Pinterest", "pinterest"),
        "doordash": ("DoorDash", "doordash"),
        "uber": ("Uber", "uber"),
        "snowflake": ("Snowflake", "snowflake"),

        # Quant (some use Greenhouse)
        "citadel": ("Citadel", "citadel"),
        "two_sigma": ("Two Sigma", "twosigma"),
    }

    # Known Lever boards
    lever_boards = {
        "netflix": ("Netflix", "netflix"),
        "roblox": ("Roblox", "roblox"),
        "klarna": ("Klarna", "klarna"),
        "revolut": ("Revolut", "revolut"),
        "block": ("Block", "block"),
        "meta": ("Meta", "meta"),
    }

    # Known Ashby boards (popular with AI startups)
    ashby_boards = {
        "perplexity": ("Perplexity AI", "perplexity"),
        "perplexity_ai": ("Perplexity AI", "perplexity"),
        "mistral": ("Mistral AI", "mistralai"),
        "mistral_ai": ("Mistral AI", "mistralai"),
        "character_ai": ("Character.ai", "characterai"),
        "midjourney": ("Midjourney", "midjourney"),
    }

    if company_key in greenhouse_boards:
        name, token = greenhouse_boards[company_key]
        return GreenhouseCrawler(name, token, config)

    if company_key in lever_boards:
        name, lever_id = lever_boards[company_key]
        return LeverCrawler(name, lever_id, config)

    if company_key in ashby_boards:
        name, ashby_id = ashby_boards[company_key]
        return AshbyCrawler(name, ashby_id, config)

    if company_key in COMPANY_CAREER_URLS:
        return CompanyDirectCrawler(
            company_key.replace("_", " ").title(),
            COMPANY_CAREER_URLS[company_key],
            config
        )

    return None
