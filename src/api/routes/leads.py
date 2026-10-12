from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import List, Optional
import json
from src.storage.database import DatabaseManager
from src.storage.models.outreach import OutreachLead

router = APIRouter(prefix="/leads", tags=["leads"])

# In FastAPI, we need to pass the session dependency. 
# We'll attach db_manager to app state or just import it.
# For simplicity, we can do a global dependency.
from src.app.main import db_manager

async def get_session():
    async with db_manager.session_maker() as session:
        yield session

@router.get("")
async def list_leads(
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    company: Optional[str] = None,
    priority: Optional[str] = None,
    contact_status: Optional[str] = None,
    outreach_status: Optional[str] = None,
    branch: Optional[str] = None,
    currently_present: bool = True
):
    stmt = select(OutreachLead).where(OutreachLead.currently_present == currently_present)
    
    if company:
        stmt = stmt.where(OutreachLead.company_name.ilike(f"%{company}%"))
    if priority:
        stmt = stmt.where(OutreachLead.outreach_priority == priority)
    if contact_status:
        stmt = stmt.where(OutreachLead.contact_status == contact_status)
    if outreach_status:
        stmt = stmt.where(OutreachLead.outreach_status == outreach_status)
        
    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await session.scalar(count_stmt)
    
    # Pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    leads = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": leads
    }

@router.get("/companies/list")
async def list_companies(session: AsyncSession = Depends(get_session)):
    query = text("SELECT DISTINCT company_name FROM outreach_leads")
    res = await session.execute(query)
    return [r[0] for r in res]

@router.get("/events/list")
async def list_events(session: AsyncSession = Depends(get_session)):
    query = text("SELECT DISTINCT canonical_event_id, company_name, role, event_date FROM outreach_leads")
    res = await session.execute(query)
    return [{"canonical_event_id": r[0], "company_name": r[1], "role": r[2], "event_date": r[3]} for r in res]

@router.get("/contacts/list")
async def list_contacts(session: AsyncSession = Depends(get_session)):
    query = text("SELECT company, person_name, phone, verification_state FROM outreach_contacts")
    res = await session.execute(query)
    return [{"company": r[0], "name": r[1], "phone": r[2], "status": r[3]} for r in res]

@router.get("/{lead_id}")
async def get_lead(lead_id: str, session: AsyncSession = Depends(get_session)):
    stmt = select(OutreachLead).where(OutreachLead.canonical_event_id == lead_id)
    result = await session.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.patch("/{lead_id}/status")
async def update_outreach_status(
    lead_id: str, 
    status: str, 
    session: AsyncSession = Depends(get_session)
):
    from src.storage.models.outreach import OperationalStatus, AuditLog
    
    try:
        new_status = OperationalStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid operational status")
        
    stmt = select(OutreachLead).where(OutreachLead.canonical_event_id == lead_id)
    result = await session.execute(stmt)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    old_status = lead.outreach_status
    lead.outreach_status = new_status.value
    
    audit = AuditLog(
        entity_type="LEAD",
        entity_id=lead_id,
        action="OUTREACH_STATUS_CHANGED",
        previous_state={"outreach_status": old_status},
        new_state={"outreach_status": new_status.value},
        reason="API Update"
    )
    session.add(audit)
    await session.commit()
    
    return {"status": "success", "outreach_status": new_status.value}

@router.get("/export/{export_type}")
async def export_csv(export_type: str, session: AsyncSession = Depends(get_session)):
    from fastapi.responses import PlainTextResponse
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if export_type == "active_opportunities" or export_type == "hot_outreach_leads":
        target_status = "ACTIVE_OPPORTUNITY" if export_type == "active_opportunities" else "HOT_OUTREACH_LEAD"
        stmt = select(OutreachLead).where(OutreachLead.currently_present == True, OutreachLead.temporal_status == target_status)
        result = await session.execute(stmt)
        leads = result.scalars().all()
        
        writer.writerow(["Lead ID", "Company", "Role", "Event Status", "Outreach Priority", "Contact Status", "Outreach Status", "Event Date"])
        for lead in leads:
            writer.writerow([lead.canonical_event_id, lead.company_name, lead.role, lead.temporal_status, lead.outreach_priority, lead.contact_status, lead.outreach_status, lead.event_date])
            
    elif export_type == "companies":
        query = text("SELECT DISTINCT company_name FROM outreach_leads WHERE company_name IS NOT NULL")
        res = await session.execute(query)
        writer.writerow(["Company Name"])
        for r in res:
            writer.writerow([r[0]])
            
    elif export_type == "contacts" or export_type == "phones":
        from src.storage.models.outreach import OutreachContact
        stmt = select(OutreachContact)
        result = await session.execute(stmt)
        contacts = result.scalars().all()
        
        writer.writerow(["Contact ID", "Company", "Person Name", "Contact Role", "Phone", "Verification State", "Confidence"])
        for c in contacts:
            writer.writerow([c.contact_id, c.company, c.person_name, c.contact_role, c.phone, c.verification_state, c.confidence])
            
    elif export_type == "run_history":
        writer.writerow(["Run ID", "Started At", "Completed At", "Terminal Status", "Total Duration Seconds", "Qualified Events"])
        try:
            with open("artifacts/run_history.jsonl", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        run = json.loads(line)
                        writer.writerow([
                            run.get("run_id"), run.get("started_at"), run.get("completed_at"), 
                            run.get("terminal_status"), run.get("telemetry", {}).get("total_duration_seconds"),
                            run.get("telemetry", {}).get("qualified_events")
                        ])
        except:
            pass
    else:
        raise HTTPException(status_code=400, detail="Invalid export type")
        
    return PlainTextResponse(output.getvalue(), media_type="text/csv")
    
@router.get("/stats/summary")
async def get_stats(session: AsyncSession = Depends(get_session)):
    # Total leads
    total = await session.scalar(select(func.count()).select_from(OutreachLead).where(OutreachLead.currently_present == True))
    
    # Priority breakdown
    p_result = await session.execute(
        select(OutreachLead.outreach_priority, func.count()).where(OutreachLead.currently_present == True).group_by(OutreachLead.outreach_priority)
    )
    priorities = {row[0]: row[1] for row in p_result.all()}
    
    # Contact breakdown
    c_result = await session.execute(
        select(OutreachLead.contact_status, func.count()).where(OutreachLead.currently_present == True).group_by(OutreachLead.contact_status)
    )
    contacts = {row[0]: row[1] for row in c_result.all()}
    
    # Operational Status breakdown
    o_result = await session.execute(
        select(OutreachLead.outreach_status, func.count()).where(OutreachLead.currently_present == True).group_by(OutreachLead.outreach_status)
    )
    operational = {row[0]: row[1] for row in o_result.all()}
    
    return {
        "total_leads": total,
        "by_priority": priorities,
        "by_contact_status": contacts,
        "by_operational_status": operational
    }
