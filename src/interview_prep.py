"""
Interview Preparation Generator

Generates tailored interview preparation materials based on company type, role,
and candidate profile. Optionally uses Claude API for enhanced analysis.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from .cv_parser import CandidateProfile
from .database import JobPosting
from .matcher import MatchScore

logger = logging.getLogger(__name__)


@dataclass
class InterviewPrepConfig:
    """Configuration for interview prep generation."""

    templates_dir: Optional[Path] = None
    use_claude_api: bool = False
    claude_api_key: Optional[str] = None


# Quant/Trading interview prep template
QUANT_PREP_TEMPLATE = """
## Technical Preparation for {company}

### System Design Focus Areas
- [ ] Low-latency architecture patterns (sub-millisecond requirements)
- [ ] High-throughput data pipelines (millions of events/sec)
- [ ] Disaster recovery with near-zero RPO/RTO
- [ ] Multi-region active-active deployments
- [ ] Network optimization and colocation strategies

### Quant-Specific Infrastructure Topics
- [ ] Time-series databases (InfluxDB, TimescaleDB, kdb+)
- [ ] Message queues for trading (Kafka, Chronicle Queue, Aeron)
- [ ] Deterministic systems and avoiding GC pauses
- [ ] Market data feed handling
- [ ] Regulatory compliance (SOC2, audit logging)

### Sample Questions to Prepare
1. "Design a system that can process 10 million market events per second with <1ms latency"
2. "How would you ensure exactly-once processing in a distributed trading system?"
3. "Design the infrastructure for deploying ML models that make trading decisions"
4. "How do you handle secrets management and access control for sensitive trading systems?"
5. "Explain your approach to building highly available systems with 99.999% uptime"

### Fintech Compliance Topics
- [ ] PCI-DSS compliance for payment systems
- [ ] SOC2 Type II audit requirements
- [ ] Data residency and GDPR considerations
- [ ] Encryption at rest and in transit standards
- [ ] Audit logging and immutable records

### Questions You Should Ask
- "What's the latency budget for your critical path systems?"
- "How do you handle infrastructure changes during market hours?"
- "What's the on-call structure for infrastructure teams?"
- "How do infrastructure and quant teams collaborate?"
- "What's your deployment strategy for trading systems?"

### Your Transferable Skills to Highlight
{transferable_skills}

### Gap Areas to Address
{gap_areas}
"""

# AI Companies interview prep template
AI_PREP_TEMPLATE = """
## Technical Preparation for {company}

### AI Infrastructure Core Concepts
- [ ] GPU cluster architecture (NVIDIA DGX, cloud GPU instances)
- [ ] Distributed training frameworks (Horovod, DeepSpeed, PyTorch DDP)
- [ ] Model serving patterns (TensorRT, Triton Inference Server, vLLM)
- [ ] Training job orchestration (Kubernetes, Slurm, Ray)
- [ ] Storage for ML (high-throughput for training data, model artifacts)

### MLOps & Platform Topics
- [ ] Feature stores (Feast, Tecton)
- [ ] Experiment tracking (MLflow, Weights & Biases)
- [ ] Model registries and versioning
- [ ] A/B testing infrastructure for models
- [ ] Model monitoring and drift detection

### LLM-Specific Infrastructure
- [ ] Inference optimization (batching, KV caching, speculative decoding)
- [ ] Multi-GPU and multi-node serving
- [ ] Cost optimization for GPU workloads
- [ ] Fine-tuning infrastructure
- [ ] RAG system architecture

### Sample Questions to Prepare
1. "Design infrastructure to serve an LLM to 1 million concurrent users"
2. "How would you build a platform for researchers to run distributed training jobs?"
3. "Design a system for A/B testing different model versions in production"
4. "How do you handle GPU failures during a multi-day training run?"
5. "Explain how you would optimize inference costs while maintaining latency SLAs"

### Transferable Skills to Highlight
Your cloud infrastructure background directly applies:
- Kubernetes experience → GPU cluster orchestration
- IaC/Terraform expertise → Reproducible ML environments
- Multi-cloud architecture → GPU availability across providers
- Enterprise architecture → Scalable ML platforms
- Security/compliance → Model access control, audit logging

{transferable_skills}

### Gap Areas to Address
{gap_areas}

### Questions You Should Ask
- "What's your current GPU utilization rate and how do you optimize it?"
- "How do researchers request and get access to compute resources?"
- "What's the biggest infrastructure challenge you're facing right now?"
- "How do you balance research experimentation with production stability?"
- "What's your approach to ML model versioning and rollbacks?"
"""

# Big Tech/Cloud Vendors interview prep template
BIGTECH_PREP_TEMPLATE = """
## Technical Preparation for {company}

### System Design at Scale
- [ ] Design for billions of users
- [ ] Global load balancing and traffic management
- [ ] Microservices architecture patterns
- [ ] Service mesh (Istio, Envoy)
- [ ] Observability at scale (metrics, logs, traces)

### Cloud-Native Deep Dives
- [ ] Kubernetes internals (scheduler, CNI, CSI)
- [ ] Serverless architectures and cold start optimization
- [ ] Multi-tenancy and isolation patterns
- [ ] Cost optimization strategies
- [ ] FinOps principles

### Sample Questions to Prepare
1. "Design the infrastructure for a global CDN"
2. "How would you architect a multi-tenant SaaS platform?"
3. "Design a system for processing 1PB of data daily"
4. "Explain your approach to zero-downtime deployments at scale"
5. "Design a disaster recovery strategy for a global service"

### Leadership/Behavioral (STAR Format)
- [ ] Leading large-scale migrations
- [ ] Incident response and post-mortems
- [ ] Cross-team collaboration examples
- [ ] Mentoring junior engineers
- [ ] Driving technical decisions with stakeholders
- [ ] Handling disagreements with technical approach

### Your Transferable Skills
{transferable_skills}

### Gap Areas to Address
{gap_areas}

### Questions You Should Ask
- "How are architecture decisions made across teams?"
- "What's the typical scope for a senior/staff engineer?"
- "How do you handle technical debt prioritization?"
- "What's the on-call rotation and incident response process?"
- "What learning and development opportunities exist?"
"""

# Fintech interview prep template
FINTECH_PREP_TEMPLATE = """
## Technical Preparation for {company}

### Fintech Infrastructure Focus
- [ ] Payment processing architecture
- [ ] Real-time transaction systems
- [ ] Fraud detection infrastructure
- [ ] Multi-currency and cross-border considerations
- [ ] Regulatory technology (RegTech)

### Compliance & Security Deep Dives
- [ ] PCI-DSS compliance requirements
- [ ] SOC2 Type II controls
- [ ] GDPR and data privacy
- [ ] AML/KYC system infrastructure
- [ ] Encryption and key management

### High Availability & Reliability
- [ ] 99.99%+ uptime architectures
- [ ] Disaster recovery for financial systems
- [ ] Database replication strategies
- [ ] Idempotency in payment systems
- [ ] Reconciliation and audit trails

### Sample Questions to Prepare
1. "Design a payment processing system that handles 10,000 TPS"
2. "How would you ensure exactly-once processing for financial transactions?"
3. "Design the infrastructure for a real-time fraud detection system"
4. "Explain your approach to database migrations with zero downtime"
5. "How do you handle PCI compliance in a containerized environment?"

### Your Transferable Skills
{transferable_skills}

### Gap Areas to Address
{gap_areas}

### Questions You Should Ask
- "What's your approach to handling sensitive financial data?"
- "How do you balance velocity with compliance requirements?"
- "What's the deployment strategy for production payment systems?"
- "How are on-call and incident response handled?"
- "What's the biggest infrastructure challenge you're currently facing?"
"""

# Consulting interview prep template
CONSULTING_PREP_TEMPLATE = """
## Technical Preparation for {company}

### Consulting-Specific Skills
- [ ] Client stakeholder management
- [ ] Technical pre-sales and solution architecture
- [ ] Multi-client environment experience
- [ ] Technology advisory and assessment
- [ ] Enterprise architecture patterns

### Cloud Migration & Modernization
- [ ] Lift-and-shift vs refactoring strategies
- [ ] Legacy system integration
- [ ] Hybrid cloud architectures
- [ ] Cost-benefit analysis for migrations
- [ ] Change management for technical transformations

### Sample Questions to Prepare
1. "Describe a complex migration project you led"
2. "How do you handle competing priorities across multiple clients?"
3. "Explain how you would assess a client's cloud readiness"
4. "How do you handle client pushback on technical recommendations?"
5. "Describe a situation where you had to adapt your approach mid-project"

### Behavioral Focus (Case Study Format)
- [ ] Client conflict resolution examples
- [ ] Managing scope creep
- [ ] Building trust with technical stakeholders
- [ ] Presenting complex topics to non-technical audiences
- [ ] Delivering difficult messages to clients

### Your Transferable Skills
{transferable_skills}

### Gap Areas to Address
{gap_areas}

### Questions You Should Ask
- "How are consultants staffed to projects?"
- "What's the typical project duration and team size?"
- "How does the firm support professional development?"
- "What's the travel expectation for this role?"
- "How do you measure consultant success?"
"""

# General/Unknown company prep template
GENERAL_PREP_TEMPLATE = """
## Technical Preparation for {company}

### Core Technical Topics
- [ ] System design fundamentals
- [ ] Cloud architecture patterns (AWS/Azure/GCP)
- [ ] Kubernetes and container orchestration
- [ ] Infrastructure as Code (Terraform, CloudFormation)
- [ ] CI/CD pipeline design
- [ ] Monitoring and observability

### Sample Questions to Prepare
1. "Walk me through your approach to designing a highly available system"
2. "How do you handle infrastructure as code at scale?"
3. "Describe your experience with Kubernetes in production"
4. "How do you approach capacity planning?"
5. "Explain your disaster recovery strategy"

### Behavioral Topics (STAR Format)
- [ ] Leadership and mentoring examples
- [ ] Conflict resolution
- [ ] Cross-team collaboration
- [ ] Incident response experience
- [ ] Project delivery under pressure

### Your Transferable Skills
{transferable_skills}

### Gap Areas to Address
{gap_areas}

### Questions You Should Ask
- "What does success look like in this role at 30/60/90 days?"
- "What's the biggest technical challenge the team is facing?"
- "How do you approach technical debt?"
- "What's the on-call structure?"
- "What learning and growth opportunities exist?"
"""


class InterviewPrepGenerator:
    """Generates tailored interview preparation materials."""

    def __init__(self, config: Optional[InterviewPrepConfig] = None):
        self.config = config or InterviewPrepConfig()
        self._claude_client = None

    def _get_claude_client(self):
        """Get or create Claude API client."""
        if self._claude_client is None and self.config.use_claude_api:
            api_key = self.config.claude_api_key or os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    import anthropic
                    self._claude_client = anthropic.Anthropic(api_key=api_key)
                except ImportError:
                    logger.warning("anthropic package not installed. Install with: pip install anthropic")
        return self._claude_client

    def generate(
        self,
        job: JobPosting,
        profile: CandidateProfile,
        match_score: Optional[MatchScore] = None
    ) -> str:
        """
        Generate interview preparation materials.

        Args:
            job: Job posting
            profile: Candidate profile
            match_score: Optional match score with breakdown

        Returns:
            Markdown formatted interview prep
        """
        # Determine company type
        company_type = job.company_type or self._detect_company_type(job)

        # Get appropriate template
        template = self._get_template(company_type)

        # Build transferable skills section
        transferable_skills = self._build_transferable_skills(profile, job)

        # Build gap areas section
        gap_areas = self._build_gap_areas(match_score, job)

        # Format template
        prep = template.format(
            company=job.company,
            role=job.title,
            transferable_skills=transferable_skills,
            gap_areas=gap_areas,
        )

        # Add role-specific section
        prep += self._generate_role_specific(job, profile)

        # Add company research section
        prep += self._generate_company_research(job)

        # Optionally enhance with Claude API
        if self.config.use_claude_api:
            prep = self._enhance_with_claude(prep, job, profile)

        return prep

    def _detect_company_type(self, job: JobPosting) -> str:
        """Detect company type from job details."""
        company_lower = job.company.lower()
        desc_lower = job.description_full.lower()

        # Quant/Trading
        quant_keywords = ["trading", "quant", "hedge fund", "market making", "hft", "algorithmic"]
        if any(kw in company_lower or kw in desc_lower for kw in quant_keywords):
            return "quant"

        # AI
        ai_keywords = ["ai", "machine learning", "ml", "llm", "deep learning", "neural"]
        ai_companies = ["anthropic", "openai", "nvidia", "deepmind", "cohere", "mistral"]
        if any(kw in desc_lower for kw in ai_keywords) or any(c in company_lower for c in ai_companies):
            return "ai_native"

        # Fintech
        fintech_keywords = ["payment", "fintech", "financial", "banking", "crypto", "blockchain"]
        if any(kw in company_lower or kw in desc_lower for kw in fintech_keywords):
            return "fintech"

        # Big Tech
        big_tech = ["google", "microsoft", "amazon", "meta", "apple", "netflix"]
        if any(c in company_lower for c in big_tech):
            return "big_tech"

        # Cloud Vendors
        cloud_vendors = ["aws", "azure", "hashicorp", "datadog", "snowflake", "cloudflare"]
        if any(c in company_lower for c in cloud_vendors):
            return "cloud_vendor"

        # Consulting
        consulting = ["deloitte", "accenture", "mckinsey", "bcg", "consulting", "advisory"]
        if any(c in company_lower for c in consulting):
            return "consulting"

        return ""

    def _get_template(self, company_type: str) -> str:
        """Get appropriate template for company type."""
        templates = {
            "quant": QUANT_PREP_TEMPLATE,
            "ai_native": AI_PREP_TEMPLATE,
            "big_tech": BIGTECH_PREP_TEMPLATE,
            "cloud_vendor": BIGTECH_PREP_TEMPLATE,
            "fintech": FINTECH_PREP_TEMPLATE,
            "consulting": CONSULTING_PREP_TEMPLATE,
        }
        return templates.get(company_type, GENERAL_PREP_TEMPLATE)

    def _build_transferable_skills(self, profile: CandidateProfile, job: JobPosting) -> str:
        """Build transferable skills section."""
        lines = []

        # Certifications
        if profile.certifications:
            lines.append("\n**Certifications to Highlight:**")
            for cert in profile.certifications[:5]:
                lines.append(f"- {cert}")

        # Core skills
        if profile.skills:
            lines.append("\n**Technical Skills:**")
            for category, skills in profile.skills.items():
                skill_list = ", ".join(f"{k} ({v}y)" for k, v in list(skills.items())[:3])
                lines.append(f"- {category.replace('_', ' ').title()}: {skill_list}")

        # Experience highlights
        if profile.experience_highlights:
            lines.append("\n**Key Experience:**")
            for highlight in profile.experience_highlights[:3]:
                lines.append(f"- {highlight}")

        # Industry experience
        if profile.industries:
            lines.append(f"\n**Industry Experience:** {', '.join(profile.industries)}")

        return "\n".join(lines) if lines else "- Review your resume for key accomplishments to highlight"

    def _build_gap_areas(self, match_score: Optional[MatchScore], job: JobPosting) -> str:
        """Build gap areas section."""
        lines = []

        if match_score and match_score.missing_skills:
            lines.append("\n**Skills to Address:**")
            for skill in match_score.missing_skills:
                # Suggest how to address each gap
                suggestion = self._get_gap_suggestion(skill)
                lines.append(f"- {skill.replace('_', ' ').title()}: {suggestion}")
        else:
            # Extract potential gaps from job description
            lines.append("\n**Potential Topics to Review:**")
            lines.append("- Review the job description for any unfamiliar technologies")
            lines.append("- Prepare to discuss how your existing skills transfer")

        return "\n".join(lines)

    def _get_gap_suggestion(self, skill: str) -> str:
        """Get suggestion for addressing a skill gap."""
        suggestions = {
            "mlops": "Emphasize Kubernetes experience and ability to learn ML tooling quickly",
            "ai_ml": "Highlight platform/infrastructure skills that support ML teams",
            "kubernetes": "Consider getting CKA certification or building a homelab",
            "terraform": "Highlight IaC experience with other tools, show quick learning ability",
            "python": "Emphasize scripting experience and willingness to develop proficiency",
            "go": "Show programming aptitude with other languages",
            "monitoring": "Discuss observability principles and experience with any monitoring tools",
            "security": "Highlight compliance experience and security awareness",
        }
        return suggestions.get(skill, "Acknowledge gap and show eagerness to learn")

    def _generate_role_specific(self, job: JobPosting, profile: CandidateProfile) -> str:
        """Generate role-specific preparation section."""
        lines = ["\n\n### Role-Specific Preparation\n"]

        title_lower = job.title.lower()

        if "architect" in title_lower:
            lines.extend([
                "**For Architecture Roles:**",
                "- Prepare 2-3 system design case studies from your experience",
                "- Be ready to whiteboard complex architectures",
                "- Know trade-offs between different cloud services",
                "- Prepare examples of cross-team technical leadership",
            ])
        elif "sre" in title_lower or "reliability" in title_lower:
            lines.extend([
                "**For SRE Roles:**",
                "- Review SRE principles (error budgets, SLOs, SLIs)",
                "- Prepare incident response examples (5 Whys, blameless postmortems)",
                "- Know monitoring and alerting best practices",
                "- Be ready to discuss capacity planning",
            ])
        elif "devops" in title_lower:
            lines.extend([
                "**For DevOps Roles:**",
                "- Deep dive on CI/CD pipeline design",
                "- Review GitOps patterns and practices",
                "- Prepare infrastructure automation examples",
                "- Know configuration management approaches",
            ])
        elif "platform" in title_lower:
            lines.extend([
                "**For Platform Roles:**",
                "- Understand internal developer platform (IDP) concepts",
                "- Review self-service infrastructure patterns",
                "- Know developer experience (DX) principles",
                "- Prepare examples of platform product thinking",
            ])
        elif "ml" in title_lower or "machine learning" in title_lower:
            lines.extend([
                "**For ML Infrastructure Roles:**",
                "- Review ML pipeline architectures",
                "- Understand GPU cluster management basics",
                "- Know model serving patterns",
                "- Prepare to discuss experiment tracking and reproducibility",
            ])
        else:
            lines.extend([
                "**General Preparation:**",
                "- Review the job description for specific technologies",
                "- Prepare relevant examples from your experience",
                "- Know your resume inside and out",
                "- Prepare questions about the team and role",
            ])

        return "\n".join(lines)

    def _generate_company_research(self, job: JobPosting) -> str:
        """Generate company research section."""
        lines = ["\n\n### Company Research Checklist\n"]

        lines.extend([
            f"- [ ] Review {job.company}'s engineering blog",
            f"- [ ] Check {job.company}'s GitHub/open source projects",
            "- [ ] Read recent news and press releases",
            "- [ ] Look up the team on LinkedIn",
            "- [ ] Review Glassdoor/Levels.fyi for interview experiences",
            "- [ ] Understand the company's tech stack",
            "- [ ] Research the company's culture and values",
            "- [ ] Prepare thoughtful questions about the company's direction",
        ])

        if job.company_type == "ai_native":
            lines.append(f"- [ ] Read {job.company}'s research papers or blog posts")
        elif job.company_type == "fintech":
            lines.append(f"- [ ] Understand {job.company}'s products and regulatory environment")
        elif job.company_type == "quant":
            lines.append(f"- [ ] Research {job.company}'s trading strategies (if public)")

        return "\n".join(lines)

    def _enhance_with_claude(
        self,
        prep: str,
        job: JobPosting,
        profile: CandidateProfile
    ) -> str:
        """Enhance preparation with Claude API analysis."""
        client = self._get_claude_client()
        if not client:
            return prep

        try:
            prompt = f"""You are a career coach helping a candidate prepare for an interview.

Job Title: {job.title}
Company: {job.company}
Job Description: {job.description_full[:2000]}

Candidate Background:
- Current Title: {profile.current_title}
- Years of Experience: {profile.years_experience}
- Certifications: {', '.join(profile.certifications[:5])}
- Skills: {profile.skills}

The candidate has already prepared the following interview prep document:

{prep}

Please provide:
1. 3 additional specific questions they should prepare for based on the job description
2. 2 ways to highlight their strengths for this specific role
3. 1 potential concern the interviewer might have and how to address it

Keep your response concise and actionable."""

            message = client.messages.create(
                model="claude-3-haiku-20240307",  # Use fast model for quick analysis
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            enhancement = message.content[0].text

            prep += f"\n\n### AI-Enhanced Insights\n\n{enhancement}"

        except Exception as e:
            logger.warning(f"Failed to enhance prep with Claude API: {e}")

        return prep

    def generate_quick_prep(self, job: JobPosting) -> str:
        """Generate quick interview prep checklist."""
        lines = [
            f"# Quick Interview Prep: {job.title} at {job.company}\n",
            "## Before the Interview",
            "- [ ] Research the company website and recent news",
            "- [ ] Review the job description thoroughly",
            "- [ ] Prepare your STAR stories (Situation, Task, Action, Result)",
            "- [ ] Test your video/audio setup",
            "- [ ] Prepare questions to ask",
            "",
            "## Key Topics to Review",
        ]

        # Add role-specific topics
        title_lower = job.title.lower()
        if "architect" in title_lower:
            lines.extend([
                "- System design principles",
                "- Cloud architecture patterns",
                "- Trade-off analysis",
            ])
        elif "devops" in title_lower or "sre" in title_lower:
            lines.extend([
                "- CI/CD pipeline design",
                "- Infrastructure as Code",
                "- Incident response procedures",
            ])
        else:
            lines.extend([
                "- Core technical skills from JD",
                "- Relevant project examples",
                "- Team collaboration experiences",
            ])

        lines.extend([
            "",
            "## Questions to Ask",
            "- What does success look like in this role?",
            "- What's the team structure?",
            "- What are the biggest challenges currently?",
            "",
            f"**Apply:** {job.application_url}"
        ])

        return "\n".join(lines)


def generate_interview_prep(
    job: JobPosting,
    profile: CandidateProfile,
    match_score: Optional[MatchScore] = None,
    use_claude: bool = False
) -> str:
    """
    Convenience function to generate interview preparation.

    Args:
        job: Job posting
        profile: Candidate profile
        match_score: Optional match score
        use_claude: Whether to use Claude API for enhancement

    Returns:
        Markdown formatted interview prep
    """
    config = InterviewPrepConfig(use_claude_api=use_claude)
    generator = InterviewPrepGenerator(config)
    return generator.generate(job, profile, match_score)
