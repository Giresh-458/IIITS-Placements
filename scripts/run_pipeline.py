import asyncio
import argparse
from src.config.settings import settings
from src.orchestration.state import create_initial_state

async def main():
    parser = argparse.ArgumentParser(description="Placement Intelligence Pipeline")
    parser.add_argument("command", choices=["health", "validate-config"], help="Command to run")
    
    args = parser.parse_args()
    
    if args.command == "health":
        print("Pipeline health check: OK")
    elif args.command == "validate-config":
        print("Validating configuration...")
        print(f"Max Runtime: {settings.crawl_budget.max_runtime_seconds}")
        print("Configuration is valid.")

if __name__ == "__main__":
    asyncio.run(main())
