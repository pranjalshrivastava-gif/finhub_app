
import frappe

def assign_ticket(doc, method=None):
    """Auto-assign ticket"""
    if doc.assigned_to or not doc.lead_reference:
        return
    
    lead = frappe.get_doc("FinHub Lead", doc.lead_reference)
    if lead.assigned_to:
        doc.assigned_to = lead.assigned_to
        doc.save()
