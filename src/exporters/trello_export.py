"""
Trello Exporter

Exports job search results to Trello-compatible JSON format for board import.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

from ..database import JobPosting
from ..matcher import MatchScore

logger = logging.getLogger(__name__)


class TrelloExporter:
    """
    Export job results to Trello-compatible format.

    Generates JSON files that can be used with Trello's import functionality
    or the Trello API for automated board creation.
    """

    # Default list names for job tracking
    DEFAULT_LISTS = [
        "Strong Matches",
        "Good Matches",
        "Stretch Roles",
        "Applied",
        "Interviewing",
        "Rejected",
        "Offers",
    ]

    def __init__(self, output_path: Optional[Path] = None, board_name: str = "Job Search"):
        """
        Initialize Trello exporter.

        Args:
            output_path: Output file path
            board_name: Name for the Trello board
        """
        if output_path:
            self.output_path = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = Path(f"trello_cards_{timestamp}.json")

        self.board_name = board_name

    def export(
        self,
        jobs: List[JobPosting],
        scores: Optional[Dict[str, MatchScore]] = None
    ) -> Path:
        """
        Export jobs to Trello-compatible JSON.

        Args:
            jobs: List of job postings
            scores: Optional dict mapping job_id to MatchScore

        Returns:
            Path to exported file
        """
        # Organize jobs by list
        lists_data = {name: [] for name in self.DEFAULT_LISTS}

        for job in jobs:
            card = self._job_to_card(job, scores)
            list_name = self._get_list_for_job(job, scores)
            lists_data[list_name].append(card)

        # Build export structure
        export_data = {
            "board_name": self.board_name,
            "exported_at": datetime.now().isoformat(),
            "total_cards": len(jobs),
            "lists": [
                {
                    "name": list_name,
                    "cards": cards
                }
                for list_name, cards in lists_data.items()
                if cards  # Only include non-empty lists
            ]
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Exported {len(jobs)} jobs to Trello format: {self.output_path}")
        return self.output_path

    def _job_to_card(
        self,
        job: JobPosting,
        scores: Optional[Dict[str, MatchScore]] = None
    ) -> Dict[str, Any]:
        """Convert job to Trello card format."""
        # Build card description
        desc_parts = []

        if job.location:
            desc_parts.append(f"**Location:** {job.location}")

        if job.remote_policy:
            desc_parts.append(f"**Remote:** {job.remote_policy.title()}")

        if job.salary_min or job.salary_max:
            salary = ""
            if job.salary_min and job.salary_max:
                salary = f"${job.salary_min:,} - ${job.salary_max:,}"
            elif job.salary_max:
                salary = f"Up to ${job.salary_max:,}"
            else:
                salary = f"${job.salary_min:,}+"
            desc_parts.append(f"**Salary:** {salary} {job.salary_currency}")

        # Add match score
        match_score = job.match_score
        if scores and job.job_id in scores:
            score = scores[job.job_id]
            match_score = score.total
            desc_parts.append(f"**Match Score:** {match_score:.0f}% ({score.tier.title()})")

            if score.matched_skills:
                desc_parts.append(f"**Matched Skills:** {', '.join(score.matched_skills)}")

            if score.missing_skills:
                desc_parts.append(f"**Gap Areas:** {', '.join(score.missing_skills)}")
        elif match_score:
            desc_parts.append(f"**Match Score:** {match_score:.0f}%")

        if job.posting_date:
            desc_parts.append(f"**Posted:** {job.posting_date[:10]}")

        desc_parts.append(f"**Source:** {job.source}")
        desc_parts.append(f"\n---\n\n**Apply:** {job.application_url}")

        # Build labels
        labels = []
        if job.company_type:
            labels.append(job.company_type.replace("_", " ").title())
        if job.remote_policy == "remote":
            labels.append("Remote")

        # Checklist items
        checklist = [
            {"name": "Research company", "completed": False},
            {"name": "Tailor resume", "completed": False},
            {"name": "Write cover letter", "completed": False},
            {"name": "Submit application", "completed": job.status == "applied"},
            {"name": "Follow up", "completed": False},
        ]

        return {
            "name": f"{job.title} @ {job.company}",
            "description": "\n\n".join(desc_parts),
            "labels": labels,
            "url": job.application_url,
            "checklist": checklist,
            "due_date": None,  # Can be set based on posting date + X days
            "metadata": {
                "job_id": job.job_id,
                "match_score": match_score,
                "company_type": job.company_type,
            }
        }

    def _get_list_for_job(
        self,
        job: JobPosting,
        scores: Optional[Dict[str, MatchScore]] = None
    ) -> str:
        """Determine which list a job should go in."""
        # Check status first
        if job.status == "applied":
            return "Applied"
        elif job.status == "interviewing":
            return "Interviewing"
        elif job.status == "rejected":
            return "Rejected"
        elif job.status == "offer":
            return "Offers"

        # Otherwise, sort by match score
        match_score = job.match_score
        tier = ""

        if scores and job.job_id in scores:
            score = scores[job.job_id]
            match_score = score.total
            tier = score.tier

        if tier == "strong" or (match_score and match_score >= 80):
            return "Strong Matches"
        elif tier == "good" or (match_score and match_score >= 70):
            return "Good Matches"
        else:
            return "Stretch Roles"

    def export_for_api(
        self,
        jobs: List[JobPosting],
        scores: Optional[Dict[str, MatchScore]] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        board_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Trello API-ready format.

        This can be used with the Trello REST API to directly create cards.

        Args:
            jobs: List of job postings
            scores: Optional match scores
            api_key: Trello API key
            token: Trello API token
            board_id: Existing board ID to add cards to

        Returns:
            Dict with API request data
        """
        api_data = {
            "api_key": api_key,
            "token": token,
            "board_id": board_id,
            "operations": []
        }

        for job in jobs:
            card = self._job_to_card(job, scores)
            list_name = self._get_list_for_job(job, scores)

            api_data["operations"].append({
                "action": "create_card",
                "list_name": list_name,
                "card_data": {
                    "name": card["name"],
                    "desc": card["description"],
                    "urlSource": card["url"],
                }
            })

        return api_data

    @classmethod
    def get_trello_setup_instructions(cls) -> str:
        """Get instructions for setting up Trello board."""
        return """
# Trello Board Setup Instructions

## Manual Setup

1. Create a new Trello board named "Job Search"

2. Create the following lists (in order):
   - Strong Matches
   - Good Matches
   - Stretch Roles
   - Applied
   - Interviewing
   - Rejected
   - Offers

3. Create labels for company types:
   - AI Native (purple)
   - Fintech (green)
   - Big Tech (blue)
   - Quant (orange)
   - Cloud Vendor (yellow)
   - Remote (light blue)

4. Import cards using the exported JSON:
   - Use Trello's Butler automation or a third-party import tool
   - Or manually create cards from the exported data

## API Setup (Automated)

1. Get your Trello API key from: https://trello.com/app-key

2. Generate a token with write access

3. Use the `export_for_api()` method with your credentials

4. The exported data includes Trello API-compatible operations

## Recommended Workflow

1. Review "Strong Matches" first
2. Move cards to "Applied" after submitting
3. Use the checklist on each card to track progress
4. Archive rejected positions regularly
"""


def export_to_trello(
    jobs: List[JobPosting],
    output_path: Optional[str] = None,
    scores: Optional[Dict[str, MatchScore]] = None,
    board_name: str = "Job Search"
) -> Path:
    """
    Convenience function to export jobs to Trello format.

    Args:
        jobs: List of job postings
        output_path: Optional output file path
        scores: Optional match scores
        board_name: Name for the Trello board

    Returns:
        Path to exported file
    """
    path = Path(output_path) if output_path else None
    exporter = TrelloExporter(path, board_name)
    return exporter.export(jobs, scores)
