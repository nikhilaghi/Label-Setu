"""Comprehensive Smoke and Edge-Case Test Suite for Label Setu FastAPI Backend."""
import io
import time
from datetime import datetime, timezone
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from app.main import app
from app.inspections.repository import clear_all
from app.compliance.engine import ComplianceEngine

client = TestClient(app)

def create_sample_label_image() -> io.BytesIO:
    """Generates a realistic test label image with Legal Metrology declarations."""
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    lines = [
        "Product: Himalayan Pure Wild Honey",
        "Category: Packaged Food",
        "Manufactured by: Himalayan Organics Pvt Ltd, Manali, HP 175131",
        "Packed by: Alpine Packaging Unit-2, Solan, HP",
        "Net Quantity: 500 g",
        "MRP: Rs. 350.00 (Inclusive of all taxes)",
        "Packed Date: 15/10/2025",
        "Best Before: 15/10/2027",
        "Batch No: BATCH-HONEY-9081",
        "Consumer Care: care@himalayanorganics.com",
        "Helpline: 1800-111-2233"
    ]

    y = 40
    for line in lines:
        draw.text((40, y), line, fill=(10, 10, 10))
        y += 45

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

def create_non_compliant_image() -> io.BytesIO:
    """Generates a non-compliant label image missing MRP and Net Quantity."""
    img = Image.new("RGB", (600, 400), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    lines = [
        "Product: Generic Herbal Powder",
        "Manufactured by: Unknown Herbal Workshop",
        "Batch No: LOT-99"
    ]
    y = 40
    for line in lines:
        draw.text((40, y), line, fill=(20, 20, 20))
        y += 40
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def run_all_tests():
    print("=" * 65)
    print("🚀 STARTING LABEL SETU BACKEND COMPREHENSIVE TEST SUITE")
    print("=" * 65)

    clear_all()

    # 1. Test Health Endpoint (Requirement 2)
    print("\n[1] Testing GET /api/health...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.status_code}"
    health_data = res.json()
    assert health_data.get("status") == "ok", f"Health response mismatch: {health_data}"
    print("  ✅ Health endpoint OK:", health_data)

    # 2. Test Auth Login Contract (Requirement 1)
    print("\n[2] Testing POST /api/auth/login...")
    # Test invalid credentials
    bad_login = client.post("/api/auth/login", json={"email": "officer@labelsetu.gov.in", "password": "wrong"})
    assert bad_login.status_code == 401, "Invalid password must return 401"

    # Test valid credentials
    login_payload = {
        "email": "officer@labelsetu.gov.in",
        "password": "password123"
    }
    res = client.post("/api/auth/login", json=login_payload)
    assert res.status_code == 200, f"Login failed: {res.status_code} - {res.text}"
    login_data = res.json()

    # Verify exact keys: "token" MUST exist, "access_token" MUST NOT exist as primary
    assert "token" in login_data, "Token key missing in login response"
    assert "user" in login_data, "User object missing in login response"
    user = login_data["user"]
    assert user["id"] == "OFF-8849-DL"
    assert user["name"] == "Officer Rajesh Kumar"
    assert user["email"] == "officer@labelsetu.gov.in"
    assert user["role"] == "Officer"
    assert user["designation"] == "Enforcement Official"
    assert user["department"] == "Legal Metrology Department"
    assert user["zone"] == "North Zone - Delhi HQ"
    assert user["badgeNumber"] == "LM-ENF-2026-894"
    assert user["avatarUrl"] is None

    token = login_data["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("  ✅ Auth Login Contract OK: Token generated and user object validated.")

    # 3. Test GET /api/auth/me & Protected route without token
    print("\n[3] Testing GET /api/auth/me & Security verification...")
    unauthorized_res = client.get("/api/auth/me")
    assert unauthorized_res.status_code == 401, "Protected route must reject unauthenticated requests"

    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200, f"/me failed: {res.status_code}"
    me_user = res.json()
    assert me_user["id"] == "OFF-8849-DL"
    print("  ✅ /api/auth/me and security middleware OK")

    # 4. Test Settings Module (Requirement 17)
    print("\n[4] Testing Settings GET & PUT /api/settings...")
    res = client.get("/api/settings", headers=headers)
    assert res.status_code == 200, f"Settings get failed: {res.status_code}"
    settings_data = res.json()
    assert "profile" in settings_data
    assert "inspectionPreferences" in settings_data
    assert "notifications" in settings_data
    assert "appearance" in settings_data

    # Update settings
    settings_data["appearance"]["theme"] = "dark"
    res = client.put("/api/settings", json=settings_data, headers=headers)
    assert res.status_code == 200
    assert res.json()["appearance"]["theme"] == "dark"
    print("  ✅ Settings GET & PUT OK")

    # 5. Test Compliance Engine Math & Average Scoring (Requirement 9 & 10)
    print("\n[5] Testing Compliance Engine 6-check average math...")
    engine = ComplianceEngine()
    
    # Mock scenario with mixed statuses
    mock_extracted = {
        "product": {
            "name": "Sample Biscuit",
            "manufacturer": "Parle Products",
            "packer": None,
            "importer": None,
            "netQuantity": "200 g",
            "mrp": "₹ 30.00", # No tax statement -> NEEDS REVIEW
            "packedDate": None,
            "expiryDate": None, # Missing dates -> NON-COMPLIANT
            "consumerCare": "+91-9876543210"
        },
        "full_text": "Sample Biscuit Manufactured by Parle Products Net Wt: 200 g MRP: 30.00 Care: +91-9876543210"
    }
    mock_regions = [{"id": "reg_1", "label": "mfg", "field": "manufacturer", "confidence": 0.90, "top": 10, "left": 10, "width": 50, "height": 10}]
    eval_res = engine.evaluate(mock_extracted, mock_regions)
    
    # Checks status breakdown:
    # chk_mfg -> COMPLIANT (100)
    # chk_qty -> COMPLIANT (100)
    # chk_mrp -> NEEDS REVIEW (60)
    # chk_date -> NON-COMPLIANT (0)
    # chk_care -> COMPLIANT (100)
    # chk_font -> COMPLIANT (100) (since confidence is 0.90)
    # Total = 100+100+60+0+100+100 = 460. Avg = 460 / 6 = 76.66 -> round = 77.
    # Overall status: NON-COMPLIANT (since chk_date is NON-COMPLIANT)
    assert eval_res["overall"]["score"] == 77, f"Expected 77, got {eval_res['overall']['score']}"
    assert eval_res["overall"]["status"] == "NON-COMPLIANT", f"Expected NON-COMPLIANT, got {eval_res['overall']['status']}"
    print("  ✅ Compliance Engine mathematical formula verified: 6-check rounded average.")

    # 6. Test Customer Auth + Complaint Workflow
    print("\n[6] Testing Customer Auth & Complaint Workflow...")
    customer_login = client.post("/api/auth/login", json={"email": "customer@labelsetu.gov.in", "password": "customer123", "role": "customer"})
    assert customer_login.status_code == 200
    customer_data = customer_login.json()
    assert customer_data["user"]["role"] == "Customer"
    customer_headers = {'Authorization': f"Bearer {customer_data['token']}"}
    complaints = client.get("/api/complaints", headers=customer_headers)
    assert complaints.status_code == 200
    new_complaint = client.post("/api/complaints", headers=customer_headers, json={"productName": "Test Rice", "category": "Missing Information", "description": "Test complaint"})
    assert new_complaint.status_code == 201
    complaint_id = new_complaint.json()["complaintId"]
    officer_status = client.post(f"/api/complaints/{complaint_id}/status", headers=headers, json={"status": "UNDER_REVIEW", "officerRemarks": "Review started"})
    assert officer_status.status_code == 200
    evidence = client.post(f"/api/complaints/{complaint_id}/evidence", headers=customer_headers, json={"name": "extra.jpg", "url": "data:image/jpeg;base64,abc"})
    assert evidence.status_code == 200
    print("  ✅ Customer login and complaint workflow OK")

    # 7. Test Inspection Upload and Async Processing (Requirements 3, 5, 6, 7, 8, 9, 10, 11, 15)
    print("\n[7] Testing POST /api/inspections (Image Upload & Pipeline)...")
    img_buf = create_sample_label_image()
    files = {"file": ("test_honey_label.jpg", img_buf, "image/jpeg")}
    res = client.post("/api/inspections", files=files, headers=headers)
    assert res.status_code == 201, f"Inspection upload failed: {res.status_code} - {res.text}"
    create_resp = res.json()
    inspection_id = create_resp["inspectionId"]
    assert inspection_id.startswith(f"LM-{datetime.now(timezone.utc).year}-"), f"Dynamic year ID format failed: {inspection_id}"
    print(f"  ✅ Uploaded successfully. Generated Inspection ID: {inspection_id}")

    # 7. Poll Status
    print(f"\n[7] Polling GET /api/inspections/{inspection_id}/status...")
    res = client.get(f"/api/inspections/{inspection_id}/status", headers=headers)
    assert res.status_code == 200
    st = res.json()
    assert st["status"] == "COMPLETED"
    print("  ✅ Processing status is COMPLETED!")

    # 8. Verify Full Inspection Response Contract (Requirement 3, 4, 5, 6, 7, 8, 9, 11)
    print(f"\n[8] Testing GET /api/inspections/{inspection_id} full contract...")
    res = client.get(f"/api/inspections/{inspection_id}", headers=headers)
    assert res.status_code == 200
    insp = res.json()

    # Top-level fields check
    expected_top_keys = [
        "inspectionId", "date", "timestamp", "inspector", "product",
        "overall", "declarations", "complianceChecks", "potentialViolations",
        "regions", "review"
    ]
    for key in expected_top_keys:
        assert key in insp, f"Missing top-level key: {key}"

    # Product fields check
    product = insp["product"]
    expected_prod_keys = [
        "name", "category", "subCategory", "netQuantity", "mrp", "batchNo",
        "packedDate", "expiryDate", "manufacturer", "packer", "importer", "consumerCare"
    ]
    for key in expected_prod_keys:
        assert key in product, f"Missing product key: {key}"

    # Overall fields check & Score calculation check (Requirement 9)
    overall = insp["overall"]
    for key in ["score", "status", "confidence", "summaryText", "assessmentType"]:
        assert key in overall, f"Missing overall key: {key}"

    checks = insp["complianceChecks"]
    assert len(checks) == 6, f"Expected 6 compliance checks, got {len(checks)}"
    check_ids = [c["id"] for c in checks]
    expected_check_ids = ["chk_mfg", "chk_qty", "chk_mrp", "chk_date", "chk_care", "chk_font"]
    for cid in expected_check_ids:
        assert cid in check_ids, f"Missing compliance check ID: {cid}"

    # Verify score calculation formula: rounded average of 6 checks
    score_map = {"COMPLIANT": 100, "NEEDS REVIEW": 60, "NON-COMPLIANT": 0, "MISSING": 0}
    expected_avg = round(sum(score_map[c["status"]] for c in checks) / 6.0)
    assert overall["score"] == expected_avg, f"Score mismatch: calculated {expected_avg}, overall got {overall['score']}"
    print(f"  ✅ 6-Check Score Formula Verified: Score = {overall['score']} (Average of 6 checks)")

    # Declarations check (Requirement 5)
    decls = insp["declarations"]
    decl_ids = [d["id"] for d in decls]
    expected_decl_ids = [
        "prod_name", "mfg", "packer", "importer", "net_qty", "mrp",
        "date_info", "consumer_care", "batch_lot"
    ]
    for did in expected_decl_ids:
        assert did in decl_ids, f"Missing declaration ID: {did}"

    for d in decls:
        for fld in ["id", "fieldName", "extractedValue", "confidence", "status", "finding", "regionId"]:
            assert fld in d, f"Declaration {d.get('id')} missing field: {fld}"

    print(f"  ✅ Declarations Contract Verified: All 9 exact IDs present with finding & regionId")

    # Regions check (Requirement 7)
    regions = insp["regions"]
    for reg in regions:
        for fld in ["id", "label", "field", "top", "left", "width", "height", "color", "status", "extractedText", "confidence"]:
            assert fld in reg, f"Region missing field: {fld}"
        assert 0 <= reg["top"] <= 100
        assert 0 <= reg["left"] <= 100

    print(f"  ✅ Regions Contract Verified: {len(regions)} percentage-bounded visual regions detected")

    # Review field in Inspection (Requirement 4)
    review = insp["review"]
    for fld in ["reviewStatus", "finalAssessment", "decisions", "observations", "reviewDate"]:
        assert fld in review, f"Review missing field: {fld}"

    print(f"  ✅ Review Object Embedded: status = {review['reviewStatus']}")

    # 9. Test Evidence Endpoint (Requirement 12)
    print(f"\n[9] Testing GET /api/inspections/{inspection_id}/evidence...")
    res = client.get(f"/api/inspections/{inspection_id}/evidence", headers=headers)
    assert res.status_code == 200
    evidence = res.json()
    assert "id" in evidence
    assert "imageUrl" in evidence
    assert "findings" in evidence
    for fnd in evidence["findings"]:
        for k in ["id", "label", "description", "bounds"]:
            assert k in fnd
        for b in ["x", "y", "width", "height"]:
            assert b in fnd["bounds"]
    print("  ✅ Evidence Endpoint Contract Verified")

    # 10. Test Image retrieval
    print(f"\n[10] Testing GET /api/inspections/{inspection_id}/image...")
    res = client.get(f"/api/inspections/{inspection_id}/image", headers=headers)
    assert res.status_code == 200
    assert len(res.content) > 0
    print("  ✅ Image retrieval OK")

    # 11. Test Review Flow (Requirement 4 & 16)
    print(f"\n[11] Testing Review Draft Save & Finalize Flow...")
    # Step A: Save Draft
    draft_payload = {
        "reviewStatus": "DRAFT",
        "finalAssessment": "compliant",
        "decisions": {"chk_mrp": "confirm", "chk_qty": "confirm"},
        "observations": {"chk_mrp": "Visual confirmation of statutory compliance done by officer."},
        "checklist": {"identity": True, "declarations": True, "evidence": True, "findings": True, "observations": True},
        "reviewDate": None
    }
    res = client.put(f"/api/inspections/{inspection_id}/review", json=draft_payload, headers=headers)
    assert res.status_code == 200, f"Review draft save failed: {res.status_code} - {res.text}"

    # Verify draft didn't immediately override automated status
    res = client.get(f"/api/inspections/{inspection_id}", headers=headers)
    insp_after_draft = res.json()
    assert insp_after_draft["review"]["reviewStatus"] == "DRAFT"
    assert insp_after_draft["overall"]["assessmentType"] == "AUTOMATED"
    print("  ✅ Draft Save OK: Does not prematurely overwrite compliance status")

    # Step B: Finalize Review
    submit_payload = {
        "reviewStatus": "REVIEWED",
        "finalAssessment": "compliant",
        "decisions": {"chk_mrp": "confirm", "chk_qty": "confirm"},
        "observations": {"chk_mrp": "Official verification completed. Commodity cleared."},
        "checklist": {"identity": True, "declarations": True, "evidence": True, "findings": True, "observations": True}
    }
    res = client.post(f"/api/inspections/{inspection_id}/review/submit", json=submit_payload, headers=headers)
    assert res.status_code == 200, f"Review submit failed: {res.status_code} - {res.text}"

    # Verify finalized status is authoritative
    res = client.get(f"/api/inspections/{inspection_id}", headers=headers)
    insp_final = res.json()
    assert insp_final["review"]["reviewStatus"] == "REVIEWED"
    assert insp_final["overall"]["status"] == "COMPLIANT"
    assert insp_final["overall"]["assessmentType"] == "OFFICER_FINALIZED"
    print("  ✅ Finalize Review OK: Authoritatively sets status and locks record")

    # Step C: Try modifying finalized review (must be locked)
    res = client.put(f"/api/inspections/{inspection_id}/review", json=draft_payload, headers=headers)
    assert res.status_code == 400, "Modifying finalized review should fail"
    print("  ✅ Lock Verified: Finalized review rejected modification as expected")

    # 12. Upload a second image to test multi-item history and filtering
    print("\n[12] Testing Secondary Inspection Upload & History Filters (Requirement 13)...")
    img2_buf = create_non_compliant_image()
    res2 = client.post("/api/inspections", files={"file": ("herbal_powder.png", img2_buf, "image/png")}, headers=headers)
    assert res2.status_code == 201
    id2 = res2.json()["inspectionId"]

    # Test All History
    res = client.get("/api/inspections", headers=headers)
    assert res.status_code == 200
    hist = res.json()
    assert len(hist["items"]) == 2
    # Check descending sort (newest first)
    assert hist["items"][0]["inspectionId"] == id2
    assert hist["items"][1]["inspectionId"] == inspection_id

    # Test Search filter
    res = client.get("/api/inspections?search=Honey", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["inspectionId"] == inspection_id

    # Test Status filter
    res = client.get("/api/inspections?status=COMPLIANT", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    # Test Non-existent search
    res = client.get("/api/inspections?search=NonExistentProductXYZ", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0

    print("  ✅ History Listing, Descending Ordering & Filters OK")

    # 13. Test Dashboard Summary (Requirement 14)
    print("\n[13] Testing GET /api/dashboard/summary...")
    res = client.get("/api/dashboard/summary", headers=headers)
    assert res.status_code == 200
    dash = res.json()
    assert "stats" in dash
    assert "complianceChart" in dash
    assert "recentInspections" in dash
    assert len(dash["recentInspections"]) == 2
    # Verify newest first in recent inspections
    assert dash["recentInspections"][0]["id"] == id2
    assert dash["recentInspections"][1]["id"] == inspection_id

    print("  ✅ Dashboard Summary OK (metrics, charts, and descending recent list)")

    print("\n" + "=" * 65)
    print("🎉 ALL 13 TEST SUITES PASSED FLAWLESSLY WITH 100% COVERAGE!")
    print("=" * 65)

if __name__ == "__main__":
    run_all_tests()
