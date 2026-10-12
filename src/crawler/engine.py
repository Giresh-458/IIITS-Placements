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
        self.router = Router[BeautifulSoupCrawlingContext]()
        self.setup_router()

    def setup_router(self):
        @self.router.default_handler
        async def default_handler(context: BeautifulSoupCrawlingContext):
            url = context.request.url
            depth = context.request.user_data.get('depth', 0)
            seed_url = context.request.user_data.get('seed_url', url)
            inst = context.request.user_data.get('institution', 'UNKNOWN')
            
            # Determine per-source budgets
            source_max_pages = context.request.user_data.get('max_pages', 15)
            source_max_depth = context.request.user_data.get('max_depth', 2)

            # Telemetry tracking
            if inst not in self.telemetry.source_stats:
                self.telemetry.source_stats[inst] = {'pages_visited': 0, 'events_found': 0, 'browser_escalations': 0, 'stop_reason': None}
                
            if self.telemetry.source_stats[inst]['pages_visited'] >= source_max_pages:
                self.telemetry.source_stats[inst]['stop_reason'] = "BUDGET_EXHAUSTED"
                return

            self.telemetry.source_stats[inst]['pages_visited'] += 1
            self.telemetry.pages_attempted += 1
            self.telemetry.http_requests += 1

            if getattr(context, 'http_response', None) and context.http_response.status_code == 403:
                self.telemetry.forbidden_blocks += 1
                self.telemetry.source_stats[inst]['stop_reason'] = "BLOCKED_OR_FORBIDDEN"
                return

            if "login" in context.request.url.lower():
                self.telemetry.authentication_blocks += 1
                self.telemetry.source_stats[inst]['stop_reason'] = "AUTHENTICATION_REQUIRED"
                return

            html = str(context.soup)
            text = context.soup.get_text(separator="\n", strip=True)
            
            # JS Escalation check
            needs_js = False
            if len(text) < 2000 and "loading" in html.lower():
                needs_js = True
            
            if needs_js:
                self.telemetry.browser_escalations += 1
                self.telemetry.source_stats[inst]['browser_escalations'] += 1
                html, text = await self.fetch_with_playwright(url)
            
            page_type = get_page_type(url, text)
            
            candidate = extract_event_candidate(html, text, url, {'institution': inst, 'seed_url': seed_url})
            if candidate:
                edate, eraw, econf, rdate, rraw, rconf = extract_dates(text, html)
                candidate.event_date = edate
                candidate.event_date_raw = eraw
                candidate.event_date_confidence = econf
                candidate.registration_deadline = rdate
                candidate.registration_deadline_raw = rraw
                
                if edate:
                    candidate.is_recent = is_event_recent(edate, datetime(2026, 9, 20), datetime(2026, 10, 4))
                    if candidate.is_recent:
                        candidate.event_status = "COMPLETED_15D"
                    
                self.discovered_events.append(candidate)
                self.telemetry.event_candidates_found += 1
                self.telemetry.source_stats[inst]['events_found'] += 1

            if depth < source_max_depth and self.telemetry.source_stats[inst]['pages_visited'] < source_max_pages:
                base_domain = urlparse(seed_url).netloc
                links = [a['href'] for a in context.soup.find_all('a', href=True)]
                
                urls_to_enqueue = []
                for href in links:
                    full_url = normalize_url(urljoin(url, href))
                    parsed = urlparse(full_url)
                    if parsed.netloc == base_domain:
                        t = (href + " " + context.soup.get_text()).lower()
                        if any(kw in t for kw in ['notice', 'drive', 'hiring', 'career', 'event', 'page', 'archive', 'circular']):
                            urls_to_enqueue.append(full_url)
                            
                # Strict bound
                allowed = source_max_pages - self.telemetry.source_stats[inst]['pages_visited']
                urls_to_enqueue = list(set(urls_to_enqueue))[:allowed]
                
                if urls_to_enqueue:
                    requests = [
                        Request.from_url(
                            url=u,
                            user_data={'depth': depth + 1, 'seed_url': seed_url, 'institution': inst, 'max_pages': source_max_pages, 'max_depth': source_max_depth}
                        ) for u in urls_to_enqueue
                    ]
                    await context.add_requests(requests)

    async def fetch_with_playwright(self, url: str) -> Tuple[str, str]:
        self.telemetry.browser_pages += 1
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=15000)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
                return html, text
            except Exception as e:
                self.telemetry.browser_failures += 1
                return "", ""
            finally:
                await browser.close()

    async def run(self):
        self.telemetry.started_at = datetime.utcnow()
        crawler = BeautifulSoupCrawler(
            request_handler=self.router,
            max_request_retries=2,
            request_handler_timeout=timedelta(seconds=20)
        )
        
        requests = []
        for s in self.seeds:
            self.telemetry.sources_attempted += 1
            if s.get("source_category") in ["P0_DIRECT_EVENT_FEED", "P0_PUBLIC_EVENT_ARCHIVE", "P0_EVENT_INDEX_WITH_CHILD_DETAILS"]:
                limits = s.get('crawl_limits', {})
                max_pages = limits.get('max_pages', self.global_max_pages)
                max_depth = limits.get('max_depth', self.global_max_depth)
                
                req = Request.from_url(
                    url=s['seed_url'],
                    user_data={
                        'depth': 0, 
                        'seed_url': s['seed_url'], 
                        'institution': s['institution'],
                        'max_pages': max_pages,
                        'max_depth': max_depth
                    }
                )
                requests.append(req)
                
        await crawler.run(requests)
        
        self.telemetry.finished_at = datetime.utcnow()
        self.telemetry.duration_seconds = (self.telemetry.finished_at - self.telemetry.started_at).total_seconds()
        
        self.discovered_events = deduplicate_events(self.discovered_events)
        self.telemetry.events_deduplicated = len(self.discovered_events)
        
        return self.discovered_events, self.telemetry
