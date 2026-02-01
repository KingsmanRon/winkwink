"""
CSV Exporter

Exports job search results to CSV format for spreadsheet applications.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, IO
import logging

from ..database import JobPosting
from ..matcher import MatchScore

logger = logging.getLogger(__name__)


class CSVExporter:
    """Export job results to CSV format."""

    # Standard columns for export
    COLUMNS = [
        "job_id",
        "company",
        "title",
        "location",
        "remote_policy",
        "salary_min",
        "salary_max",
        "salary_currency",
        "match_score",
        "match_tier",
        "status",
        "posting_date",
        "source",
        "application_url",
        "applied_date",
        "next_action",
        "notes",
    ]

    def __init__(self, output_path: Optional[Path] = None):
        """
        Initialize CSV exporter.

        Args:
            output_path: Output file path (default: results_{timestamp}.csv)
        """
        if output_path:
            self.output_path = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = Path(f"job_results_{timestamp}.csv")

    def export(
        self,
        jobs: List[JobPosting],
        scores: Optional[Dict[str, MatchScore]] = None,
        columns: Optional[List[str]] = None
    ) -> Path:
        """
        Export jobs to CSV file.

        Args:
            jobs: List of job postings
            scores: Optional dict mapping job_id to MatchScore
            columns: Optional custom column list

        Returns:
            Path to exported file
        """
        columns = columns or self.COLUMNS

        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()

            for job in jobs:
                row = self._job_to_row(job, scores)
                writer.writerow(row)

        logger.info(f"Exported {len(jobs)} jobs to {self.output_path}")
        return self.output_path

    def export_with_match_details(
        self,
        results: List[Tuple[JobPosting, MatchScore]]
    ) -> Path:
        """
        Export jobs with detailed match scores.

        Args:
            results: List of (job, score) tuples

        Returns:
            Path to exported file
        """
        extended_columns = self.COLUMNS + [
            "skill_score",
            "experience_score",
            "certification_score",
            "matched_skills",
            "missing_skills",
        ]

        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=extended_columns, extrasaction="ignore")
            writer.writeheader()

            for job, score in results:
                row = self._job_to_row(job, {job.job_id: score})
                row["skill_score"] = round(score.skill_score, 1)
                row["experience_score"] = round(score.experience_score, 1)
                row["certification_score"] = round(score.certification_score, 1)
                row["matched_skills"] = ", ".join(score.matched_skills)
                row["missing_skills"] = ", ".join(score.missing_skills)
                writer.writerow(row)

        logger.info(f"Exported {len(results)} jobs with match details to {self.output_path}")
        return self.output_path

    def _job_to_row(
        self,
        job: JobPosting,
        scores: Optional[Dict[str, MatchScore]] = None
    ) -> Dict[str, Any]:
        """Convert job to CSV row."""
        row = {
            "job_id": job.job_id,
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "remote_policy": job.remote_policy,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "match_score": job.match_score,
            "status": job.status,
            "posting_date": job.posting_date,
            "source": job.source,
            "application_url": job.application_url,
            "applied_date": job.applied_date,
            "next_action": job.next_action,
            "notes": job.notes,
        }

        # Add match tier if score available
        if scores and job.job_id in scores:
            score = scores[job.job_id]
            row["match_score"] = round(score.total, 1)
            row["match_tier"] = score.tier

        return row

    @classmethod
    def export_summary(
        cls,
        jobs: List[JobPosting],
        output_path: Path
    ) -> Path:
        """
        Export a summary CSV with minimal columns.

        Args:
            jobs: List of job postings
            output_path: Output file path

        Returns:
            Path to exported file
        """
        summary_columns = [
            "company",
            "title",
            "location",
            "match_score",
            "application_url",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=summary_columns)
            writer.writeheader()

            for job in jobs:
                writer.writerow({
                    "company": job.company,
                    "title": job.title,
                    "location": job.location,
                    "match_score": job.match_score,
                    "application_url": job.application_url,
                })

        return output_path


class JSONExporter:
    """Export job results to JSON format."""

    def __init__(self, output_path: Optional[Path] = None):
        """
        Initialize JSON exporter.

        Args:
            output_path: Output file path
        """
        if output_path:
            self.output_path = Path(output_path)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = Path(f"job_results_{timestamp}.json")

    def export(
        self,
        jobs: List[JobPosting],
        scores: Optional[Dict[str, MatchScore]] = None,
        include_raw: bool = False
    ) -> Path:
        """
        Export jobs to JSON file.

        Args:
            jobs: List of job postings
            scores: Optional dict mapping job_id to MatchScore
            include_raw: Include full description text

        Returns:
            Path to exported file
        """
        data = {
            "exported_at": datetime.now().isoformat(),
            "total_jobs": len(jobs),
            "jobs": []
        }

        for job in jobs:
            job_data = job.to_dict()

            # Remove large description if not needed
            if not include_raw:
                job_data.pop("description_full", None)

            # Add match score details
            if scores and job.job_id in scores:
                job_data["match_details"] = scores[job.job_id].to_dict()

            data["jobs"].append(job_data)

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported {len(jobs)} jobs to {self.output_path}")
        return self.output_path


def export_to_csv(
    jobs: List[JobPosting],
    output_path: Optional[str] = None,
    scores: Optional[Dict[str, MatchScore]] = None
) -> Path:
    """
    Convenience function to export jobs to CSV.

    Args:
        jobs: List of job postings
        output_path: Optional output file path
        scores: Optional match scores

    Returns:
        Path to exported file
    """
    path = Path(output_path) if output_path else None
    exporter = CSVExporter(path)
    return exporter.export(jobs, scores)


def export_to_json(
    jobs: List[JobPosting],
    output_path: Optional[str] = None,
    scores: Optional[Dict[str, MatchScore]] = None
) -> Path:
    """
    Convenience function to export jobs to JSON.

    Args:
        jobs: List of job postings
        output_path: Optional output file path
        scores: Optional match scores

    Returns:
        Path to exported file
    """
    path = Path(output_path) if output_path else None
    exporter = JSONExporter(path)
    return exporter.export(jobs, scores)
