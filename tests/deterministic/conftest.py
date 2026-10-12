import pytest
import asyncio
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared"

class FixtureHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(os.path.dirname(__file__), '../fixtures'), **kwargs)

    def log_message(self, format, *args):
        pass # Suppress logging

@pytest.fixture(scope="session")
def fixture_server():
    server = HTTPServer(('127.0.0.1', 0), FixtureHandler)
    port = server.server_address[1]
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    yield f"http://127.0.0.1:{port}"
    
    server.shutdown()
    server.server_close()
    thread.join()

def extract_from_file(filename: str, folder: str = 'html', inst: str = "LocalTest"):
    from bs4 import BeautifulSoup
    from src.extraction.event_extractor import extract_event_candidate
    filepath = os.path.join(os.path.dirname(__file__), '../fixtures/placement', folder, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    candidate = extract_event_candidate(html, text, f"http://localhost/{filename}", {'institution': inst, 'seed_url': "http://localhost/"})
    return candidate
