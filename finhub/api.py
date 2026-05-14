import frappe

@frappe.whitelist()
def trigger_docusign(docname):
    """Placeholder for DocuSign API Call"""
    doc = frappe.get_doc("Commercial Offer", docname)
    # Integration logic here
    doc.db_set("status", "Sent")
    return True

def map_entity_on_save(doc, method):
    """Requirement 1.8: Country -> Company/Branch Mapping"""
    if doc.customer:
        territory = frappe.db.get_value("Customer", doc.customer, "territory")
        # Logic: Set branch based on territory
        if territory == "United Kingdom":
            doc.branch = "UK Division"
        elif territory == "India":
            doc.branch = "India Division"

def auto_create_ticket(doc, method):
    """Requirement 1.11: Create Issue on Submission"""
    if doc.docstatus == 1:
        issue = frappe.get_doc({
            "doctype": "Issue",
            "subject": f"Offer {doc.name} Requires Signature",
            "customer": doc.customer,
            "description": f"Commercial Offer for {doc.vertical} has been submitted."
        }).insert(ignore_permissions=True)
