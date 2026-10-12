import json
import asyncio
from src.crawler.engine import CrawlerEngine

async def run_batch3():
    with open('artifacts/crawl_seed_registry.json', 'r') as f:
        seeds = json.load(f)
        
    # Only test P0
    p0_seeds = [s for s in seeds if s.get("source_category") == "P0_DIRECT_EVENT_FEED"]
    engine = CrawlerEngine(p0_seeds, max_pages=3, max_depth=1)
    events, telemetry = await engine.run()
    
    with open('artifacts/discovered_events.json', 'w') as f:
        json.dump([e.model_dump(mode='json') for e in events], f, indent=2)
        
    with open('artifacts/crawl_telemetry.json', 'w') as f:
        json.dump(telemetry.model_dump(mode='json'), f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_batch3())
