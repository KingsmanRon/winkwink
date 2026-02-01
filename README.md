# AI-Powered Job Crawler with CV Matching

A Python-based web crawler that intelligently finds job postings aligned to your CV, filters by customizable parameters, and provides comprehensive application support materials including role specifications and interview preparation.

## Features

- **CV Processing**: Parse PDF, DOCX, or text CVs to extract skills, certifications, experience
- **Multi-Source Crawling**: LinkedIn, Indeed, RemoteOK, WeWorkRemotely, company career pages
- **Intelligent Matching**: Score jobs against your profile with detailed breakdown
- **Interview Prep**: Generate tailored preparation materials for different company types
- **Export Options**: CSV, JSON, Notion, and Trello formats

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd job-crawler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```bash
# Parse your CV
jobcrawler parse --cv resume.pdf

# Crawl jobs matching your profile
jobcrawler crawl --cv resume.pdf --keywords "cloud architect" "devops"

# Match stored jobs against your profile
jobcrawler match --cv resume.pdf --threshold 70

# Generate interview prep for a specific job
jobcrawler prep <job_id> --cv resume.pdf

# Export results
jobcrawler export --format notion --min-score 70
```

## Configuration

Copy `config/config.example.yaml` to `config.yaml` and customize:

```yaml
# Salary requirements
salary_minimum_yearly_usd: 190800

# Work arrangement
work_arrangement:
  - remote
  - hybrid

# Target companies
company_categories:
  ai_companies:
    enabled: true
    priority: high
    targets:
      - Anthropic
      - OpenAI
      - NVIDIA

# Role types
role_types:
  core_infrastructure:
    - Cloud Architect
    - Solutions Architect
    - Platform Engineer
```

## Commands

### `crawl`
Crawl job sources and save results.

```bash
jobcrawler crawl --cv resume.pdf --keywords "devops" --remote-only
```

Options:
- `--cv`: Path to CV file (PDF, DOCX, or TXT)
- `--keywords`: Search keywords (can specify multiple)
- `--sources`: Job sources to crawl (linkedin, indeed, remoteok, etc.)
- `--location`: Location filter
- `--remote-only`: Only search for remote jobs
- `--companies`: Target specific companies
- `--max-jobs`: Maximum jobs per source (default: 100)
- `--output`: Output file for results

### `match`
Match stored jobs against candidate profile.

```bash
jobcrawler match --cv resume.pdf --threshold 70
```

Options:
- `--cv`: Path to CV file (required)
- `--threshold`: Minimum match score (default: 60)
- `--limit`: Maximum results to show (default: 50)

### `export`
Export job results to various formats.

```bash
jobcrawler export --format notion --min-score 70
```

Options:
- `--format`: Export format (csv, json, notion, trello)
- `--output`: Output file path
- `--min-score`: Minimum match score to export
- `--status`: Filter by status

### `prep`
Generate interview preparation materials.

```bash
jobcrawler prep <job_id> --cv resume.pdf --use-claude
```

Options:
- `job_id`: Job ID to generate prep for
- `--cv`: Path to CV for personalization
- `--output`: Output file path
- `--use-claude`: Use Claude API for enhanced analysis

### `status`
Show crawler statistics and database status.

```bash
jobcrawler status
```

### `parse`
Parse a CV and show extracted information.

```bash
jobcrawler parse --cv resume.pdf --output profile.json
```

### `update`
Update job status or add notes.

```bash
jobcrawler update <job_id> --status applied --notes "Submitted via website"
```

### `cleanup`
Clean up old jobs from database.

```bash
jobcrawler cleanup --days 60
```

## Matching Algorithm

The matching algorithm scores jobs on multiple factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| Skill Overlap | 35% | Percentage of required skills you have |
| Experience | 20% | Years of experience vs job requirements |
| Certifications | 15% | Matching certifications |
| Salary Fit | 15% | Salary meets minimum threshold |
| Company Priority | 10% | Based on your configured priorities |
| Growth Opportunity | 5% | Bonus for "willing to train" signals |

### Match Tiers

- **Strong Match (80-100%)**: Highly aligned, prioritize these
- **Good Match (70-79%)**: Solid fit, include in main results
- **Stretch Role (60-69%)**: Growth opportunity, may need upskilling
- **Below Threshold (<60%)**: Excluded by default

## Interview Prep Templates

Templates are available for different company types:

- `templates/interview_prep_quant.md` - Quant/Trading companies
- `templates/interview_prep_ai.md` - AI/ML companies
- `templates/interview_prep_bigtech.md` - Big Tech and Cloud Vendors

## Job Sources

### Supported Sources
- LinkedIn Jobs
- Indeed
- RemoteOK (API)
- WeWorkRemotely
- Wellfound (AngelList)
- Levels.fyi
- Company career pages (Greenhouse, Lever boards)

### Adding Custom Sources

Extend the `BaseCrawler` class to add new job sources:

```python
from src.crawler.base import BaseCrawler

class CustomCrawler(BaseCrawler):
    @property
    def source_name(self) -> str:
        return "custom_source"

    async def search_jobs(self, keywords, **kwargs):
        # Implement job search
        pass
```

## Export Formats

### CSV
Standard CSV format for spreadsheets.

### JSON
Full structured data with all job details.

### Notion
CSV formatted for Notion database import with proper column types.

### Trello
JSON format with cards organized by match tier for Kanban boards.

## Environment Variables

```bash
# Optional: Claude API for enhanced interview prep
export ANTHROPIC_API_KEY="your-api-key"
```

## Project Structure

```
job-crawler/
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point
│   ├── cv_parser.py        # CV processing
│   ├── database.py         # SQLite operations
│   ├── matcher.py          # Matching algorithm
│   ├── interview_prep.py   # Prep generation
│   ├── crawler/
│   │   ├── base.py         # Base crawler class
│   │   ├── linkedin.py
│   │   ├── indeed.py
│   │   ├── company_direct.py
│   │   ├── remote_boards.py
│   │   └── aggregator.py
│   └── exporters/
│       ├── csv_export.py
│       ├── notion_export.py
│       └── trello_export.py
├── config/
│   └── config.example.yaml
├── templates/
│   ├── interview_prep_quant.md
│   ├── interview_prep_ai.md
│   └── interview_prep_bigtech.md
├── tests/
├── requirements.txt
└── README.md
```

## Ethical Considerations

1. **No Auto-Applying**: Generates materials but requires manual application
2. **No Credential Storage**: Never saves passwords or auth tokens
3. **Polite Crawling**: Respects robots.txt, rate limiting, rotating user agents
4. **Transparency**: Logs all actions
5. **Data Privacy**: CV data stays local (except optional Claude API)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI
- Uses [aiohttp](https://aiohttp.readthedocs.io/) for async requests
- PDF parsing via [PyMuPDF](https://pymupdf.readthedocs.io/)
- Optional Claude API integration via [anthropic](https://github.com/anthropics/anthropic-sdk-python)
