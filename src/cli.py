"""
CLI Module

Command-line interface for the AI Job Crawler with CV Matching.

Commands:
- crawl: Crawl job sources
- match: Match jobs against candidate profile
- export: Export results to various formats
- prep: Generate interview preparation materials
- status: Show crawl statistics
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, List
import logging

import click
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config(config_path: Optional[str]) -> dict:
    """Load configuration from YAML file."""
    if not config_path:
        # Look for default config locations
        default_paths = [
            Path("config.yaml"),
            Path("config/config.yaml"),
            Path.home() / ".jobcrawler" / "config.yaml",
        ]
        for path in default_paths:
            if path.exists():
                config_path = str(path)
                break

    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    return {}


@click.group()
@click.version_option(version="1.0.0")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, config, verbose):
    """AI-Powered Job Crawler with CV Matching.

    Find jobs aligned to your CV, filter by customizable parameters,
    and generate interview preparation materials.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--cv", type=click.Path(exists=True), help="Path to CV file (PDF, DOCX, or TXT)")
@click.option("--keywords", "-k", multiple=True, help="Search keywords")
@click.option("--sources", "-s", multiple=True, help="Job sources to crawl (linkedin, indeed, remoteok, etc.)")
@click.option("--location", "-l", help="Location filter")
@click.option("--remote-only", is_flag=True, help="Only search for remote jobs")
@click.option("--companies", multiple=True, help="Target specific companies")
@click.option("--max-jobs", default=100, help="Maximum jobs per source")
@click.option("--output", "-o", type=click.Path(), help="Output file for results")
@click.pass_context
def crawl(ctx, cv, keywords, sources, location, remote_only, companies, max_jobs, output):
    """Crawl job sources and save results.

    Example:
        jobcrawler crawl --cv resume.pdf --keywords "cloud architect" "devops"
    """
    from .database import JobDatabase
    from .crawler.aggregator import JobAggregator
    from .cv_parser import CVParser
    from .matcher import JobMatcher, MatchConfig

    config = ctx.obj["config"]

    click.echo("Starting job crawl...")

    # Parse CV if provided
    profile = None
    if cv:
        click.echo(f"Parsing CV: {cv}")
        parser = CVParser()
        profile = parser.parse(cv)
        click.echo(f"  Candidate: {profile.name or 'Unknown'}")
        click.echo(f"  Title: {profile.current_title or 'Not detected'}")
        click.echo(f"  Certifications: {len(profile.certifications)}")

    # Get keywords from config if not provided
    if not keywords:
        role_types = config.get("role_types", {})
        keywords = []
        for titles in role_types.values():
            keywords.extend(titles[:2])
        if not keywords:
            keywords = ["cloud architect", "solutions architect", "devops engineer"]

    # Get sources from config if not provided
    if not sources:
        sources = ["linkedin", "indeed", "remoteok"]

    # Get target companies from config if not provided
    target_companies = list(companies) if companies else []
    if not target_companies and config.get("company_categories"):
        for category, cat_config in config.get("company_categories", {}).items():
            if cat_config.get("enabled") and cat_config.get("priority") == "high":
                target_companies.extend(cat_config.get("targets", [])[:3])

    # Initialize database
    db = JobDatabase()

    click.echo(f"Crawling sources: {', '.join(sources)}")
    click.echo(f"Keywords: {', '.join(keywords)}")
    if target_companies:
        click.echo(f"Target companies: {', '.join(target_companies[:5])}...")

    async def run_crawl():
        async with JobAggregator(db=db) as aggregator:
            jobs = await aggregator.crawl_all(
                keywords=list(keywords),
                sources=list(sources),
                location=location,
                remote_only=remote_only,
                target_companies=target_companies,
                max_jobs_per_source=max_jobs
            )
            return jobs

    jobs = asyncio.run(run_crawl())

    click.echo(f"\nCrawled {len(jobs)} jobs")

    # Match jobs if CV provided
    if profile and jobs:
        click.echo("Matching jobs against profile...")

        match_config = MatchConfig()
        if config.get("salary_minimum_yearly_usd"):
            match_config.min_salary_yearly = config["salary_minimum_yearly_usd"]

        matcher = JobMatcher(match_config)
        results = matcher.batch_match(jobs, profile)

        strong = sum(1 for _, s in results if s.tier == "strong")
        good = sum(1 for _, s in results if s.tier == "good")
        stretch = sum(1 for _, s in results if s.tier == "stretch")

        click.echo(f"  Strong matches: {strong}")
        click.echo(f"  Good matches: {good}")
        click.echo(f"  Stretch roles: {stretch}")

        # Update match scores in database
        for job, score in results:
            db.update_match_score(job.job_id, score.total)

    # Export if output specified
    if output:
        from .exporters.csv_export import export_to_csv
        export_to_csv(jobs, output)
        click.echo(f"Results exported to: {output}")

    click.echo("\nDone!")


@cli.command()
@click.option("--cv", type=click.Path(exists=True), required=True, help="Path to CV file")
@click.option("--threshold", "-t", default=60, help="Minimum match score threshold")
@click.option("--limit", default=50, help="Maximum results to show")
@click.pass_context
def match(ctx, cv, threshold, limit):
    """Match stored jobs against candidate profile.

    Example:
        jobcrawler match --cv resume.pdf --threshold 70
    """
    from .database import JobDatabase
    from .cv_parser import CVParser
    from .matcher import JobMatcher, MatchConfig

    config = ctx.obj["config"]

    click.echo(f"Parsing CV: {cv}")
    parser = CVParser()
    profile = parser.parse(cv)

    click.echo(f"Candidate: {profile.name or 'Unknown'}")
    click.echo(f"Title: {profile.current_title or 'Not detected'}")
    click.echo(f"Years Experience: {profile.years_experience}")
    click.echo(f"Certifications: {len(profile.certifications)}")
    click.echo("")

    # Load jobs from database
    db = JobDatabase()
    jobs = db.get_jobs(limit=500)

    if not jobs:
        click.echo("No jobs in database. Run 'crawl' first.")
        return

    click.echo(f"Matching against {len(jobs)} jobs...")

    # Configure matcher
    match_config = MatchConfig(stretch_threshold=threshold)
    if config.get("salary_minimum_yearly_usd"):
        match_config.min_salary_yearly = config["salary_minimum_yearly_usd"]

    # Set company priorities
    for category, cat_config in config.get("company_categories", {}).items():
        if cat_config.get("enabled"):
            priority = cat_config.get("priority", "medium")
            for company in cat_config.get("targets", []):
                match_config.company_priorities[company.lower()] = priority

    matcher = JobMatcher(match_config)
    results = matcher.batch_match(jobs, profile, min_score=threshold)

    if not results:
        click.echo(f"No jobs found above {threshold}% threshold.")
        return

    # Display results
    click.echo(f"\nFound {len(results)} matching jobs:\n")

    for i, (job, score) in enumerate(results[:limit], 1):
        tier_emoji = {"strong": "🔥", "good": "✅", "stretch": "📈"}.get(score.tier, "")
        click.echo(f"{i}. {tier_emoji} [{score.total:.0f}%] {job.title} @ {job.company}")
        if job.location:
            click.echo(f"   Location: {job.location}")
        if job.salary_max:
            click.echo(f"   Salary: ${job.salary_min:,} - ${job.salary_max:,}")
        click.echo(f"   Apply: {job.application_url}")
        click.echo("")

        # Update score in database
        db.update_match_score(job.job_id, score.total)

    # Summary
    click.echo("---")
    strong = sum(1 for _, s in results if s.tier == "strong")
    good = sum(1 for _, s in results if s.tier == "good")
    stretch = sum(1 for _, s in results if s.tier == "stretch")
    click.echo(f"Total: {len(results)} | Strong: {strong} | Good: {good} | Stretch: {stretch}")


@cli.command()
@click.option("--format", "-f", type=click.Choice(["csv", "json", "notion", "trello"]), default="csv")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--min-score", default=60, help="Minimum match score to export")
@click.option("--status", help="Filter by status (new, applied, interviewing)")
@click.pass_context
def export(ctx, format, output, min_score, status):
    """Export job results to various formats.

    Example:
        jobcrawler export --format notion --min-score 70
    """
    from .database import JobDatabase
    from .exporters.csv_export import CSVExporter, JSONExporter
    from .exporters.notion_export import NotionExporter
    from .exporters.trello_export import TrelloExporter

    db = JobDatabase()

    # Get jobs with filters
    jobs = db.get_jobs(
        min_match_score=min_score,
        status=status,
        order_by="match_score DESC"
    )

    if not jobs:
        click.echo("No jobs found matching criteria.")
        return

    click.echo(f"Exporting {len(jobs)} jobs...")

    output_path = Path(output) if output else None

    if format == "csv":
        exporter = CSVExporter(output_path)
        path = exporter.export(jobs)
    elif format == "json":
        exporter = JSONExporter(output_path)
        path = exporter.export(jobs)
    elif format == "notion":
        exporter = NotionExporter(output_path)
        path = exporter.export(jobs)
        click.echo("\nNotion import instructions:")
        click.echo(NotionExporter.get_notion_template_instructions())
    elif format == "trello":
        exporter = TrelloExporter(output_path)
        path = exporter.export(jobs)
        click.echo("\nTrello setup instructions:")
        click.echo(TrelloExporter.get_trello_setup_instructions())

    click.echo(f"\nExported to: {path}")


@cli.command()
@click.argument("job_id")
@click.option("--cv", type=click.Path(exists=True), help="Path to CV file for personalization")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--use-claude", is_flag=True, help="Use Claude API for enhanced analysis")
@click.pass_context
def prep(ctx, job_id, cv, output, use_claude):
    """Generate interview preparation materials for a job.

    Example:
        jobcrawler prep abc123 --cv resume.pdf
    """
    from .database import JobDatabase
    from .cv_parser import CVParser
    from .interview_prep import InterviewPrepGenerator, InterviewPrepConfig
    from .matcher import JobMatcher

    db = JobDatabase()

    # Find job
    job = db.get_job(job_id)
    if not job:
        # Try searching by partial ID
        jobs = db.search_jobs(job_id, limit=5)
        if jobs:
            job = jobs[0]
            click.echo(f"Found job: {job.title} @ {job.company}")
        else:
            click.echo(f"Job not found: {job_id}")
            return

    click.echo(f"Generating interview prep for: {job.title} @ {job.company}")

    # Parse CV if provided
    profile = None
    match_score = None
    if cv:
        parser = CVParser()
        profile = parser.parse(cv)
        matcher = JobMatcher()
        match_score = matcher.match(job, profile)

    # Generate prep
    config = InterviewPrepConfig(use_claude_api=use_claude)
    generator = InterviewPrepGenerator(config)

    if profile:
        prep_content = generator.generate(job, profile, match_score)
    else:
        prep_content = generator.generate_quick_prep(job)

    # Output
    if output:
        with open(output, "w") as f:
            f.write(prep_content)
        click.echo(f"Interview prep saved to: {output}")
    else:
        click.echo("\n" + "=" * 60 + "\n")
        click.echo(prep_content)


@cli.command()
@click.pass_context
def status(ctx):
    """Show crawler statistics and database status."""
    from .database import JobDatabase

    db = JobDatabase()
    stats = db.get_statistics()

    click.echo("Job Crawler Status")
    click.echo("=" * 40)
    click.echo(f"Total jobs in database: {stats['total_jobs']}")
    click.echo("")

    if stats.get("by_status"):
        click.echo("By Status:")
        for status, count in stats["by_status"].items():
            click.echo(f"  {status}: {count}")
        click.echo("")

    if stats.get("by_source"):
        click.echo("By Source:")
        for source, count in list(stats["by_source"].items())[:10]:
            click.echo(f"  {source}: {count}")
        click.echo("")

    if stats.get("by_match_tier"):
        click.echo("By Match Tier:")
        for tier, count in stats["by_match_tier"].items():
            click.echo(f"  {tier}: {count}")
        click.echo("")

    if stats.get("recent_crawls"):
        click.echo("Recent Crawls:")
        for crawl in stats["recent_crawls"][:5]:
            click.echo(f"  {crawl['source']}: {crawl['jobs_found']} found, {crawl['jobs_new']} new")


@cli.command()
@click.option("--cv", type=click.Path(exists=True), required=True, help="Path to CV file")
@click.option("--output", "-o", type=click.Path(), help="Output JSON file")
@click.pass_context
def parse(ctx, cv, output):
    """Parse a CV and show extracted information.

    Example:
        jobcrawler parse --cv resume.pdf
    """
    from .cv_parser import CVParser

    click.echo(f"Parsing CV: {cv}")

    parser = CVParser()
    profile = parser.parse(cv)

    click.echo("\n" + "=" * 40)
    click.echo("CANDIDATE PROFILE")
    click.echo("=" * 40)

    click.echo(f"\nName: {profile.name or 'Not detected'}")
    click.echo(f"Current Title: {profile.current_title or 'Not detected'}")
    click.echo(f"Years of Experience: {profile.years_experience}")

    if profile.certifications:
        click.echo(f"\nCertifications ({len(profile.certifications)}):")
        for cert in profile.certifications:
            click.echo(f"  - {cert}")

    if profile.skills:
        click.echo("\nSkills:")
        for category, skills in profile.skills.items():
            click.echo(f"  {category.replace('_', ' ').title()}:")
            for skill, years in skills.items():
                click.echo(f"    - {skill} ({years}y)")

    if profile.industries:
        click.echo(f"\nIndustries: {', '.join(profile.industries)}")

    if profile.preferred_titles:
        click.echo(f"\nPreferred Titles:")
        for title in profile.preferred_titles:
            click.echo(f"  - {title}")

    if output:
        with open(output, "w") as f:
            f.write(profile.to_json())
        click.echo(f"\nProfile saved to: {output}")


@cli.command()
@click.argument("job_id")
@click.option("--status", type=click.Choice(["new", "applied", "interviewing", "rejected", "offer"]))
@click.option("--notes", help="Add notes to the job")
@click.pass_context
def update(ctx, job_id, status, notes):
    """Update job status or add notes.

    Example:
        jobcrawler update abc123 --status applied --notes "Submitted via website"
    """
    from .database import JobDatabase

    db = JobDatabase()

    job = db.get_job(job_id)
    if not job:
        click.echo(f"Job not found: {job_id}")
        return

    if status:
        db.update_job_status(job_id, status, notes or "")
        click.echo(f"Updated {job.title} @ {job.company} -> {status}")
    elif notes:
        db.update_job_status(job_id, job.status, notes)
        click.echo(f"Added notes to {job.title} @ {job.company}")
    else:
        click.echo("No updates specified. Use --status or --notes")


@cli.command()
@click.option("--days", default=90, help="Delete jobs older than N days")
@click.pass_context
def cleanup(ctx, days):
    """Clean up old jobs from database.

    Example:
        jobcrawler cleanup --days 60
    """
    from .database import JobDatabase

    db = JobDatabase()

    click.confirm(f"Delete jobs older than {days} days?", abort=True)

    deleted = db.delete_old_jobs(days)
    click.echo(f"Deleted {deleted} old jobs")


@cli.command()
@click.option("--cv", type=click.Path(exists=True), help="Path to CV file for matching")
@click.option("--companies", "-c", multiple=True, help="Specific companies to crawl")
@click.option("--category", type=click.Choice(["ai", "quant", "fintech", "bigtech", "all"]), default="all", help="Company category")
@click.option("--keywords", "-k", multiple=True, help="Filter by job title keywords")
@click.pass_context
def targets(ctx, cv, companies, category, keywords):
    """Crawl top target companies directly via their APIs.

    This uses Greenhouse/Lever/Ashby APIs for reliable job fetching.

    Examples:
        jobcrawler targets --category ai --cv resume.pdf
        jobcrawler targets -c anthropic -c stripe -c databricks
        jobcrawler targets --category quant -k "infrastructure" -k "platform"
    """
    from .database import JobDatabase
    from .crawler.company_direct import get_company_crawler, GreenhouseCrawler, LeverCrawler, AshbyCrawler
    from .cv_parser import CVParser
    from .matcher import JobMatcher, MatchConfig

    config = ctx.obj["config"]

    # Define target companies by category
    target_companies = {
        "ai": [
            "anthropic", "openai", "scale_ai", "cohere", "anyscale",
            "modal", "replicate", "together_ai", "perplexity", "mistral",
            "databricks", "hugging_face"
        ],
        "quant": [
            "citadel", "two_sigma", "jane_street", "jump_trading",
            "hudson_river", "optiver", "drw", "imc_trading"
        ],
        "fintech": [
            "stripe", "coinbase", "plaid", "ramp", "brex",
            "affirm", "kraken", "revolut", "block"
        ],
        "bigtech": [
            "netflix", "airbnb", "uber", "pinterest", "doordash",
            "snowflake", "roblox", "meta"
        ]
    }

    # Determine which companies to crawl
    companies_to_crawl = []
    if companies:
        companies_to_crawl = list(companies)
    elif category == "all":
        for cat_companies in target_companies.values():
            companies_to_crawl.extend(cat_companies)
    else:
        companies_to_crawl = target_companies.get(category, [])

    if not companies_to_crawl:
        click.echo("No companies specified. Use --companies or --category")
        return

    click.echo(f"Crawling {len(companies_to_crawl)} target companies...")

    # Parse CV if provided
    profile = None
    if cv:
        click.echo(f"Parsing CV: {cv}")
        parser = CVParser()
        profile = parser.parse(cv)
        click.echo(f"  Candidate: {profile.name or 'Unknown'}")

    # Initialize database
    db = JobDatabase()

    all_jobs = []
    successful = 0
    failed = 0

    async def crawl_company(company_key):
        crawler = get_company_crawler(company_key)
        if not crawler:
            return company_key, []

        jobs = []
        try:
            kw_list = list(keywords) if keywords else None
            async for job in crawler.search_jobs(keywords=kw_list):
                jobs.append(job)
        except Exception as e:
            logger.debug(f"Error crawling {company_key}: {e}")
        finally:
            await crawler.close()

        return company_key, jobs

    async def crawl_all():
        nonlocal successful, failed
        import asyncio

        for company in companies_to_crawl:
            company_key, jobs = await crawl_company(company)
            if jobs:
                click.echo(f"  ✓ {company}: {len(jobs)} jobs")
                all_jobs.extend(jobs)
                successful += 1
            else:
                click.echo(f"  ✗ {company}: no jobs or API unavailable")
                failed += 1

    import asyncio
    asyncio.run(crawl_all())

    click.echo(f"\nCrawled {len(all_jobs)} total jobs from {successful} companies ({failed} unavailable)")

    if all_jobs:
        # Save to database
        result = db.save_jobs(all_jobs)
        click.echo(f"Saved {result['inserted']} new, updated {result['updated']} existing")

        # Match if CV provided
        if profile:
            click.echo("\nMatching jobs against profile...")
            match_config = MatchConfig()
            if config.get("salary_minimum_yearly_usd"):
                match_config.min_salary_yearly = config["salary_minimum_yearly_usd"]

            matcher = JobMatcher(match_config)
            results = matcher.batch_match(all_jobs, profile)

            strong = sum(1 for _, s in results if s.tier == "strong")
            good = sum(1 for _, s in results if s.tier == "good")
            stretch = sum(1 for _, s in results if s.tier == "stretch")

            click.echo(f"  Strong matches: {strong}")
            click.echo(f"  Good matches: {good}")
            click.echo(f"  Stretch roles: {stretch}")

            # Update scores in database
            for job, score in results:
                db.update_match_score(job.job_id, score.total)

    click.echo("\nDone! Run 'jobcrawler match' to see results.")


def main():
    """Main entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
