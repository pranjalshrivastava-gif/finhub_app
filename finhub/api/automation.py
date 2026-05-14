import frappe
from frappe import _
from frappe.utils import flt

@frappe.whitelist()
def trigger_docusign(docname):
    """Requirement 1.13: DocuSign Integration Logic"""
    try:
        if not docname:
            return {"status": "failed", "reason": "Missing DocName"}
            
        offer = frappe.get_doc("Commercial Offer", docname)
        
        # Defensive check: Only send if status is not already Signed
        if offer.status == "Signed":
            frappe.throw(_("Offer is already signed."))

        # LOGIC: Integrate with DocuSign API here
        # For now, we update the status per the WBS workflow
        offer.db_set("status", "Sent")
        
        return {"status": "success"}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "DocuSign API Error")
        return {"status": "error"}

def map_entity_on_save(doc, method):
    """Requirement 1.8: Entity mapping (Country -> Company)"""
    if not doc.customer:
        return

    # Fetch customer country
    country = frappe.db.get_value("Customer", doc.customer, "country")
    
    if country:
        # Optimized lookup for mapping
        internal_company = frappe.db.get_value("Entity Mapping Logic", 
            {"country": country}, "internal_company", cache=True)
        
        if internal_company:
            doc.company = internal_company

def auto_create_ticket(doc, method):
    """Requirement 1.11: Ticketing Integration on Submit"""
    try:
        # Check if ticket already exists to prevent duplicates
        exists = frappe.db.exists("Issue", {"customer": doc.customer, "subject": f"Fulfillment: {doc.name}"})
        if exists:
            return

        new_issue = frappe.get_doc({
            "doctype": "Issue",
            "subject": f"Fulfillment: {doc.name}",
            "customer": doc.customer,
            "description": _("Automated ticket for Commercial Offer {0}").format(doc.name),
            "priority": "Medium",
            "status": "Open"
        })
        new_issue.insert(ignore_permissions=True)
        
        # Store back the reference
        doc.db_set("custom_ticket_id", new_issue.name)
        
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Ticketing Automation Error")