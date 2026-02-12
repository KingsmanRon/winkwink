"""
CV Processing Module

Accepts CV uploads (PDF, DOCX, or plain text), extracts and parses skills,
experience, certifications, job titles, industries, and education.
Generates a candidate profile JSON with weighted skill relevance scores.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Known certifications and their categories
CERTIFICATION_PATTERNS = {
    # AWS Certifications
    r"aws\s*(certified)?\s*solutions?\s*architect": "AWS Solutions Architect",
    r"aws\s*(certified)?\s*devops\s*engineer": "AWS DevOps Engineer",
    r"aws\s*(certified)?\s*developer": "AWS Developer",
    r"aws\s*(certified)?\s*sysops": "AWS SysOps Administrator",
    r"aws\s*(certified)?\s*cloud\s*practitioner": "AWS Cloud Practitioner",
    r"aws\s*(certified)?\s*machine\s*learning": "AWS Machine Learning",
    r"aws\s*(certified)?\s*data\s*analytics": "AWS Data Analytics",
    r"aws\s*(certified)?\s*database": "AWS Database Specialty",
    r"aws\s*(certified)?\s*security": "AWS Security Specialty",
    r"aws\s*(certified)?\s*networking": "AWS Networking Specialty",

    # Azure Certifications
    r"az-?\s*900": "Azure Fundamentals (AZ-900)",
    r"az-?\s*104": "Azure Administrator Associate (AZ-104)",
    r"az-?\s*204": "Azure Developer Associate (AZ-204)",
    r"az-?\s*305": "Azure Solutions Architect Expert (AZ-305)",
    r"az-?\s*400": "Azure DevOps Engineer Expert (AZ-400)",
    r"azure\s*(solutions?)?\s*architect\s*expert": "Azure Solutions Architect Expert",
    r"azure\s*administrator": "Azure Administrator Associate",
    r"azure\s*devops\s*engineer": "Azure DevOps Engineer Expert",
    r"azure\s*developer": "Azure Developer Associate",
    r"azure\s*fundamentals": "Azure Fundamentals",

    # GCP Certifications
    r"gcp\s*(certified)?\s*professional\s*cloud\s*architect": "GCP Professional Cloud Architect",
    r"gcp\s*(certified)?\s*professional\s*cloud\s*devops": "GCP Professional Cloud DevOps Engineer",
    r"gcp\s*(certified)?\s*associate\s*cloud\s*engineer": "GCP Associate Cloud Engineer",
    r"gcp\s*(certified)?\s*professional\s*data\s*engineer": "GCP Professional Data Engineer",
    r"gcp\s*(certified)?\s*professional\s*ml\s*engineer": "GCP Professional ML Engineer",
    r"google\s*cloud\s*(certified)?\s*professional\s*cloud\s*architect": "GCP Professional Cloud Architect",
    r"google\s*cloud\s*(certified)?\s*professional\s*cloud\s*devops": "GCP Professional Cloud DevOps Engineer",
    r"google\s*cloud\s*(certified)?\s*associate\s*cloud\s*engineer": "GCP Associate Cloud Engineer",

    # HashiCorp Certifications
    r"terraform\s*associate": "Terraform Associate",
    r"hct[ao]-?\d+": "Terraform Associate",
    r"vault\s*associate": "Vault Associate",
    r"consul\s*associate": "Consul Associate",

    # Kubernetes Certifications
    r"cka\b": "Certified Kubernetes Administrator (CKA)",
    r"ckad\b": "Certified Kubernetes Application Developer (CKAD)",
    r"cks\b": "Certified Kubernetes Security Specialist (CKS)",
    r"certified\s*kubernetes\s*administrator": "Certified Kubernetes Administrator (CKA)",
    r"certified\s*kubernetes\s*application\s*developer": "Certified Kubernetes Application Developer (CKAD)",

    # Other Cloud/DevOps
    r"docker\s*certified": "Docker Certified Associate",
    r"red\s*hat\s*certified\s*engineer": "Red Hat Certified Engineer (RHCE)",
    r"rhce\b": "Red Hat Certified Engineer (RHCE)",
    r"rhcsa\b": "Red Hat Certified System Administrator (RHCSA)",

    # Agile/Project Management
    r"safe\s*\d*\s*(practitioner|agilist)": "SAFe Practitioner",
    r"pmp\b": "Project Management Professional (PMP)",
    r"scrum\s*master": "Certified Scrum Master (CSM)",
    r"csm\b": "Certified Scrum Master (CSM)",

    # Other Certifications
    r"microsoft\s*dynamics\s*365\s*fundamentals": "Microsoft Dynamics 365 Fundamentals",
    r"nintex\s*rpa\s*expert": "Nintex RPA Expert",
    r"nintex\s*process\s*automation": "Nintex Process Automation Expert",
}

# Skills and their categories
SKILL_CATEGORIES = {
    "cloud_platforms": {
        "aws": ["aws", "amazon web services", "ec2", "s3", "lambda", "cloudformation", "eks", "ecs", "rds", "dynamodb"],
        "azure": ["azure", "microsoft azure", "aks", "azure functions", "azure devops", "arm templates"],
        "gcp": ["gcp", "google cloud", "gke", "cloud functions", "bigquery", "cloud run"],
    },
    "infrastructure": {
        "kubernetes": ["kubernetes", "k8s", "helm", "kubectl", "eks", "aks", "gke"],
        "terraform": ["terraform", "hcl", "infrastructure as code", "iac"],
        "docker": ["docker", "containers", "containerization", "docker compose"],
        "ansible": ["ansible", "playbooks", "ansible tower"],
        "pulumi": ["pulumi"],
        "cloudformation": ["cloudformation", "cfn"],
    },
    "ci_cd": {
        "jenkins": ["jenkins", "jenkins pipelines"],
        "github_actions": ["github actions", "github workflows"],
        "gitlab_ci": ["gitlab ci", "gitlab pipelines"],
        "azure_devops": ["azure devops", "azure pipelines"],
        "circleci": ["circleci"],
        "argocd": ["argocd", "argo cd", "gitops"],
    },
    "programming": {
        "python": ["python"],
        "go": ["golang", "go lang", "go programming"],
        "javascript": ["javascript", "js", "node.js", "nodejs"],
        "typescript": ["typescript", "ts"],
        "java": ["java"],
        "bash": ["bash", "shell scripting", "shell scripts"],
    },
    "databases": {
        "postgresql": ["postgresql", "postgres", "psql"],
        "mysql": ["mysql"],
        "mongodb": ["mongodb", "mongo"],
        "redis": ["redis"],
        "elasticsearch": ["elasticsearch", "elastic"],
        "dynamodb": ["dynamodb"],
    },
    "monitoring": {
        "prometheus": ["prometheus"],
        "grafana": ["grafana"],
        "datadog": ["datadog"],
        "splunk": ["splunk"],
        "elk": ["elk", "elasticsearch logstash kibana"],
        "cloudwatch": ["cloudwatch"],
    },
    "security": {
        "security": ["security", "cybersecurity", "infosec"],
        "iam": ["iam", "identity and access management"],
        "vault": ["vault", "hashicorp vault", "secrets management"],
        "compliance": ["compliance", "soc2", "pci-dss", "gdpr", "hipaa"],
    },
    "ai_ml": {
        "mlops": ["mlops", "ml ops", "machine learning operations"],
        "mlflow": ["mlflow"],
        "kubeflow": ["kubeflow"],
        "tensorflow": ["tensorflow", "tf"],
        "pytorch": ["pytorch"],
        "sagemaker": ["sagemaker"],
    },
}

# Job title patterns for inferring roles
TITLE_PATTERNS = {
    "Solutions Architect": [r"solutions?\s*architect", r"sa\b"],
    "Cloud Architect": [r"cloud\s*architect"],
    "Platform Engineer": [r"platform\s*engineer"],
    "DevOps Engineer": [r"devops\s*engineer"],
    "Site Reliability Engineer": [r"sre\b", r"site\s*reliability\s*engineer"],
    "Infrastructure Engineer": [r"infrastructure\s*engineer"],
    "Cloud Engineer": [r"cloud\s*engineer"],
    "Principal Engineer": [r"principal\s*engineer"],
    "Staff Engineer": [r"staff\s*engineer"],
    "MLOps Engineer": [r"mlops\s*engineer"],
    "ML Platform Engineer": [r"ml\s*platform\s*engineer"],
}

# Industry patterns
INDUSTRY_PATTERNS = {
    "consulting": [r"consult", r"deloitte", r"accenture", r"mckinsey", r"bcg", r"kpmg", r"pwc", r"ey\b"],
    "fintech": [r"fintech", r"financial\s*technology", r"payments?", r"banking", r"stripe", r"paypal"],
    "automotive": [r"automotive", r"bmw", r"mercedes", r"toyota", r"tesla", r"volkswagen", r"car"],
    "healthcare": [r"health\s*care", r"medical", r"pharmaceutical", r"hospital"],
    "e-commerce": [r"e-?commerce", r"retail", r"amazon", r"shopify"],
    "tech": [r"technology", r"software", r"saas", r"startup"],
    "ai": [r"\bai\b", r"artificial\s*intelligence", r"machine\s*learning", r"deep\s*learning"],
    "cloud": [r"cloud\s*(provider|vendor|services?)", r"aws", r"azure", r"gcp"],
}


@dataclass
class CandidateProfile:
    """Structured candidate profile extracted from CV."""

    name: str = ""
    current_title: str = ""
    years_experience: int = 0
    certifications: List[str] = field(default_factory=list)
    skills: Dict[str, Dict[str, int]] = field(default_factory=dict)
    industries: List[str] = field(default_factory=list)
    education: List[Dict[str, str]] = field(default_factory=list)
    preferred_titles: List[str] = field(default_factory=list)
    experience_highlights: List[str] = field(default_factory=list)
    contact: Dict[str, str] = field(default_factory=dict)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateProfile":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "CandidateProfile":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


class CVParser:
    """Parse CV documents and extract structured candidate profiles."""

    def __init__(self):
        self._pdf_parser = None
        self._docx_parser = None

    def parse(self, file_path: Union[str, Path]) -> CandidateProfile:
        """
        Parse a CV file and return a structured candidate profile.

        Args:
            file_path: Path to CV file (PDF, DOCX, or TXT)

        Returns:
            CandidateProfile with extracted information
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"CV file not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            text = self._parse_pdf(file_path)
        elif suffix in (".docx", ".doc"):
            text = self._parse_docx(file_path)
        elif suffix in (".txt", ".md"):
            text = self._parse_text(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        return self._extract_profile(text)

    def parse_text(self, text: str) -> CandidateProfile:
        """Parse CV from plain text."""
        return self._extract_profile(text)

    def _parse_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            import fitz  # PyMuPDF

            text_parts = []
            with fitz.open(file_path) as doc:
                for page in doc:
                    text_parts.append(page.get_text())
            return "\n".join(text_parts)
        except ImportError:
            try:
                import pdfplumber

                text_parts = []
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                return "\n".join(text_parts)
            except ImportError:
                raise ImportError(
                    "PDF parsing requires either PyMuPDF (fitz) or pdfplumber. "
                    "Install with: pip install pymupdf or pip install pdfplumber"
                )

    def _parse_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            import docx

            doc = docx.Document(file_path)
            text_parts = []

            for para in doc.paragraphs:
                text_parts.append(para.text)

            # Also extract from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text_parts.append(cell.text)

            return "\n".join(text_parts)
        except ImportError:
            raise ImportError(
                "DOCX parsing requires python-docx. "
                "Install with: pip install python-docx"
            )

    def _parse_text(self, file_path: Path) -> str:
        """Read plain text file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _extract_profile(self, text: str) -> CandidateProfile:
        """Extract candidate profile from text."""
        profile = CandidateProfile(raw_text=text)
        text_lower = text.lower()

        # Extract name (usually at the top)
        profile.name = self._extract_name(text)

        # Extract contact info
        profile.contact = self._extract_contact(text)

        # Extract certifications
        profile.certifications = self._extract_certifications(text_lower)

        # Extract skills with experience years
        profile.skills = self._extract_skills(text_lower)

        # Extract years of experience
        profile.years_experience = self._extract_years_experience(text)

        # Extract current title
        profile.current_title = self._extract_current_title(text)

        # Extract industries
        profile.industries = self._extract_industries(text_lower)

        # Extract education
        profile.education = self._extract_education(text)

        # Infer preferred titles based on experience
        profile.preferred_titles = self._infer_preferred_titles(profile)

        # Extract experience highlights
        profile.experience_highlights = self._extract_experience_highlights(text)

        return profile

    def _extract_name(self, text: str) -> str:
        """Extract candidate name from CV."""
        lines = text.strip().split("\n")

        # Usually the name is in the first few lines
        for line in lines[:5]:
            line = line.strip()
            # Skip empty lines and lines that look like headers/titles
            if not line or len(line) < 3:
                continue
            # Skip lines that are clearly not names (contain common CV words)
            skip_words = ["resume", "cv", "curriculum", "vitae", "profile", "summary",
                         "experience", "education", "skills", "contact", "email", "phone",
                         "engineer", "architect", "developer", "manager", "lead", "senior",
                         "junior", "principal", "staff", "cloud", "multi"]
            if any(word in line.lower() for word in skip_words):
                continue
            # Name should be mostly letters and spaces, allow uppercase
            if re.match(r"^[A-Za-z\s\-\'\.]+$", line, re.IGNORECASE) and len(line.split()) <= 4:
                # Normalize case (handle all-caps names)
                return line.title() if line.isupper() else line

        return ""

    def _extract_contact(self, text: str) -> Dict[str, str]:
        """Extract contact information."""
        contact = {}

        # Email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        if email_match:
            contact["email"] = email_match.group()

        # Phone
        phone_match = re.search(r"[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{3,4}[-\s\.]?[0-9]{3,4}", text)
        if phone_match:
            contact["phone"] = phone_match.group()

        # LinkedIn
        linkedin_match = re.search(r"linkedin\.com/in/[\w\-]+", text)
        if linkedin_match:
            contact["linkedin"] = "https://" + linkedin_match.group()

        # GitHub
        github_match = re.search(r"github\.com/[\w\-]+", text)
        if github_match:
            contact["github"] = "https://" + github_match.group()

        return contact

    def _extract_certifications(self, text_lower: str) -> List[str]:
        """Extract certifications from CV text."""
        certifications = set()

        for pattern, cert_name in CERTIFICATION_PATTERNS.items():
            if re.search(pattern, text_lower):
                certifications.add(cert_name)

        return sorted(list(certifications))

    def _extract_skills(self, text_lower: str) -> Dict[str, Dict[str, int]]:
        """Extract skills organized by category with estimated years."""
        skills = {}

        for category, skill_groups in SKILL_CATEGORIES.items():
            category_skills = {}

            for skill_name, patterns in skill_groups.items():
                for pattern in patterns:
                    if re.search(r"\b" + pattern + r"\b", text_lower):
                        # Try to find years of experience for this skill
                        years = self._estimate_skill_years(text_lower, pattern)
                        category_skills[skill_name] = years
                        break

            if category_skills:
                skills[category] = category_skills

        return skills

    def _estimate_skill_years(self, text_lower: str, skill: str) -> int:
        """Estimate years of experience for a skill."""
        # Look for patterns like "5 years of Kubernetes" or "Kubernetes (5 years)"
        patterns = [
            rf"(\d+)\+?\s*years?\s*(?:of\s+)?{skill}",
            rf"{skill}\s*[-–]\s*(\d+)\+?\s*years?",
            rf"{skill}\s*\((\d+)\+?\s*years?\)",
            rf"{skill}.*?(\d+)\+?\s*years?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass

        # Default to 1 year if skill is mentioned but no years specified
        return 1

    def _extract_years_experience(self, text: str) -> int:
        """Extract total years of experience."""
        text_lower = text.lower()

        # Look for explicit mentions
        patterns = [
            r"(\d+)\+?\s*years?\s*(?:of\s+)?(?:professional\s+)?experience",
            r"with\s+(\d+)\+?\s*years?\s*(?:of\s+)?experience",
            r"experience[:\s]+(\d+)\+?\s*years?",
            r"over\s+(\d+)\s*years?",
            r"(\d+)\+?\s*years?\s*in\s+(?:it|tech|software|cloud)",
            r"(\d+)\+?\s*years?\s*(?:of\s+)?(?:designing|building|implementing|developing)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass

        # Try to calculate from date ranges (work history)
        years = self._calculate_years_from_dates(text)
        if years > 0:
            return years

        # Fallback: count years from job history date ranges
        date_range_pattern = r"(\d{4})\s*[-–]\s*(?:present|current|\d{4})"
        matches = re.findall(date_range_pattern, text_lower)
        if matches:
            earliest = min(int(y) for y in matches)
            from datetime import datetime
            return datetime.now().year - earliest

        return 0

    def _calculate_years_from_dates(self, text: str) -> int:
        """Calculate years of experience from date ranges in CV."""
        # Find all year mentions
        year_pattern = r"\b(19|20)\d{2}\b"
        years = [int(y) for y in re.findall(year_pattern, text)]

        if len(years) >= 2:
            current_year = datetime.now().year
            min_year = min(years)
            max_year = min(max(years), current_year)

            if min_year >= 1990 and max_year <= current_year:
                return max_year - min_year

        return 0

    def _extract_current_title(self, text: str) -> str:
        """Extract current job title."""
        text_lower = text.lower()
        lines = text.strip().split("\n")

        # Check first few lines for title (usually right after name)
        title_keywords = ["architect", "engineer", "developer", "manager", "lead",
                         "consultant", "analyst", "specialist", "administrator", "devops",
                         "sre", "platform", "infrastructure", "cloud", "solutions"]
        for line in lines[1:6]:  # Skip first line (name), check next 5
            line_clean = line.strip()
            line_lower = line_clean.lower()
            if any(kw in line_lower for kw in title_keywords):
                # Skip if it's a section header
                if line_lower in ["experience", "skills", "education", "certifications"]:
                    continue
                if len(line_clean) < 60:  # Reasonable title length
                    return line_clean.title() if line_clean.isupper() else line_clean

        # Check for explicit current title patterns
        title_patterns = [
            r"(?:current\s+)?(?:position|title|role)[:\s]+([^\n]+)",
            r"^([^,\n]+),?\s*(?:at|@)\s*\w+",  # Title at Company
        ]

        for pattern in title_patterns:
            match = re.search(pattern, text_lower, re.MULTILINE)
            if match:
                title = match.group(1).strip()
                if len(title) < 100:  # Sanity check
                    return title.title()

        # Infer from known title patterns
        for title, patterns in TITLE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return title

        return ""

    def _extract_industries(self, text_lower: str) -> List[str]:
        """Extract industries candidate has worked in."""
        industries = set()

        for industry, patterns in INDUSTRY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    industries.add(industry)
                    break

        return sorted(list(industries))

    def _extract_education(self, text: str) -> List[Dict[str, str]]:
        """Extract education information."""
        education = []

        # Look for degree patterns
        degree_patterns = [
            r"(bachelor'?s?|b\.?s\.?|b\.?a\.?|b\.?eng\.?|b\.?sc\.?)\s*(?:of|in)?\s*([^,\n]+)",
            r"(master'?s?|m\.?s\.?|m\.?a\.?|m\.?eng\.?|m\.?sc\.?|mba)\s*(?:of|in)?\s*([^,\n]+)",
            r"(ph\.?d\.?|doctor)\s*(?:of|in)?\s*([^,\n]+)",
        ]

        text_lower = text.lower()

        for pattern in degree_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                degree_type = match[0].upper()
                field = match[1].strip().title()

                if len(field) < 100:  # Sanity check
                    education.append({
                        "degree": degree_type,
                        "field": field
                    })

        return education

    def _infer_preferred_titles(self, profile: CandidateProfile) -> List[str]:
        """Infer preferred job titles based on skills and experience."""
        preferred = []

        skills = profile.skills
        certs = [c.lower() for c in profile.certifications]
        years = profile.years_experience

        # Check for cloud architect potential
        cloud_skills = skills.get("cloud_platforms", {})
        if len(cloud_skills) >= 2:
            if years >= 5:
                preferred.extend(["Solutions Architect", "Cloud Architect"])
            else:
                preferred.append("Cloud Engineer")

        # Check for platform/infra roles
        infra_skills = skills.get("infrastructure", {})
        if "kubernetes" in infra_skills or any("kubernetes" in c for c in certs):
            if years >= 5:
                preferred.extend(["Platform Engineer", "Staff Engineer"])
            else:
                preferred.append("Platform Engineer")

        # Check for DevOps/SRE
        ci_cd_skills = skills.get("ci_cd", {})
        if ci_cd_skills:
            preferred.extend(["DevOps Engineer", "Site Reliability Engineer"])

        # Check for ML/AI adjacent
        ml_skills = skills.get("ai_ml", {})
        if ml_skills:
            preferred.extend(["MLOps Engineer", "ML Platform Engineer"])

        # Add senior variants if experienced
        if years >= 7:
            preferred = ["Senior " + t if not t.startswith("Senior") else t for t in preferred]
            preferred.extend(["Principal Engineer", "Staff Engineer"])

        return list(dict.fromkeys(preferred))  # Remove duplicates while preserving order

    def _extract_experience_highlights(self, text: str) -> List[str]:
        """Extract key experience highlights."""
        highlights = []

        # Look for bullet points and achievement-like statements
        patterns = [
            r"[•\-\*]\s*([^\n]+)",  # Bullet points
            r"(?:led|managed|designed|implemented|built|created|developed|architected|migrated)\s+([^\n\.]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:10]:  # Limit to 10 highlights
                if isinstance(match, str) and len(match) > 20 and len(match) < 200:
                    highlights.append(match.strip())

        return highlights[:10]


def load_candidate_profile(file_path: Union[str, Path]) -> CandidateProfile:
    """
    Convenience function to load a candidate profile from a CV file.

    Args:
        file_path: Path to CV file (PDF, DOCX, or TXT)

    Returns:
        CandidateProfile with extracted information
    """
    parser = CVParser()
    return parser.parse(file_path)


def create_profile_from_yaml(yaml_content: str) -> CandidateProfile:
    """
    Create a candidate profile from YAML content.

    This is useful for pre-loaded profiles or testing.
    """
    import yaml

    data = yaml.safe_load(yaml_content)
    return CandidateProfile(
        name=data.get("name", ""),
        current_title=data.get("current_title", ""),
        years_experience=data.get("years_experience", 0),
        certifications=data.get("certifications", []),
        skills=data.get("skills", data.get("core_skills", {})),
        industries=data.get("industries", []),
        education=data.get("education", []),
        preferred_titles=data.get("preferred_titles", []),
        experience_highlights=data.get("experience_highlights", []),
    )
