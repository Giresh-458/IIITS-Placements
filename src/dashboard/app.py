import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import json

st.set_page_config(page_title="Placement Intelligence Dashboard", layout="wide")

# API Base
API_URL = "http://localhost:8000"

@st.cache_data(ttl=60)
def fetch_stats():
    try:
        return requests.get(f"{API_URL}/leads/stats/summary").json()
    except:
        return {}

@st.cache_data(ttl=60)
def fetch_leads():
    try:
        return requests.get(f"{API_URL}/leads?page_size=500").json().get("items", [])
    except:
        return []

@st.cache_data(ttl=60)
def fetch_contacts():
    try:
        return requests.get(f"{API_URL}/leads/contacts/list").json()
    except:
        return []

@st.cache_data(ttl=60)
def fetch_health():
    try:
        return requests.get(f"{API_URL}/metrics/sources/health").json()
    except:
        return []

@st.cache_data(ttl=60)
def fetch_runs():
    try:
        return requests.get(f"{API_URL}/metrics/runs").json()
    except:
        return []

@st.cache_data(ttl=60)
def fetch_alerts():
    try:
        res = requests.get(f"{API_URL}/alerts")
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict) and "items" in data:
                return data["items"]
            return data
    except:
        pass
    return []

def render_overview(leads, stats, contacts, health):
    st.header("Operational Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    active_leads = [l for l in leads if l.get("temporal_status") == "ACTIVE_OPPORTUNITY"]
    
    hot_leads = [l for l in leads if l.get("temporal_status") == "HOT_OUTREACH_LEAD"]
    
    with col1:
        st.metric("Active Opportunities", len(active_leads))
    with col2:
        st.metric("Hot Outreach Leads", len(hot_leads))
    with col3:
        st.metric("Qualified Events", stats.get("total_leads", 0))
    with col4:
        st.metric("Companies", len(set(l.get("company_name") for l in leads if l.get("company_name"))))
        
    st.markdown("---")
    col5, col6, col7, col8 = st.columns(4)
    verified_phones = len([c for c in contacts if c.get("status") == "VERIFIED"])
    no_phones = len([c for c in contacts if c.get("status") in ["NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE", "UNKNOWN"]])
    healthy_sources = len([s for s in health if s.get("health") == "HEALTHY"])
    failed_sources = len([s for s in health if s.get("health") in ["FAILED", "DEGRADED", "BLOCKED_OR_FORBIDDEN"]])
    
    with col5:
        st.metric("Verified Phones", verified_phones)
    with col6:
        st.metric("Unverified / No Phone", no_phones)
    with col7:
        st.metric("Healthy Sources", healthy_sources)
    with col8:
        st.metric("Failed/Degraded Sources", failed_sources)

def render_active_opportunities(leads):
    st.header("Active Opportunities 🔴")
    if not leads:
        st.info("No active opportunities found.")
        return
        
    active_leads = [l for l in leads if l.get("temporal_status") == "ACTIVE_OPPORTUNITY"]
    
    if not active_leads:
        st.info("No active opportunities right now.")
        return
        
    df = pd.DataFrame(active_leads)
    
    # Filtering
    col1, col2, col3 = st.columns(3)
    with col1:
        company_filter = st.text_input("Filter by Company")
    with col2:
        role_filter = st.text_input("Filter by Role")
    with col3:
        status_filter = st.selectbox("Event Status", ["All"] + list(df['temporal_status'].dropna().unique()))
        
    if company_filter:
        df = df[df['company_name'].str.contains(company_filter, case=False, na=False)]
    if role_filter:
        df = df[df['role'].str.contains(role_filter, case=False, na=False)]
    if status_filter != "All":
        df = df[df['temporal_status'] == status_filter]
        
    display_df = df[['canonical_event_id', 'outreach_status', 'company_name', 'role', 'branches', 'ctc', 'event_date', 'registration_deadline', 'contact_status', 'target_fit']]
    
    st.dataframe(display_df.drop(columns=['canonical_event_id']), use_container_width=True)

    st.subheader("Event Detail & Evidence View")
    selected_id = st.selectbox("Select a Lead to view details and evidence:", df['canonical_event_id'].tolist(), format_func=lambda x: str(df[df['canonical_event_id']==x]['company_name'].values[0]) + " - " + str(df[df['canonical_event_id']==x]['role'].values[0]) if len(df[df['canonical_event_id']==x]) else x)
    
    if selected_id:
        lead_data = df[df['canonical_event_id'] == selected_id].iloc[0]
        st.write(f"**Company:** {lead_data.get('company_name', 'Unknown')}")
        st.write(f"**Role:** {lead_data.get('role', 'Unknown')}")
        st.write(f"**CTC:** {lead_data.get('ctc', 'Not available')}")
        st.write(f"**Branch Fit:** {lead_data.get('branches', 'Not available')}")
        st.write(f"**Event Date:** {lead_data.get('event_date', 'Unknown')}")
        st.write(f"**Contact Status:** {lead_data.get('contact_status', 'NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE')}")
        
        with st.expander("Evidence Panel"):
            st.write("Source Lineage / Evidence:")
            lineage = lead_data.get("source_lineage", "{}")
            if isinstance(lineage, str):
                try:
                    st.json(json.loads(lineage))
                except:
                    st.text(lineage)
            else:
                st.json(lineage)

def render_hot_leads(leads):
    st.header("Hot Outreach Leads 🟠")
    hot_leads = [l for l in leads if l.get("temporal_status") == "HOT_OUTREACH_LEAD"]
    
    if not hot_leads:
        st.info("No hot outreach leads right now.")
        return
        
    df = pd.DataFrame(hot_leads)
    display_df = df[['company_name', 'role', 'branches', 'ctc', 'event_date', 'contact_status']]
    display_df.columns = ["Company", "Role", "Branch", "CTC", "Completed Date", "Contact Status"]
    st.dataframe(display_df, use_container_width=True)

def render_contact_intelligence(contacts):
    st.header("Contact Intelligence")
    if not contacts:
        st.info("No contact intelligence data.")
        return
        
    df = pd.DataFrame(contacts)
    st.dataframe(df, use_container_width=True)

def render_source_health(health):
    st.header("Source Health")
    if not health:
        st.info("No source health data.")
        return
        
    df = pd.DataFrame(health)
    
    st.subheader("Failed / Degraded Sources")
    failed_df = df[df['health'] != 'HEALTHY']
    if not failed_df.empty:
        st.error(f"Found {len(failed_df)} failing or degraded sources.")
        st.dataframe(failed_df[['institution', 'health', 'stop_reason', 'last_failure']])
    else:
        st.success("All sources are healthy!")
        
    st.subheader("All Sources")
    st.dataframe(df[['institution', 'source_category', 'health', 'events_found', 'pages_visited']], use_container_width=True)

def render_run_history(runs):
    st.header("Run History")
    if not runs:
        st.info("No run history available.")
        return
        
    df = pd.DataFrame([{
        "Run ID": r.get("run_id"),
        "Started At": r.get("started_at"),
        "Status": r.get("terminal_status"),
        "Qualified": r.get("telemetry", {}).get("qualified_events", "N/A"),
        "Duration (s)": r.get("telemetry", {}).get("total_duration_seconds", "N/A")
    } for r in runs])
    
    st.dataframe(df, use_container_width=True)
    
    st.subheader("Latest Run Telemetry")
    st.json(runs[0].get("telemetry", {}))

def render_alerts(alerts):
    st.header("Alerts & Change Detection")
    if not alerts:
        st.info("No alerts found.")
        return
        
    df = pd.DataFrame(alerts)
    if not df.empty:
        if 'change_fingerprint' not in df.columns:
            df['change_fingerprint'] = 'N/A'
        display_df = df[['alert_type', 'priority', 'status', 'change_fingerprint', 'detected_at']]
        st.dataframe(display_df, use_container_width=True)

def render_export():
    st.header("Export Data")
    st.markdown("Download operational CSVs from the API.")
    st.markdown(f"[Download Active Opportunities]({API_URL}/leads/export/active_opportunities)")
    st.markdown(f"[Download Hot Outreach Leads]({API_URL}/leads/export/hot_outreach_leads)")
    st.markdown(f"[Download Companies]({API_URL}/leads/export/companies)")
    st.markdown(f"[Download Contacts/Phones]({API_URL}/leads/export/contacts)")
    st.markdown(f"[Download Run History]({API_URL}/leads/export/run_history)")

def main():
    st.title("Placement Intelligence Dashboard")

    stats = fetch_stats()
    leads = fetch_leads()
    contacts = fetch_contacts()
    health = fetch_health()
    runs = fetch_runs()
    alerts = fetch_alerts()

    tabs = st.tabs([
        "Overview", 
        "Active Opportunities", 
        "Hot Outreach Leads", 
        "Contact Intelligence", 
        "Source Health",
        "Run History",
        "Alerts",
        "Export"
    ])

    with tabs[0]:
        render_overview(leads, stats, contacts, health)
    with tabs[1]:
        render_active_opportunities(leads)
    with tabs[2]:
        render_hot_leads(leads)
    with tabs[3]:
        render_contact_intelligence(contacts)
    with tabs[4]:
        render_source_health(health)
    with tabs[5]:
        render_run_history(runs)
    with tabs[6]:
        render_alerts(alerts)
    with tabs[7]:
        render_export()

if __name__ == "__main__":
    main()
