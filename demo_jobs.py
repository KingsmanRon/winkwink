#!/usr/bin/env python3
"""Demo script to populate database with sample jobs for testing."""

import sys
sys.path.insert(0, 'src')

from database import JobDatabase, JobPosting

# Sample job postings
SAMPLE_JOBS = [
    JobPosting(
        job_id="demo001",
        title="Senior Cloud Architect",
        company="Anthropic",
        company_type="ai_native",
        location="San Francisco, CA (Remote)",
        remote_policy="remote",
        salary_min=250000,
        salary_max=350000,
        salary_currency="USD",
        salary_period="yearly",
        requirements=[
            "5+ years cloud infrastructure experience",
            "AWS, Azure, or GCP expertise",
            "Kubernetes and container orchestration",
            "Infrastructure as Code (Terraform)",
            "Strong system design skills"
        ],
        nice_to_have=[
            "ML infrastructure experience",
            "GPU cluster management",
            "Experience with LLM deployment"
        ],
        description_full="""
        We're looking for a Senior Cloud Architect to help build and scale our AI infrastructure.
        You'll work on designing systems that support ML training and inference at scale.
        Strong engineering fundamentals required - we will train on ML-specific tooling.
        This is a platform focus role supporting our ML/AI teams.
        """,
        application_url="https://anthropic.com/careers/cloud-architect",
        posting_date="2026-01-28",
        source="direct_anthropic"
    ),
    JobPosting(
        job_id="demo002",
        title="Infrastructure Engineer - Trading Systems",
        company="Jane Street",
        company_type="quant",
        location="New York, NY",
        remote_policy="hybrid",
        salary_min=300000,
        salary_max=500000,
        salary_currency="USD",
        salary_period="yearly",
        requirements=[
            "Strong systems programming background",
            "Experience with low-latency systems",
            "Linux systems expertise",
            "Network programming knowledge",
            "5+ years infrastructure experience"
        ],
        nice_to_have=[
            "OCaml or functional programming",
            "Trading systems experience",
            "Performance optimization"
        ],
        description_full="""
        Join our infrastructure team to build and maintain trading systems infrastructure.
        We need engineers who understand low-latency, high-throughput systems.
        Experience with distributed systems and Kubernetes is valuable.
        Strong engineering fundamentals - we will train on trading-specific aspects.
        """,
        application_url="https://janestreet.com/careers/infra-engineer",
        posting_date="2026-01-25",
        source="direct_jane_street"
    ),
    JobPosting(
        job_id="demo003",
        title="Platform Engineer",
        company="Stripe",
        company_type="fintech",
        location="Remote (US/EU)",
        remote_policy="remote",
        salary_min=200000,
        salary_max=280000,
        salary_currency="USD",
        salary_period="yearly",
        requirements=[
            "AWS or GCP experience",
            "Kubernetes expertise",
            "Infrastructure as Code",
            "CI/CD pipeline design",
            "4+ years platform engineering"
        ],
        nice_to_have=[
            "Payment systems experience",
            "PCI-DSS compliance knowledge",
            "Ruby or Go programming"
        ],
        description_full="""
        Build the platform that powers global payments infrastructure.
        You'll work on developer experience, deployment systems, and infrastructure reliability.
        Multi-cloud architecture experience with Terraform is essential.
        Strong focus on security and compliance.
        """,
        application_url="https://stripe.com/jobs/platform-engineer",
        posting_date="2026-01-30",
        source="direct_stripe"
    ),
    JobPosting(
        job_id="demo004",
        title="MLOps Engineer",
        company="NVIDIA",
        company_type="ai_native",
        location="Santa Clara, CA (Hybrid)",
        remote_policy="hybrid",
        salary_min=220000,
        salary_max=320000,
        salary_currency="USD",
        salary_period="yearly",
        requirements=[
            "Kubernetes experience",
            "Python programming",
            "CI/CD expertise",
            "Cloud platform experience (AWS/Azure/GCP)"
        ],
        nice_to_have=[
            "GPU programming knowledge",
            "ML framework experience",
            "Distributed training systems"
        ],
        description_full="""
        Join our ML Platform team to build infrastructure for AI model training and deployment.
        No ML experience required - infrastructure background preferred.
        You'll enable data scientists and researchers with tooling and platform capabilities.
        Build tooling for ML experiment tracking and model serving.
        """,
        application_url="https://nvidia.com/careers/mlops",
        posting_date="2026-01-27",
        source="direct_nvidia"
    ),
    JobPosting(
        job_id="demo005",
        title="Site Reliability Engineer",
        company="Google Cloud",
        company_type="big_tech",
        location="London, UK",
        remote_policy="hybrid",
        salary_min=180000,
        salary_max=250000,
        salary_currency="GBP",
        salary_period="yearly",
        requirements=[
            "5+ years SRE/DevOps experience",
            "Strong Linux systems knowledge",
            "Monitoring and observability",
            "Incident management experience",
            "Programming in Python or Go"
        ],
        nice_to_have=[
            "GCP experience",
            "Kubernetes internals knowledge",
            "Distributed systems"
        ],
        description_full="""
        Join Google Cloud SRE to ensure reliability of our cloud platform.
        You'll work on systems that serve millions of customers globally.
        Strong focus on automation, monitoring, and incident response.
        """,
        application_url="https://careers.google.com/jobs/sre-cloud",
        posting_date="2026-01-29",
        source="direct_google"
    ),
    JobPosting(
        job_id="demo006",
        title="DevOps Engineer",
        company="Databricks",
        company_type="ai_native",
        location="Amsterdam, Netherlands (Remote)",
        remote_policy="remote",
        salary_min=150000,
        salary_max=200000,
        salary_currency="EUR",
        salary_period="yearly",
        requirements=[
            "AWS and Azure experience",
            "Terraform expertise",
            "Kubernetes administration",
            "CI/CD pipeline design"
        ],
        nice_to_have=[
            "Spark/data platform experience",
            "Security and compliance",
            "Python scripting"
        ],
        description_full="""
        Help build infrastructure for the data and AI company.
        Support ML/AI teams with robust deployment infrastructure.
        Strong Kubernetes and multi-cloud experience required.
        """,
        application_url="https://databricks.com/careers/devops",
        posting_date="2026-01-26",
        source="direct_databricks"
    ),
    JobPosting(
        job_id="demo007",
        title="Cloud Solutions Architect",
        company="Microsoft Azure",
        company_type="cloud_vendor",
        location="Seattle, WA (Hybrid)",
        remote_policy="hybrid",
        salary_min=180000,
        salary_max=260000,
        salary_currency="USD",
        salary_period="yearly",
        requirements=[
            "Azure certifications (AZ-305 preferred)",
            "5+ years cloud architecture",
            "Customer-facing experience",
            "Multi-cloud knowledge"
        ],
        nice_to_have=[
            "AWS or GCP certifications",
            "Enterprise architecture",
            "Consulting background"
        ],
        description_full="""
        Join the Azure team as a Solutions Architect working with enterprise customers.
        Design and implement cloud solutions for digital transformation.
        Your consulting background will be valuable.
        Strong multi-cloud experience appreciated.
        """,
        application_url="https://careers.microsoft.com/azure-architect",
        posting_date="2026-01-31",
        source="direct_microsoft"
    ),
]

def main():
    db = JobDatabase()

    print("Populating database with sample jobs...")
    result = db.save_jobs(SAMPLE_JOBS)
    print(f"Inserted {result['inserted']} jobs, updated {result['updated']} existing")

    print("\nSample jobs added:")
    for job in SAMPLE_JOBS:
        print(f"  - {job.title} @ {job.company} (${job.salary_min:,} - ${job.salary_max:,})")

if __name__ == "__main__":
    main()
