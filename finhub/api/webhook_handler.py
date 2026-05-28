
import frappe
import json

@frappe.whitelist(allow_guest=True)
def tenant_registration_webhook():
    """Handle tenant registration webhook"""
    try:
        data = frappe.local.form_dict
        
        lead_data = {
            "lead_name": data.get("tenant_name") or data.get("name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "source": "Webhook",
            "event_type": "Sandbox Signup" if data.get("signup_type") == "sandbox" else "Test Signup",
            "region": data.get("region"),
            "vertical": data.get("vertical"),
            "metadata": data
        }
        
        from finhub.api.lead_api import create_lead_from_event
        return create_lead_from_event(lead_data)
    except Exception as e:
        return {"success": False, "error": str(e)}
