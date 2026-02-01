"""
Job Aggregator

Combines multiple job sources into a unified crawling interface.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
import logging

from .base import BaseCrawler, JobPosting, CrawlConfig
from .linkedin import LinkedInCrawler
from .indeed import IndeedCrawler
from .company_direct import (
    GreenhouseCrawler,
    LeverCrawler,
    CompanyDirectCrawler,
    get_company_crawler,
    COMPANY_CAREER_URLS
)
from .remote_boards import (
    RemoteOKCrawler,
    WeWorkRemotelyCrawler,
    WellfoundCrawler,
    LevelsFYICrawler
)

logger = logging.getLogger(__name__)


class JobAggregator:
    """
    Aggregates job postings from multiple sources.

    Provides a unified interface for crawling LinkedIn, Indeed, remote job boards,
    and company career pages.
    """

    def __init__(
        self,
        config: Optional[CrawlConfig] = None,
        db=None
    ):
        """
        Initialize the job aggregator.

        Args:
            config: Crawler configuration
            db: Database instance for caching
        """
        self.config = config or CrawlConfig()
        self.db = db
        self._crawlers: Dict[str, BaseCrawler] = {}
        self._seen_job_ids: Set[str] = set()

    async def close(self):
        """Close all crawler sessions."""
        for crawler in self._crawlers.values():
            await crawler.close()
        self._crawlers.clear()

    def get_crawler(self, source: str) -> Optional[BaseCrawler]:
        """Get or create a crawler for a source."""
        if source in self._crawlers:
            return self._crawlers[source]

        crawler = None

        if source == "linkedin":
            crawler = LinkedInCrawler(self.config)
        elif source == "indeed":
            crawler = IndeedCrawler(self.config)
        elif source == "remoteok":
            crawler = RemoteOKCrawler(self.config)
        elif source == "weworkremotely":
            crawler = WeWorkRemotelyCrawler(self.config)
        elif source == "wellfound":
            crawler = WellfoundCrawler(self.config)
        elif source == "levelsfyi":
            crawler = LevelsFYICrawler(self.config)
        else:
            # Try company-specific crawler
            crawler = get_company_crawler(source, self.config)

        if crawler:
            self._crawlers[source] = crawler

        return crawler

    async def crawl_all(
        self,
        keywords: List[str],
        sources: Optional[List[str]] = None,
        location: Optional[str] = None,
        remote_only: bool = False,
        target_companies: Optional[List[str]] = None,
        max_jobs_per_source: int = 100,
        **kwargs
    ) -> List[JobPosting]:
        """
        Crawl all configured sources.

        Args:
            keywords: Search keywords
            sources: List of sources to crawl (default: all)
            location: Location filter
            remote_only: Only remote jobs
            target_companies: Specific companies to crawl
            max_jobs_per_source: Maximum jobs to collect per source

        Returns:
            List of deduplicated JobPosting objects
        """
        start_time = time.time()

        # Default sources
        if sources is None:
            sources = ["linkedin", "indeed", "remoteok", "weworkremotely"]

        all_jobs: List[JobPosting] = []
        self._seen_job_ids.clear()

        # Crawl general sources
        tasks = []
        for source in sources:
            tasks.append(self._crawl_source(
                source,
                keywords,
                location,
                remote_only,
                max_jobs_per_source,
                **kwargs
            ))

        # Crawl target companies
        if target_companies:
            for company in target_companies:
                tasks.append(self._crawl_company(
                    company,
                    keywords,
                    max_jobs_per_source
                ))

        # Run all crawls concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Crawl error: {result}")
            elif isinstance(result, list):
                for job in result:
                    if job.job_id not in self._seen_job_ids:
                        self._seen_job_ids.add(job.job_id)
                        all_jobs.append(job)

        duration = time.time() - start_time
        logger.info(f"Crawled {len(all_jobs)} unique jobs in {duration:.1f}s")

        # Save to database if available
        if self.db:
            result = self.db.save_jobs(all_jobs)
            logger.info(f"Saved {result['inserted']} new, updated {result['updated']} existing")

        return all_jobs

    async def _crawl_source(
        self,
        source: str,
        keywords: List[str],
        location: Optional[str],
        remote_only: bool,
        max_jobs: int,
        **kwargs
    ) -> List[JobPosting]:
        """Crawl a single source."""
        crawler = self.get_crawler(source)
        if not crawler:
            logger.warning(f"No crawler available for source: {source}")
            return []

        jobs = []
        try:
            async for job in crawler.search_jobs(
                keywords=keywords,
                location=location,
                remote_only=remote_only,
                **kwargs
            ):
                jobs.append(job)
                if len(jobs) >= max_jobs:
                    break

            logger.info(f"Crawled {len(jobs)} jobs from {source}")

        except Exception as e:
            logger.error(f"Error crawling {source}: {e}")

        return jobs

    async def _crawl_company(
        self,
        company: str,
        keywords: List[str],
        max_jobs: int
    ) -> List[JobPosting]:
        """Crawl a specific company's career page."""
        company_key = company.lower().replace(" ", "_")
        crawler = get_company_crawler(company_key, self.config)

        if not crawler:
            logger.warning(f"No crawler available for company: {company}")
            return []

        jobs = []
        try:
            async for job in crawler.search_jobs(keywords=keywords):
                jobs.append(job)
                if len(jobs) >= max_jobs:
                    break

            logger.info(f"Crawled {len(jobs)} jobs from {company}")

        except Exception as e:
            logger.error(f"Error crawling {company}: {e}")

        finally:
            await crawler.close()

        return jobs

    async def crawl_by_config(
        self,
        search_config: Dict[str, Any]
    ) -> List[JobPosting]:
        """
        Crawl based on configuration dictionary.

        Args:
            search_config: Configuration with role_types, company_categories, etc.

        Returns:
            List of JobPosting objects
        """
        # Extract keywords from role types
        keywords = []
        role_types = search_config.get("role_types", {})
        for category, titles in role_types.items():
            keywords.extend(titles[:3])  # Top 3 from each category

        # Get target companies from enabled categories
        target_companies = []
        company_categories = search_config.get("company_categories", {})
        for category, config in company_categories.items():
            if config.get("enabled", False):
                targets = config.get("targets", [])
                if config.get("priority") == "high":
                    target_companies.extend(targets[:5])  # Top 5 from high priority
                else:
                    target_companies.extend(targets[:2])  # Top 2 from others

        # Work arrangement preferences
        work_arrangement = search_config.get("work_arrangement", [])
        remote_only = work_arrangement == ["remote"]

        # Geographic preferences
        locations = search_config.get("geographic_preferences", ["global"])
        location = None if "global" in locations else locations[0] if locations else None

        # Sources to crawl
        sources = ["linkedin", "indeed", "remoteok"]
        if remote_only or "remote" in work_arrangement:
            sources.extend(["weworkremotely", "wellfound"])

        return await self.crawl_all(
            keywords=keywords[:10],  # Limit keywords
            sources=sources,
            location=location,
            remote_only=remote_only,
            target_companies=target_companies[:20],  # Limit companies
            max_jobs_per_source=50
        )

    async def get_job_details(
        self,
        job: JobPosting
    ) -> Optional[JobPosting]:
        """
        Fetch full details for a job posting.

        Args:
            job: JobPosting with basic info

        Returns:
            JobPosting with full details or None
        """
        if not job.application_url:
            return None

        # Get appropriate crawler
        crawler = self.get_crawler(job.source)
        if not crawler:
            return None

        try:
            html = await crawler.fetch(job.application_url)
            if html:
                detailed_job = await crawler.parse_job_detail(html, job.application_url)
                if detailed_job:
                    # Merge with existing data
                    detailed_job.job_id = job.job_id
                    detailed_job.match_score = job.match_score
                    detailed_job.status = job.status
                    return detailed_job

        except Exception as e:
            logger.error(f"Error fetching job details: {e}")

        return None

    def get_available_sources(self) -> List[str]:
        """Get list of available job sources."""
        sources = [
            "linkedin",
            "indeed",
            "remoteok",
            "weworkremotely",
            "wellfound",
            "levelsfyi"
        ]
        sources.extend(list(COMPANY_CAREER_URLS.keys()))
        return sources

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


async def crawl_jobs(
    keywords: List[str],
    sources: Optional[List[str]] = None,
    location: Optional[str] = None,
    remote_only: bool = False,
    target_companies: Optional[List[str]] = None,
    db=None
) -> List[JobPosting]:
    """
    Convenience function to crawl jobs.

    Args:
        keywords: Search keywords
        sources: Job sources to crawl
        location: Location filter
        remote_only: Only remote jobs
        target_companies: Specific companies to target
        db: Database for caching

    Returns:
        List of JobPosting objects
    """
    async with JobAggregator(db=db) as aggregator:
        return await aggregator.crawl_all(
            keywords=keywords,
            sources=sources,
            location=location,
            remote_only=remote_only,
            target_companies=target_companies
        )
