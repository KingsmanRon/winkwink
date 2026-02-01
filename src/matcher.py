"""
Intelligent Matching Algorithm

Scores job postings against candidate profiles using multiple factors.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import logging

from .cv_parser import CandidateProfile
from .database import JobPosting

logger = logging.getLogger(__name__)


# AI-adjacent job signals (bonus for growth opportunities)
AI_ADJACENT_SIGNALS = [
    "infrastructure background preferred",
    "no ml experience required",
    "we will train",
    "platform focus",
    "support ml/ai teams",
    "deploy and scale models",
    "strong engineering fundamentals",
    "distributed systems experience",
    "not expected to write models",
    "enable data scientists",
    "build tooling for ml",
    "ml platform",
    "ai infrastructure",
    "model serving",
    "training infrastructure",
    "gpu infrastructure",
    "willing to learn",
    "learn on the job",
    "mentorship",
    "growth opportunity",
]

# Skill keyword mappings for matching
SKILL_KEYWORDS = {
    # Cloud platforms
    "aws": ["aws", "amazon web services", "ec2", "s3", "lambda", "cloudformation", "eks", "ecs", "rds"],
    "azure": ["azure", "microsoft azure", "aks", "azure functions", "arm templates", "azure devops"],
    "gcp": ["gcp", "google cloud", "gke", "bigquery", "cloud run", "cloud functions"],

    # Infrastructure
    "kubernetes": ["kubernetes", "k8s", "helm", "kubectl", "container orchestration"],
    "terraform": ["terraform", "hcl", "infrastructure as code", "iac"],
    "docker": ["docker", "containers", "containerization"],
    "ansible": ["ansible", "playbooks"],

    # CI/CD
    "cicd": ["ci/cd", "cicd", "continuous integration", "continuous deployment", "jenkins", "github actions", "gitlab ci"],
    "gitops": ["gitops", "argocd", "flux"],

    # Programming
    "python": ["python"],
    "go": ["golang", "go lang"],
    "javascript": ["javascript", "typescript", "node.js", "nodejs"],

    # Databases
    "sql": ["sql", "postgresql", "mysql", "database"],
    "nosql": ["nosql", "mongodb", "dynamodb", "redis"],

    # Monitoring
    "monitoring": ["monitoring", "observability", "prometheus", "grafana", "datadog", "splunk"],

    # Security
    "security": ["security", "devsecops", "compliance", "soc2", "pci"],

    # Architecture
    "architecture": ["architecture", "system design", "distributed systems", "microservices"],
}

# Company priority levels
COMPANY_PRIORITY_SCORES = {
    "high": 10,
    "medium": 7,
    "low": 4,
}

# Seniority level detection patterns
SENIORITY_PATTERNS = {
    "entry": [r"junior", r"entry.?level", r"graduate", r"intern", r"i\b", r"level.?1"],
    "mid": [r"mid.?level", r"intermediate", r"ii\b", r"level.?2"],
    "senior": [r"senior", r"sr\.?", r"iii\b", r"level.?3", r"lead"],
    "staff": [r"staff", r"principal", r"iv\b", r"level.?4"],
    "director": [r"director", r"head.?of", r"vp", r"vice.?president"],
}


@dataclass
class MatchScore:
    """Detailed match score breakdown."""

    total: float = 0.0
    skill_score: float = 0.0
    experience_score: float = 0.0
    certification_score: float = 0.0
    salary_score: float = 0.0
    company_score: float = 0.0
    growth_score: float = 0.0

    # Details
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    matched_certs: List[str] = field(default_factory=list)
    tier: str = ""  # strong|good|stretch|below

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": round(self.total, 1),
            "breakdown": {
                "skills": round(self.skill_score, 1),
                "experience": round(self.experience_score, 1),
                "certifications": round(self.certification_score, 1),
                "salary": round(self.salary_score, 1),
                "company": round(self.company_score, 1),
                "growth": round(self.growth_score, 1),
            },
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "matched_certs": self.matched_certs,
            "tier": self.tier,
        }


@dataclass
class MatchConfig:
    """Configuration for matching algorithm."""

    # Weights (must sum to 100)
    skill_weight: float = 35.0
    experience_weight: float = 20.0
    certification_weight: float = 15.0
    salary_weight: float = 15.0
    company_weight: float = 10.0
    growth_weight: float = 5.0

    # Thresholds
    strong_threshold: float = 80.0
    good_threshold: float = 70.0
    stretch_threshold: float = 60.0

    # Salary preferences
    min_salary_yearly: Optional[int] = None
    min_salary_monthly: Optional[int] = None

    # Company preferences
    company_priorities: Dict[str, str] = field(default_factory=dict)  # company -> priority

    # Learning openness
    willing_to_upskill: bool = True
    target_domains: List[str] = field(default_factory=list)


class JobMatcher:
    """Matches job postings against candidate profiles."""

    def __init__(self, config: Optional[MatchConfig] = None):
        self.config = config or MatchConfig()

    def match(
        self,
        job: JobPosting,
        profile: CandidateProfile
    ) -> MatchScore:
        """
        Calculate match score between job and candidate.

        Args:
            job: Job posting to evaluate
            profile: Candidate profile

        Returns:
            MatchScore with detailed breakdown
        """
        score = MatchScore()

        # 1. Skill overlap (35%)
        skill_result = self._score_skills(job, profile)
        score.skill_score = skill_result["score"] * self.config.skill_weight / 100
        score.matched_skills = skill_result["matched"]
        score.missing_skills = skill_result["missing"]

        # 2. Experience level (20%)
        score.experience_score = self._score_experience(job, profile) * self.config.experience_weight / 100

        # 3. Certification match (15%)
        cert_result = self._score_certifications(job, profile)
        score.certification_score = cert_result["score"] * self.config.certification_weight / 100
        score.matched_certs = cert_result["matched"]

        # 4. Salary fit (15%)
        score.salary_score = self._score_salary(job) * self.config.salary_weight / 100

        # 5. Company priority (10%)
        score.company_score = self._score_company(job) * self.config.company_weight / 100

        # 6. Growth opportunity (5%)
        score.growth_score = self._score_growth(job) * self.config.growth_weight / 100

        # Calculate total
        score.total = (
            score.skill_score +
            score.experience_score +
            score.certification_score +
            score.salary_score +
            score.company_score +
            score.growth_score
        )

        # Determine tier
        if score.total >= self.config.strong_threshold:
            score.tier = "strong"
        elif score.total >= self.config.good_threshold:
            score.tier = "good"
        elif score.total >= self.config.stretch_threshold:
            score.tier = "stretch"
        else:
            score.tier = "below"

        return score

    def _score_skills(
        self,
        job: JobPosting,
        profile: CandidateProfile
    ) -> Dict[str, Any]:
        """Score skill overlap."""
        job_text = f"{job.title} {job.description_full} {' '.join(job.requirements)}".lower()

        # Get candidate skills
        candidate_skills = set()
        for category, skills in profile.skills.items():
            candidate_skills.update(skills.keys())

        # Extract required skills from job
        required_skills = set()
        for skill_key, keywords in SKILL_KEYWORDS.items():
            if any(kw in job_text for kw in keywords):
                required_skills.add(skill_key)

        # Also check explicit requirements
        for req in job.requirements:
            req_lower = req.lower()
            for skill_key, keywords in SKILL_KEYWORDS.items():
                if any(kw in req_lower for kw in keywords):
                    required_skills.add(skill_key)

        if not required_skills:
            # If no skills detected, give moderate score
            return {"score": 70.0, "matched": [], "missing": []}

        # Calculate overlap
        matched = candidate_skills & required_skills
        missing = required_skills - candidate_skills

        overlap_ratio = len(matched) / len(required_skills) if required_skills else 0

        return {
            "score": overlap_ratio * 100,
            "matched": list(matched),
            "missing": list(missing),
        }

    def _score_experience(
        self,
        job: JobPosting,
        profile: CandidateProfile
    ) -> float:
        """Score experience level match."""
        job_text = f"{job.title} {job.description_full}".lower()
        candidate_years = profile.years_experience

        # Detect required seniority from job
        required_seniority = "mid"  # Default assumption
        for level, patterns in SENIORITY_PATTERNS.items():
            if any(re.search(p, job_text) for p in patterns):
                required_seniority = level
                break

        # Extract years requirement if mentioned
        years_match = re.search(r"(\d+)\+?\s*years?", job_text)
        required_years = int(years_match.group(1)) if years_match else 0

        # Score based on seniority alignment
        seniority_years = {
            "entry": (0, 2),
            "mid": (2, 5),
            "senior": (5, 10),
            "staff": (8, 15),
            "director": (12, 25),
        }

        min_years, max_years = seniority_years.get(required_seniority, (2, 5))

        if required_years > 0:
            min_years = max(min_years, required_years)

        # Calculate score
        if candidate_years >= min_years:
            if candidate_years <= max_years + 3:  # Allow some over-qualification
                return 100.0
            else:
                # Slight penalty for over-qualification
                return 80.0
        else:
            # Under-qualified
            gap = min_years - candidate_years
            return max(0, 100 - gap * 15)

    def _score_certifications(
        self,
        job: JobPosting,
        profile: CandidateProfile
    ) -> Dict[str, Any]:
        """Score certification match."""
        job_text = f"{job.title} {job.description_full} {' '.join(job.requirements)}".lower()

        # Certification patterns to detect in job
        cert_patterns = {
            "aws_solutions_architect": [r"aws\s*(certified)?\s*solutions?\s*architect"],
            "aws_devops": [r"aws\s*(certified)?\s*devops"],
            "azure_solutions_architect": [r"az-?\s*305", r"azure\s*solutions?\s*architect"],
            "azure_administrator": [r"az-?\s*104", r"azure\s*administrator"],
            "gcp_architect": [r"gcp\s*(certified)?\s*professional\s*cloud\s*architect"],
            "kubernetes": [r"cka\b", r"ckad\b", r"certified\s*kubernetes"],
            "terraform": [r"terraform\s*associate", r"hct[ao]-?\d+"],
        }

        # Candidate certifications normalized
        candidate_certs = set()
        for cert in profile.certifications:
            cert_lower = cert.lower()
            if "aws" in cert_lower and "solutions" in cert_lower:
                candidate_certs.add("aws_solutions_architect")
            if "aws" in cert_lower and "devops" in cert_lower:
                candidate_certs.add("aws_devops")
            if "azure" in cert_lower and ("305" in cert_lower or "architect" in cert_lower):
                candidate_certs.add("azure_solutions_architect")
            if "azure" in cert_lower and ("104" in cert_lower or "administrator" in cert_lower):
                candidate_certs.add("azure_administrator")
            if "gcp" in cert_lower and "architect" in cert_lower:
                candidate_certs.add("gcp_architect")
            if "kubernetes" in cert_lower or "cka" in cert_lower or "ckad" in cert_lower:
                candidate_certs.add("kubernetes")
            if "terraform" in cert_lower:
                candidate_certs.add("terraform")

        # Find required certifications
        required_certs = set()
        for cert_key, patterns in cert_patterns.items():
            if any(re.search(p, job_text) for p in patterns):
                required_certs.add(cert_key)

        if not required_certs:
            # No specific certs required, give full credit if candidate has relevant ones
            if candidate_certs:
                return {"score": 100.0, "matched": list(candidate_certs)}
            return {"score": 80.0, "matched": []}

        matched = candidate_certs & required_certs

        if len(matched) == len(required_certs):
            return {"score": 100.0, "matched": list(matched)}
        elif matched:
            return {"score": len(matched) / len(required_certs) * 100, "matched": list(matched)}
        else:
            # No matching certs but candidate has related ones
            if candidate_certs:
                return {"score": 40.0, "matched": []}
            return {"score": 0.0, "matched": []}

    def _score_salary(self, job: JobPosting) -> float:
        """Score salary fit."""
        if not job.salary_max and not job.salary_min:
            # No salary info - neutral score
            return 75.0

        job_salary = job.salary_max or job.salary_min

        # Normalize to yearly USD
        if job.salary_period == "monthly":
            job_salary *= 12
        elif job.salary_period == "hourly":
            job_salary *= 2080  # ~40h/week * 52 weeks

        # TODO: Add currency conversion if needed

        # Check against minimum
        min_salary = self.config.min_salary_yearly
        if not min_salary and self.config.min_salary_monthly:
            min_salary = self.config.min_salary_monthly * 12

        if not min_salary:
            return 100.0  # No minimum set

        if job_salary >= min_salary:
            # Bonus for significantly higher
            if job_salary >= min_salary * 1.3:
                return 100.0
            return 100.0
        else:
            # Below minimum
            ratio = job_salary / min_salary
            if ratio >= 0.9:
                return 80.0  # Within 10%
            elif ratio >= 0.8:
                return 50.0  # Within 20%
            else:
                return 20.0  # Significantly below

    def _score_company(self, job: JobPosting) -> float:
        """Score company priority."""
        company_lower = job.company.lower()

        # Check configured priorities
        for company, priority in self.config.company_priorities.items():
            if company.lower() in company_lower:
                return COMPANY_PRIORITY_SCORES.get(priority, 5) * 10

        # Check company type for default scoring
        if job.company_type == "ai_native":
            return 90.0
        elif job.company_type == "quant":
            return 90.0
        elif job.company_type == "fintech":
            return 85.0
        elif job.company_type == "big_tech":
            return 80.0
        elif job.company_type == "cloud_vendor":
            return 80.0
        elif job.company_type == "consulting":
            return 60.0

        return 70.0  # Unknown company

    def _score_growth(self, job: JobPosting) -> float:
        """Score growth opportunity for willing-to-learn candidates."""
        if not self.config.willing_to_upskill:
            return 50.0  # Neutral

        job_text = f"{job.description_full} {' '.join(job.requirements)}".lower()

        # Check for AI-adjacent signals
        signal_count = sum(1 for signal in AI_ADJACENT_SIGNALS if signal in job_text)

        if signal_count >= 3:
            return 100.0
        elif signal_count >= 2:
            return 90.0
        elif signal_count >= 1:
            return 80.0

        # Check if job mentions target domains
        for domain in self.config.target_domains:
            if domain.lower() in job_text:
                return 85.0

        return 50.0  # No clear growth signals

    def batch_match(
        self,
        jobs: List[JobPosting],
        profile: CandidateProfile,
        min_score: Optional[float] = None
    ) -> List[Tuple[JobPosting, MatchScore]]:
        """
        Match multiple jobs against a profile.

        Args:
            jobs: List of job postings
            profile: Candidate profile
            min_score: Minimum score to include (default: stretch_threshold)

        Returns:
            List of (job, score) tuples sorted by score descending
        """
        if min_score is None:
            min_score = self.config.stretch_threshold

        results = []
        for job in jobs:
            score = self.match(job, profile)
            if score.total >= min_score:
                results.append((job, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1].total, reverse=True)

        return results

    def get_match_report(
        self,
        job: JobPosting,
        profile: CandidateProfile
    ) -> str:
        """
        Generate detailed match report as markdown.

        Args:
            job: Job posting
            profile: Candidate profile

        Returns:
            Markdown formatted report
        """
        score = self.match(job, profile)

        lines = [
            f"## {job.title} at {job.company}",
            f"**Match Score: {score.total:.0f}%** ({score.tier.title()} Match)",
            "",
            "| Factor | Score | Weight | Contribution |",
            "|--------|-------|--------|--------------|",
            f"| Skills | {score.skill_score / self.config.skill_weight * 100:.0f}% | {self.config.skill_weight:.0f}% | {score.skill_score:.1f} |",
            f"| Experience | {score.experience_score / self.config.experience_weight * 100:.0f}% | {self.config.experience_weight:.0f}% | {score.experience_score:.1f} |",
            f"| Certifications | {score.certification_score / self.config.certification_weight * 100:.0f}% | {self.config.certification_weight:.0f}% | {score.certification_score:.1f} |",
            f"| Salary | {score.salary_score / self.config.salary_weight * 100:.0f}% | {self.config.salary_weight:.0f}% | {score.salary_score:.1f} |",
            f"| Company | {score.company_score / self.config.company_weight * 100:.0f}% | {self.config.company_weight:.0f}% | {score.company_score:.1f} |",
            f"| Growth | {score.growth_score / self.config.growth_weight * 100:.0f}% | {self.config.growth_weight:.0f}% | {score.growth_score:.1f} |",
            "",
            "### Skills Analysis",
            "",
        ]

        if score.matched_skills:
            lines.append("**Matched Skills:**")
            for skill in score.matched_skills:
                lines.append(f"- {skill}")
            lines.append("")

        if score.missing_skills:
            lines.append("**Gap Areas:**")
            for skill in score.missing_skills:
                lines.append(f"- {skill}")
            lines.append("")

        if score.matched_certs:
            lines.append("**Matching Certifications:**")
            for cert in score.matched_certs:
                lines.append(f"- {cert}")
            lines.append("")

        # Job details
        lines.extend([
            "### Job Details",
            "",
            f"- **Location:** {job.location or 'Not specified'}",
            f"- **Remote Policy:** {job.remote_policy or 'Not specified'}",
        ])

        if job.salary_min or job.salary_max:
            salary_str = ""
            if job.salary_min and job.salary_max:
                salary_str = f"${job.salary_min:,} - ${job.salary_max:,}"
            elif job.salary_max:
                salary_str = f"Up to ${job.salary_max:,}"
            else:
                salary_str = f"${job.salary_min:,}+"
            salary_str += f" {job.salary_currency}/{job.salary_period}"
            lines.append(f"- **Salary:** {salary_str}")

        lines.extend([
            f"- **Source:** {job.source}",
            f"- **Apply:** {job.application_url}",
        ])

        return "\n".join(lines)


def match_jobs(
    jobs: List[JobPosting],
    profile: CandidateProfile,
    config: Optional[MatchConfig] = None
) -> List[Tuple[JobPosting, MatchScore]]:
    """
    Convenience function to match jobs against a profile.

    Args:
        jobs: List of job postings
        profile: Candidate profile
        config: Optional match configuration

    Returns:
        List of (job, score) tuples sorted by score descending
    """
    matcher = JobMatcher(config)
    return matcher.batch_match(jobs, profile)
