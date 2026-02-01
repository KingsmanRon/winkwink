"""
Database Module

SQLite operations for caching job postings and tracking application status.
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".jobcrawler" / "jobs.db"


@dataclass
class JobPosting:
    """Structured job posting data."""

    job_id: str
    title: str
    company: str
    company_type: str = ""  # fintech|quant|big_tech|ai_native|consulting|cloud_vendor
    location: str = ""
    remote_policy: str = ""  # remote|hybrid|onsite
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    salary_period: str = "yearly"  # yearly|monthly
    requirements: List[str] = field(default_factory=list)
    nice_to_have: List[str] = field(default_factory=list)
    description_full: str = ""
    application_url: str = ""
    posting_date: Optional[str] = None
    source: str = ""  # linkedin|indeed|company_direct|etc
    crawled_at: Optional[str] = None
    match_score: Optional[float] = None
    status: str = "new"  # new|applied|interviewing|rejected|offer
    applied_date: Optional[str] = None
    next_action: str = ""
    notes: str = ""
    contacts: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobPosting":
        """Create from dictionary."""
        # Handle JSON strings for list fields
        for list_field in ["requirements", "nice_to_have", "contacts"]:
            if list_field in data and isinstance(data[list_field], str):
                try:
                    data[list_field] = json.loads(data[list_field])
                except json.JSONDecodeError:
                    data[list_field] = []

        # Filter to only valid fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

    @staticmethod
    def generate_job_id(title: str, company: str, url: str = "") -> str:
        """Generate unique job ID from title, company, and URL."""
        content = f"{title.lower()}|{company.lower()}|{url}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class JobDatabase:
    """SQLite database for job caching and tracking."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.jobcrawler/jobs.db
        """
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get database connection as context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    company_type TEXT,
                    location TEXT,
                    remote_policy TEXT,
                    salary_min INTEGER,
                    salary_max INTEGER,
                    salary_currency TEXT DEFAULT 'USD',
                    salary_period TEXT DEFAULT 'yearly',
                    requirements TEXT,
                    nice_to_have TEXT,
                    description_full TEXT,
                    application_url TEXT,
                    posting_date TEXT,
                    source TEXT,
                    crawled_at TEXT,
                    match_score REAL,
                    status TEXT DEFAULT 'new',
                    applied_date TEXT,
                    next_action TEXT,
                    notes TEXT,
                    contacts TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Candidate profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidate_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Crawl history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawl_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    query TEXT,
                    jobs_found INTEGER,
                    jobs_new INTEGER,
                    crawled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    duration_seconds REAL,
                    status TEXT DEFAULT 'success',
                    error_message TEXT
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON jobs(match_score)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_posting_date ON jobs(posting_date)")

    def save_job(self, job: JobPosting) -> bool:
        """
        Save or update a job posting.

        Args:
            job: JobPosting to save

        Returns:
            True if new job inserted, False if existing job updated
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if job exists
            cursor.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job.job_id,))
            exists = cursor.fetchone() is not None

            job_data = job.to_dict()

            # Serialize list fields to JSON
            for list_field in ["requirements", "nice_to_have", "contacts"]:
                if list_field in job_data:
                    job_data[list_field] = json.dumps(job_data[list_field])

            job_data["updated_at"] = datetime.now().isoformat()

            if exists:
                # Update existing
                set_clause = ", ".join([f"{k} = ?" for k in job_data.keys()])
                values = list(job_data.values()) + [job.job_id]
                cursor.execute(
                    f"UPDATE jobs SET {set_clause} WHERE job_id = ?",
                    values
                )
                return False
            else:
                # Insert new
                job_data["created_at"] = datetime.now().isoformat()
                columns = ", ".join(job_data.keys())
                placeholders = ", ".join(["?" for _ in job_data])
                cursor.execute(
                    f"INSERT INTO jobs ({columns}) VALUES ({placeholders})",
                    list(job_data.values())
                )
                return True

    def save_jobs(self, jobs: List[JobPosting]) -> Dict[str, int]:
        """
        Save multiple job postings.

        Args:
            jobs: List of JobPosting objects

        Returns:
            Dict with 'inserted' and 'updated' counts
        """
        inserted = 0
        updated = 0

        for job in jobs:
            if self.save_job(job):
                inserted += 1
            else:
                updated += 1

        return {"inserted": inserted, "updated": updated}

    def get_job(self, job_id: str) -> Optional[JobPosting]:
        """Get a job by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()

            if row:
                return JobPosting.from_dict(dict(row))
            return None

    def get_jobs(
        self,
        source: Optional[str] = None,
        company: Optional[str] = None,
        status: Optional[str] = None,
        min_match_score: Optional[float] = None,
        max_age_days: Optional[int] = None,
        limit: Optional[int] = None,
        order_by: str = "match_score DESC"
    ) -> List[JobPosting]:
        """
        Get jobs with optional filters.

        Args:
            source: Filter by source
            company: Filter by company
            status: Filter by status
            min_match_score: Minimum match score
            max_age_days: Maximum age in days
            limit: Maximum number of results
            order_by: SQL ORDER BY clause

        Returns:
            List of JobPosting objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM jobs WHERE 1=1"
            params = []

            if source:
                query += " AND source = ?"
                params.append(source)

            if company:
                query += " AND company LIKE ?"
                params.append(f"%{company}%")

            if status:
                query += " AND status = ?"
                params.append(status)

            if min_match_score is not None:
                query += " AND match_score >= ?"
                params.append(min_match_score)

            if max_age_days is not None:
                cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
                query += " AND posting_date >= ?"
                params.append(cutoff)

            # Sanitize order_by to prevent SQL injection
            allowed_orders = [
                "match_score DESC", "match_score ASC",
                "posting_date DESC", "posting_date ASC",
                "company ASC", "company DESC",
                "title ASC", "title DESC",
                "salary_max DESC", "salary_max ASC"
            ]
            if order_by not in allowed_orders:
                order_by = "match_score DESC"

            query += f" ORDER BY {order_by}"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [JobPosting.from_dict(dict(row)) for row in rows]

    def update_job_status(self, job_id: str, status: str, notes: str = "") -> bool:
        """
        Update job application status.

        Args:
            job_id: Job ID
            status: New status
            notes: Optional notes

        Returns:
            True if job was updated
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            update_data = {
                "status": status,
                "updated_at": datetime.now().isoformat()
            }

            if status == "applied":
                update_data["applied_date"] = datetime.now().isoformat()

            if notes:
                update_data["notes"] = notes

            set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [job_id]

            cursor.execute(
                f"UPDATE jobs SET {set_clause} WHERE job_id = ?",
                values
            )

            return cursor.rowcount > 0

    def update_match_score(self, job_id: str, score: float) -> bool:
        """Update job match score."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE jobs SET match_score = ?, updated_at = ? WHERE job_id = ?",
                (score, datetime.now().isoformat(), job_id)
            )
            return cursor.rowcount > 0

    def job_exists(self, job_id: str) -> bool:
        """Check if a job already exists in database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
            return cursor.fetchone() is not None

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            return cursor.rowcount > 0

    def delete_old_jobs(self, days: int = 90) -> int:
        """Delete jobs older than specified days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            cursor.execute(
                "DELETE FROM jobs WHERE crawled_at < ? AND status = 'new'",
                (cutoff,)
            )
            return cursor.rowcount

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total jobs
            cursor.execute("SELECT COUNT(*) FROM jobs")
            stats["total_jobs"] = cursor.fetchone()[0]

            # Jobs by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM jobs
                GROUP BY status
            """)
            stats["by_status"] = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Jobs by source
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM jobs
                GROUP BY source
                ORDER BY count DESC
            """)
            stats["by_source"] = {row["source"]: row["count"] for row in cursor.fetchall()}

            # Match score distribution
            cursor.execute("""
                SELECT
                    CASE
                        WHEN match_score >= 80 THEN 'strong'
                        WHEN match_score >= 70 THEN 'good'
                        WHEN match_score >= 60 THEN 'stretch'
                        ELSE 'below_threshold'
                    END as tier,
                    COUNT(*) as count
                FROM jobs
                WHERE match_score IS NOT NULL
                GROUP BY tier
            """)
            stats["by_match_tier"] = {row["tier"]: row["count"] for row in cursor.fetchall()}

            # Recent crawls
            cursor.execute("""
                SELECT source, jobs_found, jobs_new, crawled_at
                FROM crawl_history
                ORDER BY crawled_at DESC
                LIMIT 10
            """)
            stats["recent_crawls"] = [dict(row) for row in cursor.fetchall()]

            return stats

    def log_crawl(
        self,
        source: str,
        query: str,
        jobs_found: int,
        jobs_new: int,
        duration_seconds: float,
        status: str = "success",
        error_message: str = ""
    ):
        """Log a crawl operation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO crawl_history
                (source, query, jobs_found, jobs_new, duration_seconds, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (source, query, jobs_found, jobs_new, duration_seconds, status, error_message))

    def save_candidate_profile(self, name: str, profile_json: str) -> int:
        """Save candidate profile and return ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Deactivate other profiles
            cursor.execute("UPDATE candidate_profiles SET is_active = 0")

            cursor.execute(
                "INSERT INTO candidate_profiles (name, profile_json) VALUES (?, ?)",
                (name, profile_json)
            )

            return cursor.lastrowid

    def get_active_profile(self) -> Optional[Dict[str, Any]]:
        """Get the active candidate profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT profile_json
                FROM candidate_profiles
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()

            if row:
                return json.loads(row["profile_json"])
            return None

    def search_jobs(self, query: str, limit: int = 50) -> List[JobPosting]:
        """
        Full-text search across job titles and descriptions.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching jobs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Simple LIKE search (could be enhanced with FTS5)
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM jobs
                WHERE title LIKE ? OR company LIKE ? OR description_full LIKE ?
                ORDER BY match_score DESC
                LIMIT ?
            """, (search_pattern, search_pattern, search_pattern, limit))

            return [JobPosting.from_dict(dict(row)) for row in cursor.fetchall()]


def get_database(db_path: Optional[str] = None) -> JobDatabase:
    """Get database instance."""
    return JobDatabase(db_path)
