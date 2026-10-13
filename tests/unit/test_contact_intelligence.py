import pytest
from src.models.contact import (
    NormalizedContact, ContactRole, ContactSide, PhoneVerificationState,
    ConfidenceLevel, ContactCurrentness
)
from src.verification.contact_verifier import verify_contact, is_likely_phone

def test_a_official_recruiter():
    # Test A - official recruiter
    c = NormalizedContact(
        contact_id="1",
        company_canonical_id="c1",
        company_name="A",
        contact_role=ContactRole.TALENT_ACQUISITION,
        contact_side=ContactSide.COMPANY,
        phone_raw="+919876543210",
        phone_normalized="+919876543210",
        source_url="http://company.com",
        source_type="OFFICIAL_CAREERS",
        evidence_text="Talent Acquisition Jane Doe +919876543210",
        evidence_location="page",
        retrieved_at="2026-10-05",
        recruitment_relevance_confidence=ConfidenceLevel.HIGH,
        company_match_confidence=ConfidenceLevel.HIGH
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.VERIFIED
    assert v.contact_side == ContactSide.COMPANY
    assert v.contact_role == ContactRole.TALENT_ACQUISITION

def test_b_campus_recruiter():
    c = NormalizedContact(
        contact_id="1",
        company_canonical_id="c1",
        company_name="A",
        contact_role=ContactRole.CAMPUS_RECRUITMENT,
        contact_side=ContactSide.COMPANY,
        phone_raw="+919876543210",
        source_url="http://company.com",
        source_type="OFFICIAL_CAREERS",
        evidence_text="Campus Recruitment",
        evidence_location="page",
        retrieved_at="2026-10-05",
        recruitment_relevance_confidence=ConfidenceLevel.HIGH,
        company_match_confidence=ConfidenceLevel.HIGH
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.VERIFIED
    assert v.contact_role == ContactRole.CAMPUS_RECRUITMENT

def test_c_company_switchboard():
    c = NormalizedContact(
        contact_id="1",
        company_canonical_id="c1",
        company_name="A",
        contact_role=ContactRole.COMPANY_SWITCHBOARD,
        contact_side=ContactSide.COMPANY,
        phone_raw="+919876543210",
        source_url="http://company.com",
        source_type="OFFICIAL_CAREERS",
        evidence_text="Contact Us",
        evidence_location="page",
        retrieved_at="2026-10-05",
        recruitment_relevance_confidence=ConfidenceLevel.LOW,
        company_match_confidence=ConfidenceLevel.HIGH
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.VERIFIED
    assert v.contact_role == ContactRole.COMPANY_SWITCHBOARD

def test_d_college_placement_phone():
    c = NormalizedContact(
        contact_id="1",
        company_canonical_id="c1",
        company_name="A",
        contact_role=ContactRole.COLLEGE_CONTACT,
        contact_side=ContactSide.COLLEGE,
        phone_raw="+919876543210",
        source_url="http://college.com",
        source_type="COLLEGE_NOTICE",
        evidence_text="Training & Placement Officer",
        evidence_location="page",
        retrieved_at="2026-10-05",
        recruitment_relevance_confidence=ConfidenceLevel.HIGH,
        company_match_confidence=ConfidenceLevel.LOW
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.REJECTED_COLLEGE_SIDE

def test_e_customer_support():
    c = NormalizedContact(
        contact_id="1",
        company_canonical_id="c1",
        company_name="A",
        contact_role=ContactRole.CUSTOMER_SUPPORT,
        contact_side=ContactSide.COMPANY,
        phone_raw="+919876543210",
        source_url="http://company.com",
        source_type="OFFICIAL_SITE",
        evidence_text="Customer Support",
        evidence_location="page",
        retrieved_at="2026-10-05",
        recruitment_relevance_confidence=ConfidenceLevel.LOW,
        company_match_confidence=ConfidenceLevel.HIGH
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.REJECTED_SUPPORT_OR_SALES

def test_f_sales_number():
    c = NormalizedContact(
        contact_id="1",
        company_canonical_id="c1",
        company_name="A",
        contact_role=ContactRole.SALES,
        contact_side=ContactSide.COMPANY,
        phone_raw="+919876543210",
        source_url="http://company.com",
        source_type="OFFICIAL_SITE",
        evidence_text="Sales",
        evidence_location="page",
        retrieved_at="2026-10-05",
        recruitment_relevance_confidence=ConfidenceLevel.LOW,
        company_match_confidence=ConfidenceLevel.HIGH
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.REJECTED_SUPPORT_OR_SALES

def test_g_random_number_not_phone():
    assert is_likely_phone("10") == False
    assert is_likely_phone("20261005") == True # Technically 8 digits, but verification handles context
    
    c = NormalizedContact(
        contact_id="1",
        company_canonical_id="c1",
        company_name="A",
        contact_role=ContactRole.TALENT_ACQUISITION,
        contact_side=ContactSide.COMPANY,
        phone_raw="10",
        source_url="http://company.com",
        source_type="OFFICIAL_SITE",
        evidence_text="CTC 10 LPA",
        evidence_location="page",
        retrieved_at="2026-10-05",
        recruitment_relevance_confidence=ConfidenceLevel.HIGH,
        company_match_confidence=ConfidenceLevel.HIGH
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.REJECTED_NOT_PHONE

def test_h_same_recruiter_two_sources_merges():
    from src.verification.contact_verifier import merge_contacts
    c1 = NormalizedContact(contact_id="1", company_canonical_id="c1", company_name="A", contact_role=ContactRole.RECRUITER, phone_raw="9876543210", source_url="url1", source_type="A", evidence_text="e", evidence_location="e", retrieved_at="d")
    c2 = NormalizedContact(contact_id="2", company_canonical_id="c1", company_name="A", contact_role=ContactRole.RECRUITER, phone_raw="9876543210", source_url="url2", source_type="B", evidence_text="e", evidence_location="e", retrieved_at="d")
    merged = merge_contacts([c1, c2])
    assert len(merged) == 1

def test_i_same_company_different_recruiter_phones():
    from src.verification.contact_verifier import merge_contacts
    c1 = NormalizedContact(contact_id="1", company_canonical_id="c1", company_name="A", contact_role=ContactRole.RECRUITER, phone_raw="9876543210", source_url="url1", source_type="A", evidence_text="e", evidence_location="e", retrieved_at="d")
    c2 = NormalizedContact(contact_id="2", company_canonical_id="c1", company_name="A", contact_role=ContactRole.RECRUITER, phone_raw="1234567890", source_url="url2", source_type="B", evidence_text="e", evidence_location="e", retrieved_at="d")
    merged = merge_contacts([c1, c2])
    assert len(merged) == 2

def test_j_company_identity_conflict():
    # If company match confidence is low, it enters unverified/rejected wrong company
    c = NormalizedContact(
        contact_id="1", company_canonical_id="c1", company_name="A", contact_role=ContactRole.RECRUITER,
        contact_side=ContactSide.COMPANY, phone_raw="9876543210", source_url="url", source_type="A",
        evidence_text="e", evidence_location="e", retrieved_at="d",
        company_match_confidence=ConfidenceLevel.LOW, recruitment_relevance_confidence=ConfidenceLevel.HIGH
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.REJECTED_WRONG_COMPANY

def test_k_no_phone_event_independence():
    # An event with no phone should not modify the event validity. We mock the pipeline behavior here.
    # The requirement is that we return a specific NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE indicator.
    # We can model this by returning a dummy contact or processing result.
    c = NormalizedContact(
        contact_id="1", company_canonical_id="c1", company_name="A", contact_role=ContactRole.UNKNOWN,
        contact_side=ContactSide.UNKNOWN, phone_raw=None, source_url="url", source_type="A",
        evidence_text="No contacts found", evidence_location="e", retrieved_at="d"
    )
    v = verify_contact(c)
    assert v.verification_state == PhoneVerificationState.REJECTED_NOT_PHONE
    
    # In the actual pipeline run, if a company has no verified phones, we generate a special output.
def test_l_query_generation():
    from src.extraction.contact_extractor import generate_queries
    queries = generate_queries("TestCompany")
    assert len(queries) == 2
    assert "TestCompany" in queries[0]


def test_l2_query_generation_removes_legal_suffix():
    from src.extraction.contact_extractor import generate_queries
    queries = generate_queries("Transenergy Pvt. Ltd.")
    assert len(queries) == 2
    assert '"Transenergy"' in queries[0]
    assert "Pvt." not in queries[0]

def test_m_extract_phones():
    from src.extraction.contact_extractor import extract_phones_from_text
    # Should catch typical 10-digit formats with prefixes
    text = "Call us at +91-9876543210 or +91 9999988888. Our CTC is 10 LPA."
    phones = extract_phones_from_text(text)
    assert len(phones) == 2
    assert "+91-9876543210" in phones
    assert "+91 9999988888" in phones

def test_n_role_mapping():
    from src.extraction.contact_extractor import map_role_from_text
    assert map_role_from_text("university recruitment team") == ContactRole.CAMPUS_RECRUITMENT
    assert map_role_from_text("T&P cell") == ContactRole.COLLEGE_CONTACT
    assert map_role_from_text("sales department") == ContactRole.SALES
    assert map_role_from_text("random text") == ContactRole.UNKNOWN

def test_o_bounded_discovery_engine_initial_telemetry():
    from src.extraction.contact_extractor import BoundedDiscoveryEngine
    engine = BoundedDiscoveryEngine()
    assert engine.telemetry["urls_attempted"] == 0
    assert engine.telemetry["queries_generated"] == 0
    assert len(engine.per_company_telemetry) == 0
    assert len(engine.source_level_lineage) == 0

def test_p_genuine_zero_result():
    from src.extraction.contact_extractor import BoundedDiscoveryEngine
    from unittest.mock import patch
    engine = BoundedDiscoveryEngine()

    with patch("src.extraction.contact_extractor.DDGS") as mock_ddgs:
        # Mock DDGS to return an empty list for both bounded queries.
        mock_ddgs.return_value.__enter__.return_value.text.return_value = []
        candidates = engine.attempt_live_discovery("TestCorp", "test_id")

        assert len(candidates) == 0
        assert engine.per_company_telemetry["TestCorp"]["stop_reason"] == "NO_SEARCH_RESULTS"
        assert engine.per_company_telemetry["TestCorp"]["urls_discovered"] == 0
        assert engine.telemetry["stop_reason"] == "NO_SEARCH_RESULTS"
        assert engine.telemetry["search_results_returned"] == 0

def test_p2_explicit_bing_backend_filters_unrelated_results():
    from src.extraction.contact_extractor import BoundedDiscoveryEngine
    from unittest.mock import patch

    engine = BoundedDiscoveryEngine()
    unrelated = [{
        "href": "https://www.youtube.com/",
        "title": "YouTube",
        "body": "YouTube videos and channels",
    }]

    with patch("src.extraction.contact_extractor.DDGS") as mock_ddgs, \
         patch("httpx.Client.get") as mock_get:
        mock_ddgs.return_value.__enter__.return_value.text.return_value = unrelated
        candidates = engine.attempt_live_discovery("Transenergy Pvt. Ltd.", "evt-1")

    assert candidates == []
    assert mock_ddgs.return_value.__enter__.return_value.text.call_count == 2
    assert all(
        call.kwargs.get("backend") == "bing"
        for call in mock_ddgs.return_value.__enter__.return_value.text.call_args_list
    )
    assert mock_get.call_count == 0
    assert engine.per_company_telemetry["Transenergy Pvt. Ltd."]["urls_discovered"] == 0
    assert engine.per_company_telemetry["Transenergy Pvt. Ltd."]["stop_reason"] == "NO_RELEVANT_RESULTS"
    assert engine.telemetry["irrelevant_results_filtered"] == 2



def test_p3_single_token_company_name_rejects_similarly_named_brand():
    from src.extraction.contact_extractor import (
        BoundedDiscoveryEngine,
        _search_result_matches_company,
    )
    from unittest.mock import patch

    target_company = "Transenergy Pvt. Ltd."
    unrelated = {
        "href": "https://transenergy-global.com/",
        "title": "TransEnergy Global - Purpose Fuels Change",
        "body": "Accelerating the transition to clean energy.",
    }
    official = {
        "href": "https://transenergypvtltd.in/contact/",
        "title": "Contact - transenergypvtltd.in",
        "body": "Transenergy Private Limited, Chennai.",
    }

    assert not _search_result_matches_company(target_company, unrelated)
    assert _search_result_matches_company(target_company, official)

    engine = BoundedDiscoveryEngine()
    with patch("src.extraction.contact_extractor.DDGS") as mock_ddgs:
        with patch("httpx.Client.get") as mock_get:
            mock_ddgs.return_value.__enter__.return_value.text.return_value = [unrelated]
            candidates = engine.attempt_live_discovery(target_company, "evt-1")

    assert candidates == []
    assert mock_get.call_count == 0
    assert engine.per_company_telemetry[target_company]["urls_discovered"] == 0
    assert engine.per_company_telemetry[target_company]["stop_reason"] == "NO_RELEVANT_RESULTS"



def test_q_api_rate_limit():
    from src.extraction.contact_extractor import BoundedDiscoveryEngine
    from unittest.mock import patch
    engine = BoundedDiscoveryEngine()
    
    with patch("src.extraction.contact_extractor.DDGS") as mock_ddgs:
        # Raise an exception when calling text()
        mock_ddgs.return_value.__enter__.return_value.text.side_effect = Exception("RateLimitError")
        candidates = engine.attempt_live_discovery("RateLimitedCorp", "test_id")
        
        assert len(candidates) == 0
        assert engine.per_company_telemetry["RateLimitedCorp"]["stop_reason"] == "API_RATE_LIMIT"
        assert engine.telemetry["exceptions"] > 0

def test_r_network_failure():
    from src.extraction.contact_extractor import BoundedDiscoveryEngine
    from unittest.mock import patch
    engine = BoundedDiscoveryEngine()

    with patch("src.extraction.contact_extractor.DDGS") as mock_ddgs, \
         patch("httpx.Client.get") as mock_get:

        mock_ddgs.return_value.__enter__.return_value.text.return_value = [
            {
                "href": "http://test.com/1",
                "title": "NetFailCorp recruitment contact",
                "body": "NetFailCorp recruitment contact",
            }
        ]
        
        mock_get.side_effect = Exception("Connection Timeout")
        
        candidates = engine.attempt_live_discovery("NetFailCorp", "test_id")
        
        assert len(candidates) == 0
        assert engine.per_company_telemetry["NetFailCorp"]["stop_reason"] == "NETWORK_FAILURE"
        assert engine.per_company_telemetry["NetFailCorp"]["failed_fetches"] > 0

def test_s_successful_fetch_rejected_candidate():
    from src.extraction.contact_extractor import BoundedDiscoveryEngine
    from src.verification.contact_verifier import verify_contact
    from src.models.contact import PhoneVerificationState
    from unittest.mock import patch, MagicMock
    
    engine = BoundedDiscoveryEngine()
    
    with patch("src.extraction.contact_extractor.DDGS") as mock_ddgs, \
         patch("httpx.Client.get") as mock_get:
        
        mock_ddgs.return_value.__enter__.return_value.text.return_value = [
            {
                "href": "http://test.com/support",
                "title": "TestCorp Support",
                "body": "Customer Support",
            }
        ]
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><title>TestCorp Support</title><body>Call our sales team at +91 9999988888</body></html>"
        mock_get.return_value = mock_resp
        
        candidates = engine.attempt_live_discovery("TestCorp", "test_id")
        
        assert len(candidates) == 1
        assert engine.per_company_telemetry["TestCorp"]["stop_reason"] == "COMPLETED"
        assert engine.per_company_telemetry["TestCorp"]["phone_candidates_found"] == 1
        
        verified = verify_contact(candidates[0])
        assert verified.verification_state == PhoneVerificationState.REJECTED_SUPPORT_OR_SALES


def test_t_company_identity_required():
    from src.models.contact import PhoneVerificationState
    assert hasattr(PhoneVerificationState, 'COMPANY_IDENTITY_REQUIRED')


def test_u_production_routing_logic():
    import run_batch_7
    from src.models.contact import PhoneVerificationState
    ev = {"event_id": "anon_1", "company_name": None}
    status, reason = run_batch_7.determine_terminal_state(ev, set(), {})
    assert status == PhoneVerificationState.COMPANY_IDENTITY_REQUIRED.value
    assert status != PhoneVerificationState.NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE.value
    assert "identity missing" in reason.lower()


def test_v_empty_company_search_is_marked_incomplete():
    import run_batch_7
    from src.models.contact import PhoneVerificationState

    ev = {"event_id": "evt_1", "company_name": "Transenergy Pvt. Ltd."}
    status, reason = run_batch_7.determine_terminal_state(
        ev, set(), {"Transenergy Pvt. Ltd.": "NO_SEARCH_RESULTS"}
    )

    assert status == PhoneVerificationState.CONTACT_DISCOVERY_INCOMPLETE.value
    assert "NO_SEARCH_RESULTS" in reason
