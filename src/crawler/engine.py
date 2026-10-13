import asyncio
import uuid
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.router import Router
from crawlee import Request
from playwright.async_api import async_playwright

from src.models.domain import HiringEventCandidate
from src.extraction.event_extractor import get_page_type, extract_event_candidate
from src.extraction.date_normalizer import extract_dates, is_event_recent
from src.dedup.event_dedup import deduplicate_events, normalize_url
from src.telemetry.crawl_metrics import CrawlTelemetry

class CrawlerEngine:
    def __init__(self, seeds: List[Dict], max_pages: int = 15, max_depth: int = 2):
        self.seeds = seeds
        self.telemetry = CrawlTelemetry(run_id=str(uuid.uuid4()))
        self.discovered_events: List[HiringEventCandidate] = []
        self.global_max_pages = max_pages
        self.global_max_depth = max_depth
        # Reserve URLs when they are queued to make per-source budgets reliable.
        self._scheduled_urls_by_source: Dict[str, set] = {}
        self.router = Router[BeautifulSoupCrawlingContext]()
        self.setup_router()

    def _select_child_urls(
        self,
        hrefs: List[str],
        page_url: str,
        page_text: str,
        seed_url: str,
        scheduled_urls: set,
        remaining_slots: int,
    ) -> List[str]:
        """Select relevant same-host child URLs in document order within budget."""
        if remaining_slots <= 0:
            return []

        base_domain = urlparse(seed_url).netloc
        keywords = ('notice', 'drive', 'hiring', 'career', 'event', 'page', 'archive', 'circular')
        selected = []
        for href in hrefs:
            full_url = normalize_url(urljoin(page_url, href))
            if urlparse(full_url).netloc != base_domain or full_url in scheduled_urls:
                continue
            if not any(keyword in (href + " " + page_text).lower() for keyword in keywords):
                continue

            scheduled_urls.add(full_url)
            selected.append(full_url)
            if len(selected) >= remaining_slots:
                break
        return selected

    def setup_router(self):
        @self.router.default_handler
        async def default_handler(context: BeautifulSoupCrawlingContext):
            url = context.request.url
            depth = context.request.user_data.get('depth', 0)
            seed_url = context.request.user_data.get('seed_url', url)
            inst = context.request.user_data.get('institution', 'UNKNOWN')

            source_max_pages = context.request.user_data.get('max_pages', 15)
            source_max_depth = context.request.user_data.get('max_depth', 2)

            stats = self.telemetry.source_stats.setdefault(
                inst,
                {
                    'pages_visited': 0,
                    'pages_succeeded': 0,
                    'pages_failed': 0,
                    'events_found': 0,
                    'browser_escalations': 0,
                    'stop_reason': None,
                },
            )
            if stats['pages_visited'] >= source_max_pages:
                stats['stop_reason'] = "BUDGET_EXHAUSTED"
                return

            stats['pages_visited'] += 1
            self.telemetry.pages_attempted += 1
            self.telemetry.requests_attempted += 1
            self.telemetry.http_requests += 1

            response = getattr(context, 'http_response', None)
            status_code = getattr(response, 'status_code', None)
            if status_code == 403:
                self.telemetry.forbidden_blocks += 1
                self.telemetry.pages_failed += 1
                self.telemetry.requests_failed += 1
                stats['pages_failed'] += 1
                stats['stop_reason'] = "BLOCKED_OR_FORBIDDEN"
                return
            if status_code is not None and status_code >= 400:
                self.telemetry.pages_failed += 1
                self.telemetry.requests_failed += 1
                stats['pages_failed'] += 1
                stats['stop_reason'] = f"HTTP_{status_code}"
                return

            if "login" in url.lower():
                self.telemetry.authentication_blocks += 1
                self.telemetry.pages_failed += 1
                self.telemetry.requests_failed += 1
                stats['pages_failed'] += 1
                stats['stop_reason'] = "AUTHENTICATION_REQUIRED"
                return

            self.telemetry.pages_succeeded += 1
            self.telemetry.requests_succeeded += 1
            html = str(context.soup)
            text = context.soup.get_text(separator="\n", strip=True)

            # If browser escalation fails, keep extracting from the static HTTP
            # response rather than silently discarding potentially useful evidence.
            if len(text) < 2000 and "loading" in html.lower():
                self.telemetry.browser_escalations += 1
                stats['browser_escalations'] += 1
                html, text = await self.fetch_with_playwright(
                    url, fallback_html=html, fallback_text=text
                )

            get_page_type(url, text)
            candidate = extract_event_candidate(
                html, text, url, {'institution': inst, 'seed_url': seed_url}
            )
            if candidate:
                edate, eraw, econf, rdate, rraw, rconf = extract_dates(text, html)
                candidate.event_date = edate
                candidate.event_date_raw = eraw
                candidate.event_date_confidence = econf
                candidate.registration_deadline = rdate
                candidate.registration_deadline_raw = rraw

                if edate:
                    candidate.is_recent = is_event_recent(
                        edate, datetime(2026, 9, 20), datetime(2026, 10, 4)
                    )
                    if candidate.is_recent:
                        candidate.event_status = "COMPLETED_15D"

                self.discovered_events.append(candidate)
                self.telemetry.event_candidates_found += 1
                stats['events_found'] += 1

            if depth < source_max_depth:
                scheduled_urls = self._scheduled_urls_by_source.setdefault(inst, set())
                remaining_slots = source_max_pages - len(scheduled_urls)
                links = [a['href'] for a in context.soup.find_all('a', href=True)]
                urls_to_enqueue = self._select_child_urls(
                    links, url, context.soup.get_text(), seed_url,
                    scheduled_urls, remaining_slots
                )
                if urls_to_enqueue:
                    requests = [
                        Request.from_url(
                            url=child_url,
                            user_data={
                                'depth': depth + 1,
                                'seed_url': seed_url,
                                'institution': inst,
                                'max_pages': source_max_pages,
                                'max_depth': source_max_depth,
                            },
                        )
                        for child_url in urls_to_enqueue
                    ]
                    await context.add_requests(requests)

    async def fetch_with_playwright(
        self,
        url: str,
        fallback_html: str = "",
        fallback_text: str = "",
    ) -> Tuple[str, str]:
        self.telemetry.browser_pages += 1
        try:
            async with async_playwright() as p:
                browser = None
                try:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    html = await page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text(separator="\n", strip=True)
                    return html, text
                finally:
                    if browser is not None:
                        try:
                            await browser.close()
                        except Exception:
                            # Cleanup failure must not mask already retrieved content.
                            pass
        except Exception:
            self.telemetry.browser_failures += 1
            return fallback_html, fallback_text

    async def run(self):
        self.telemetry.started_at = datetime.utcnow()
        crawler = BeautifulSoupCrawler(
            request_handler=self.router,
            max_request_retries=2,
            request_handler_timeout=timedelta(seconds=20)
        )

        requests = []
        supported_categories = {
            "P0_DIRECT_EVENT_FEED",
            "P0_PUBLIC_EVENT_ARCHIVE",
            "P0_EVENT_INDEX_WITH_CHILD_DETAILS",
        }
        self._scheduled_urls_by_source = {}
        for source in self.seeds:
            if source.get("source_category") not in supported_categories:
                continue

            self.telemetry.sources_attempted += 1
            institution = source["institution"]
            seed_url = normalize_url(source["seed_url"])
            stats = self.telemetry.source_stats.setdefault(
                institution,
                {
                    'pages_visited': 0,
                    'pages_succeeded': 0,
                    'pages_failed': 0,
                    'events_found': 0,
                    'browser_escalations': 0,
                    'stop_reason': None,
                },
            )
            limits = source.get('crawl_limits', {})
            max_pages = limits.get('max_pages', self.global_max_pages)
            max_depth = limits.get('max_depth', self.global_max_depth)
            scheduled_urls = self._scheduled_urls_by_source.setdefault(institution, set())
            if seed_url in scheduled_urls:
                continue
            if len(scheduled_urls) >= max_pages:
                stats["stop_reason"] = "BUDGET_EXHAUSTED"
                continue
            scheduled_urls.add(seed_url)

            requests.append(
                Request.from_url(
                    url=seed_url,
                    user_data={
                        'depth': 0,
                        'seed_url': source['seed_url'],
                        'institution': institution,
                        'max_pages': max_pages,
                        'max_depth': max_depth,
                    },
                )
            )

        await crawler.run(requests)

        for stats in self.telemetry.source_stats.values():
            if stats.get("pages_succeeded", 0) == 0 and not stats.get("stop_reason"):
                stats["stop_reason"] = "NO_SUCCESSFUL_PAGE"

        self.telemetry.sources_succeeded = sum(
            1 for stats in self.telemetry.source_stats.values()
            if stats.get("pages_succeeded", 0) > 0
        )
        self.telemetry.sources_failed = max(
            0, self.telemetry.sources_attempted - self.telemetry.sources_succeeded
        )
        self.telemetry.finished_at = datetime.utcnow()
        self.telemetry.duration_seconds = (
            self.telemetry.finished_at - self.telemetry.started_at
        ).total_seconds()

        self.discovered_events = deduplicate_events(self.discovered_events)
        self.telemetry.events_deduplicated = len(self.discovered_events)

        return self.discovered_events, self.telemetry
