import json
import os
from datetime import datetime
from src.models.domain import NormalizedHiringEvent
from src.classification.business_rules import apply_business_filters, current_as_of_date

def main():
    print("Loading trusted canonical event dataset...")
    with open('artifacts/normalized_hiring_events.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    events = [NormalizedHiringEvent(**item) for item in data]
    print(f"Loaded {len(events)} canonical events.")
    
    print("Applying business rules (Batch 6)...")
    as_of = current_as_of_date()
    res = apply_business_filters(events, as_of=as_of)
    classifications = res["classifications"]
    
    # Save the output
    classified_data = []
    for ev in events:
        ev_dict = ev.dict()
        cls = classifications[ev.event_id]
        ev_dict["business_classification"] = cls.__dict__
        classified_data.append(ev_dict)
            
    with open('artifacts/classified_events.json', 'w', encoding='utf-8') as f:
        json.dump(classified_data, f, indent=2)
        
    # Generate Batch 6 Report
    md = "# Batch 6: Business Logic & Event Filtering Report\n\n"
    md += f"**Execution Date**: {datetime.utcnow().isoformat()}Z\n"
    md += f"**Qualification As-of Date**: {as_of.date().isoformat()}\n"
    md += f"**Input Dataset**: `artifacts/normalized_hiring_events.json`\n"
    md += f"**Output Dataset**: `artifacts/classified_events.json`\n\n"
    
    md += "## Detailed Canonical Event Table\n"
    md += "| Canonical ID | Institution | Company | Role | Branches | Batch | CTC | Event Date | Reg Deadline | Campus Mode | Role Rel | Fresher Scope | Pkg Qual | Currentness | Temporal Status | Target Fit | Filter Reason |\n"
    md += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    
    for ev in events:
        cls = classifications[ev.event_id]
        company = ev.company_name or "Unknown"
        role = ev.role_family or "UNKNOWN"
        branches = ", ".join(ev.eligible_branches) if ev.eligible_branches else "[]"
        batch = str(ev.graduation_year) if ev.graduation_year else (ev.batch_raw or "UNKNOWN")
        ctc = str(ev.ctc) if ev.ctc else "None"
        ev_date = ev.event_date or "UNKNOWN"
        reg_date = ev.registration_deadline or "UNKNOWN"
        campus_mode = ev.campus_mode or "UNKNOWN"
        
        reasons = ", ".join(cls.filter_reasons) if cls.filter_reasons else "-"
        
        md += f"| `{ev.canonical_identity}` | {ev.institution} | {company} | {role} | {branches} | {batch} | {ctc} | {ev_date} | {reg_date} | {campus_mode} | {cls.role_relevance} | {cls.fresher_scope} | {cls.package_qualification} | {cls.currentness} | **{cls.temporal_status}** | {cls.target_fit} | {reasons} |\n"
        
    with open('artifacts/batch_6_business_logic_report.md', 'w', encoding='utf-8') as f:
        f.write(md)
        
    print("Generated artifacts/batch_6_business_logic_report.md")

if __name__ == '__main__':
    main()
