import re
from typing import Tuple, Optional
from datetime import datetime
from dateutil import parser

def parse_date_to_iso(date_str: str, context: str) -> Optional[str]:
    if not date_str:
        return None
        
    date_str = date_str.lower().strip()
    
    # Standard ISO (YYYY-MM-DD)
    iso_match = re.search(r'(20\d{2})-(\d{2})-(\d{2})', date_str)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"
        
    # Indian Formats (DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY)
    ind_match = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.]((?:20)?\d{2})\b', date_str)
    if ind_match:
        day, month, year = ind_match.groups()
        if len(year) == 2:
            year = "20" + year
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            return f"{year}-{int(month):02d}-{int(day):02d}"
            
    # Explicit written dates (e.g., 3 October 2026, 28th September 2026)
    written_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:,?)\s*(20\d{2})\b', date_str)
    if written_match:
        day, month_str, year = written_match.groups()
        try:
            dt = parser.parse(f"{day} {month_str} {year}")
            return dt.strftime("%Y-%m-%d")
        except:
            pass

    # Month day format without year, extract year from context (e.g. 05th october)
    written_match_noyear = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b', date_str)
    if written_match_noyear:
        day, month_str = written_match_noyear.groups()
        # Find year in context
        year_match = re.search(r'\b(202[4-9])\b', context.lower() + " " + date_str)
        if year_match:
            year = year_match.group(1)
            try:
                dt = parser.parse(f"{day} {month_str} {year}")
                return dt.strftime("%Y-%m-%d")
            except:
                pass
                
    return None

def normalize_dates(raw_text: str, context: str, raw_iso: str = "") -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Returns (event_date, registration_deadline, publication_date, last_modified_date, event_end_date, warnings)
    All returned dates are in YYYY-MM-DD ISO format, or None.
    """
    event_date = None
    registration_deadline = None
    publication_date = None
    last_modified_date = None
    event_end_date = None
    warnings = None
    
    # 1. Fallback / direct ISO attempt
    if raw_iso:
        event_date = parse_date_to_iso(raw_iso, context)
        
    t = (raw_text + " " + context).lower()
    
    # Pattern to match dates
    date_pattern = r'(\d{4}-\d{2}-\d{2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[a-z]+\s*\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+[a-z]+)'
    
    # Registration
    reg_match = re.search(r'(?:register before|registration closes:?|registration deadline:|apply by|last date to register:?|register before)\s*' + date_pattern, t)
    if reg_match:
        parsed = parse_date_to_iso(reg_match.group(1), t)
        if parsed: registration_deadline = parsed
            
    # Publication
    pub_match = re.search(r'(?:published:|published on)\s*' + date_pattern, t)
    if pub_match:
        parsed = parse_date_to_iso(pub_match.group(1), t)
        if parsed: publication_date = parsed
            
    # Event Date
    ev_match = re.search(r'(?:drive:|drive date:|drive scheduled)\s*' + date_pattern, t)
    if ev_match:
        parsed = parse_date_to_iso(ev_match.group(1), t)
        if parsed and not event_date:
            event_date = parsed
            
    # Multi-day
    multi_match = re.search(r'([\d]{1,2})\s*[-?"]\s*([\d]{1,2})\s*([a-z]+)\s*(20\d{2})', t)
    if multi_match:
        d1, d2, month, year = multi_match.groups()
        parsed1 = parse_date_to_iso(f"{d1} {month} {year}", t)
        if parsed1 and not event_date:
            event_date = parsed1
        parsed2 = parse_date_to_iso(f"{d2} {month} {year}", t)
        if parsed2:
            event_end_date = parsed2

    # If simple text date found but no labels, and we still don't have an ISO
    if not event_date and not registration_deadline and not publication_date:
        parsed = parse_date_to_iso(raw_text, t)
        if not parsed:
            # Maybe it's directly in the context?
            match = re.search(date_pattern, t)
            if match:
                parsed = parse_date_to_iso(match.group(1), t)
                
        if parsed:
            event_date = parsed
        else:
            if re.search(r'\d', raw_text):
                warnings = "Could not parse valid date from string"

    return event_date, registration_deadline, publication_date, last_modified_date, event_end_date, warnings
