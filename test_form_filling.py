"""
Pytest Suite: Form Filling & Browser Automation
Verifies Groq field mapping, Playwright MCP tool execution, and browser value verification.
"""

import asyncio
from backend.groq_service import GroqService
from backend.controller import AutomationController

def test_groq_field_mapping():
    """Test that Groq maps structured user data to live accessibility snapshot elements."""
    service = GroqService()
    
    mock_snapshot = """
- generic [ref=e49]:
  - generic [ref=e50]:
    - generic [ref=e52]:
      - text: 1. Aadhaar Number
      - textbox "Your Aadhaar No" [ref=e53]
    - generic [ref=e55]:
      - text: 2. Name of Entrepreneur
      - textbox "Name as per Aadhaar" [ref=e56]
  - generic [ref=e65]:
    - checkbox [ref=e66]
    - text: I, the holder of the above Aadhaar, hereby give my consent...
    """

    user_data = {
        "aadhaar_number": "123456789012",
        "entrepreneur_name": "Rohan Kumar Sharma"
    }

    result = service.map_data_to_form_fields(
        snapshot_text=mock_snapshot,
        collected_answers=user_data,
        current_url="https://udyamregistration.gov.in/UdyamRegistration.aspx"
    )

    mappings = result.get("mappings", [])
    assert len(mappings) >= 2, f"Expected at least 2 mappings, got {len(mappings)}"
    
    mapped_keys = {m["field_key"]: m["element_ref"] for m in mappings}
    assert "aadhaar_number" in mapped_keys
    assert mapped_keys["aadhaar_number"] == "e53"
    assert "entrepreneur_name" in mapped_keys
    assert mapped_keys["entrepreneur_name"] == "e56"

def test_playwright_mcp_form_fill():
    """Test full execution: start MCP, navigate to Udyam, fill fields, verify post-snapshot."""
    async def _run():
        controller = AutomationController(session_id="pytest_session")
        controller.collected_answers = {
            "aadhaar_number": "123456789012",
            "entrepreneur_name": "Rohan Kumar Sharma"
        }

        connected = await controller.mcp_client.start()
        assert connected, "Failed to start Playwright MCP"

        try:
            await controller.mcp_client.navigate("https://udyamregistration.gov.in/UdyamRegistration.aspx")
            await asyncio.sleep(2.0)

            # Trigger dynamic form filling
            await controller.fill_form_on_portal()

            # Capture post-snapshot
            snap = await controller.mcp_client.snapshot()
            text = snap.get("snapshot_text", "")

            assert "123456789012" in text, "Aadhaar number was not populated into portal textbox!"
            assert "Rohan" in text, "Entrepreneur name was not populated into portal textbox!"
        finally:
            await controller.mcp_client.stop()

    asyncio.run(_run())
