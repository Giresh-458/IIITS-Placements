from typing import Optional

def validate_event_candidate(
    comp_norm: Optional[str],
    role_fam: str,
    ctc_amt: Optional[float],
    reg_date: Optional[str],
    ev_date: Optional[str],
    batch_norm: Optional[int],
    campus_mode: str,
    raw_event_text: str = ""
) -> str:
    """
    Evaluates whether a candidate has enough evidence to be considered a real hiring event.
    Returns:
      'VALID_COMPLETE_EVENT'
      'VALID_INCOMPLETE_EVENT'
      'REJECTED_NON_EVENT'
    """
    has_comp = bool(comp_norm and comp_norm.strip() != "")
    has_role = bool(role_fam and role_fam != "UNKNOWN")
    has_ctc = bool(ctc_amt is not None)
    has_reg = bool(reg_date is not None)
    has_date = bool(ev_date is not None)
    has_batch = bool(batch_norm is not None)
    
    text_lower = raw_event_text.lower() if raw_event_text else ""
    
    # Establish EVENT CONTEXT:
    recruitment_context = any(kw in text_lower for kw in [
        "recruitment drive", "campus placement", "hiring", "job opening", 
        "interview scheduled", "placement drive", "placement notice", 
        "recruitment", "interview", "pool campus", "off campus", "walk-in"
    ])
    schedule_context = any(kw in text_lower for kw in [
        "schedule", "date:", "deadline", "register before", "drive date",
        "positions offered", "eligible branch"
    ])
    
    # Source structure evidence: presence of multiple fields often indicates a tabular/structured notice.
    # To be strong evidence *without* explicit keywords, we need at least 3 distinct semantic fields.
    structured_field_count = sum([has_comp, has_role, has_ctc, has_reg, has_date, has_batch])
    structural_context = structured_field_count >= 3
    
    # "explicit event/schedule language associated with an employer"
    employer_schedule_context = has_comp and schedule_context
    
    has_strong_context = recruitment_context or employer_schedule_context or structural_context
    
    if not has_strong_context:
        return "REJECTED_NON_EVENT"
        
    if has_comp:
        if has_date or has_reg:
            # Employer + event-specific date/deadline
            return "VALID_COMPLETE_EVENT"
        if has_role or has_ctc or has_batch:
            # Employer + specific info, context established
            return "VALID_INCOMPLETE_EVENT"
            
    # No company, but has context
    if recruitment_context:
        if (has_ctc and has_reg) or (has_date and has_reg):
            return "VALID_INCOMPLETE_EVENT"
        if has_date and (has_role or has_ctc or has_batch):
            return "VALID_INCOMPLETE_EVENT"
        if has_reg and (has_role or has_ctc or has_batch):
            return "VALID_INCOMPLETE_EVENT"
        
    return "REJECTED_NON_EVENT"
