import re
from typing import Tuple, Optional
from datetime import datetime

def parse_date_with_context(date_str: str, html_context: str = "", current_date: Optional[datetime] = None) -> Tuple[Optional[datetime], str]:
    if not date_str:
        return None, "UNKNOWN"
        
    if not current_date:
        current_date = datetime(2026, 10, 4)
        
    has_explicit_year = bool(re.search(r'\b(202[0-9])\b', date_str))
    
    context_year = None
    if html_context:
        pub_match = re.search(r'\b(202[0-9])\b', html_context)
        if pub_match:
            context_year = pub_match.group(1)
            
    clean_str = re.sub(r'(st|nd|rd|th)\b', '', date_str, flags=re.IGNORECASE).strip()
    
    try:
        from dateutil import parser
        dt = parser.parse(clean_str, fuzzy=True, default=datetime(1900, 1, 1))
        
        confidence = "UNKNOWN"
        final_year = dt.year
        
        if final_year != 1900:
            confidence = "HIGH"
        elif has_explicit_year:
            final_year = dt.year
            confidence = "HIGH"
        elif context_year:
            final_year = int(context_year)
            confidence = "MEDIUM"
        else:
            final_year = current_date.year
            confidence = "LOW"
            
        return dt.replace(year=final_year), confidence
    except:
        return None, "UNKNOWN"

def extract_dates(text: str, html_context: str, current_date: Optional[datetime] = None) -> Tuple[Optional[datetime], str, str, Optional[datetime], str, str]:
    # Extract event date
    event_date_match = re.search(r'\b(Drive Date|Date of Drive|Interview Date|Schedule|Date|Campus Drive|On)\s*[:\-]?\s*[\(\[]?\s*(\d{1,2}[-/]\d{1,2}([-/]\d{2,4})?|\d{1,2}(st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?)\b', text, re.IGNORECASE)
    event_date = None
    event_conf = "UNKNOWN"
    event_raw = None
    if event_date_match:
        event_raw = event_date_match.group(2).strip()
        event_date, event_conf = parse_date_with_context(event_raw, html_context, current_date)
        
    # Extract reg date
    reg_match = re.search(r'\b(Registration Deadline|Apply Before|Last Date)\b.{0,40}\b(\d{1,2}[-/]\d{1,2}([-/]\d{2,4})?|\d{1,2}(st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?)\b', text, re.IGNORECASE)
    reg_date = None
    reg_conf = "UNKNOWN"
    reg_raw = None
    if reg_match:
        reg_raw = reg_match.group(2).strip()
        reg_date, reg_conf = parse_date_with_context(reg_raw, html_context, current_date)
        
    return event_date, event_raw, event_conf, reg_date, reg_raw, reg_conf

def is_event_recent(d: Optional[datetime], window_start: datetime, window_end: datetime) -> bool:
    if not d: return False
    return window_start.date() <= d.date() <= window_end.date()
