import json
import os
from src.classification.business_rules import apply_business_filters
from src.models.domain import NormalizedHiringEvent

def run():
    with open('artifacts/normalized_hiring_events.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    events = [NormalizedHiringEvent(**item) for item in data]
    
    results = apply_business_filters(events)
    
    print(f"HOT_OUTREACH_LEAD: {len(results['HOT_OUTREACH_LEAD'])}")
    for ev in results['HOT_OUTREACH_LEAD']:
        print(f" - {ev.company_name} | Role: {ev.role_family} | CTC: {ev.ctc} | Branches: {ev.eligible_branches}")
        
    print(f"\nACTIVE_OPPORTUNITY: {len(results['ACTIVE_OPPORTUNITY'])}")
    for ev in results['ACTIVE_OPPORTUNITY']:
        print(f" - {ev.company_name} | Role: {ev.role_family} | CTC: {ev.ctc} | Branches: {ev.eligible_branches}")
        
    print(f"\nFILTERED_OUT: {len(results['FILTERED_OUT'])}")

if __name__ == '__main__':
    run()
