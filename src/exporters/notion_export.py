"""
Notion Exporter

Exports job search results to Notion-compatible CSV format for database import.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

from ..database import JobPosting
from ..matcher import MatchScore

logger = logging.getLogger(__name__)


class NotionExporter:
    """
    Export job results to Notion-compatible format.

    Notion databases can import CSV files with specific column formats.
    This exporter generates a CSV that maps well to Notion's database properties.
    """

    # Notion-friendly column mappings
    NOTION_COLUMNS = [
        "Name",            # Title (required first column)
        "Company",         # Text
        "Location",        # Text
        "Remote",          # Select (Remote/Hybrid/On-site)
        "Match Score",     # Number
        "Match Tier",      # Select (Strong/Good/Stretch)
        "Status",          # Select (New/Applied/Interviewing/Rejected/Offer)
        "Salary Min",      # Number
        "Salary Max",      # Number
        "Currency",        # Select
        "Posted",          # Date
        "Applied",         # Date
        "Source",          # Select
        "URL",             # URL
        "Next Action",     # Text
        "Notes",           # Text (multi-line)
    ]

    def __init__(self, output_path: Optional[Path] = None):
        """
        Initialize Notion exporter.

        Args:
            output_path: Output file path (default: notion_import_{timestamp}.csv)
        """
        if output_path:
            self.output_path = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = Path(f"notion_import_{timestamp}.csv")

    def export(
        self,
        jobs: List[JobPosting],
        scores: Optional[Dict[str, MatchScore]] = None
    ) -> Path:
        """
        Export jobs to Notion-compatible CSV.

        Args:
            jobs: List of job postings
            scores: Optional dict mapping job_id to MatchScore

        Returns:
            Path to exported file
        """
        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.NOTION_COLUMNS)
            writer.writeheader()

            for job in jobs:
                row = self._job_to_notion_row(job, scores)
                writer.writerow(row)

        logger.info(f"Exported {len(jobs)} jobs to Notion format: {self.output_path}")
        return self.output_path

    def _job_to_notion_row(
        self,
        job: JobPosting,
        scores: Optional[Dict[str, MatchScore]] = None
    ) -> Dict[str, Any]:
        """Convert job to Notion-friendly row."""
        # Determine match tier
        match_tier = ""
        match_score = job.match_score

        if scores and job.job_id in scores:
            score = scores[job.job_id]
            match_score = score.total
            match_tier = score.tier.title()
        elif match_score:
            if match_score >= 80:
                match_tier = "Strong"
            elif match_score >= 70:
                match_tier = "Good"
            elif match_score >= 60:
                match_tier = "Stretch"

        # Map remote policy to Notion-friendly select
        remote_mapping = {
            "remote": "Remote",
            "hybrid": "Hybrid",
            "onsite": "On-site",
            "": "",
        }
        remote = remote_mapping.get(job.remote_policy.lower(), job.remote_policy)

        # Map status
        status_mapping = {
            "new": "New",
            "applied": "Applied",
            "interviewing": "Interviewing",
            "rejected": "Rejected",
            "offer": "Offer",
        }
        status = status_mapping.get(job.status.lower(), job.status.title())

        # Format dates for Notion (YYYY-MM-DD)
        posted_date = ""
        if job.posting_date:
            try:
                # Handle various date formats
                if "T" in job.posting_date:
                    posted_date = job.posting_date.split("T")[0]
                else:
                    posted_date = job.posting_date[:10]
            except Exception:
                posted_date = job.posting_date

        applied_date = ""
        if job.applied_date:
            try:
                if "T" in job.applied_date:
                    applied_date = job.applied_date.split("T")[0]
                else:
                    applied_date = job.applied_date[:10]
            except Exception:
                applied_date = job.applied_date

        return {
            "Name": job.title,
            "Company": job.company,
            "Location": job.location,
            "Remote": remote,
            "Match Score": round(match_score, 1) if match_score else "",
            "Match Tier": match_tier,
            "Status": status,
            "Salary Min": job.salary_min if job.salary_min else "",
            "Salary Max": job.salary_max if job.salary_max else "",
            "Currency": job.salary_currency,
            "Posted": posted_date,
            "Applied": applied_date,
            "Source": job.source.title() if job.source else "",
            "URL": job.application_url,
            "Next Action": job.next_action,
            "Notes": job.notes,
        }

    @classmethod
    def get_notion_template_instructions(cls) -> str:
        """Get instructions for setting up Notion database."""
        return """
# Notion Database Setup Instructions

1. Create a new Notion database (Table view recommended)

2. Add the following properties:
   - Name (Title) - Already exists by default
   - Company (Text)
   - Location (Text)
   - Remote (Select) - Options: Remote, Hybrid, On-site
   - Match Score (Number)
   - Match Tier (Select) - Options: Strong, Good, Stretch
   - Status (Select) - Options: New, Applied, Interviewing, Rejected, Offer
   - Salary Min (Number)
   - Salary Max (Number)
   - Currency (Select) - Options: USD, EUR, GBP
   - Posted (Date)
   - Applied (Date)
   - Source (Select) - Options will auto-populate
   - URL (URL)
   - Next Action (Text)
   - Notes (Text)

3. Click "..." menu > "Import" > "CSV"

4. Upload the exported CSV file

5. Map columns if needed (usually auto-detected)

6. Recommended views to create:
   - "Pipeline" - Kanban by Status
   - "Strong Matches" - Filter Match Tier = Strong
   - "To Apply" - Filter Status = New, Sort by Match Score
"""


def export_to_notion(
    jobs: List[JobPosting],
    output_path: Optional[str] = None,
    scores: Optional[Dict[str, MatchScore]] = None
) -> Path:
    """
    Convenience function to export jobs to Notion format.

    Args:
        jobs: List of job postings
        output_path: Optional output file path
        scores: Optional match scores

    Returns:
        Path to exported file
    """
    path = Path(output_path) if output_path else None
    exporter = NotionExporter(path)
    return exporter.export(jobs, scores)
