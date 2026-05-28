import frappe
from frappe.model.document import Document
from frappe.utils import flt
import requests
import json
import base64
import jwt
import time
from frappe import _

class CommercialOffer(Document):
    def validate(self):
        self.calculate_totals()
        self.apply_pricing_rules()

    def calculate_totals(self):
        total = 0.0
        if not self.get("items"):
            self.total_amount = 0.0
            return
        for item in self.items:
            qty = flt(item.qty) if item.qty else 0.0
            rate = flt(item.rate) if item.rate else 0.0
            item.amount = qty * rate
            total += item.amount
        self.total_amount = total

    def apply_pricing_rules(self):
        if not self.vertical or flt(self.total_amount) <= 0:
            return
        discount = frappe.db.get_value(
            "Pricing Rule Logic", 
            {"vertical": self.vertical}, 
            "discount_percentage", 
            cache=True
        )
        if discount:
            discount_amount = flt(self.total_amount) * (flt(discount) / 100.0)
            self.total_amount = flt(self.total_amount) - discount_amount

    @frappe.whitelist()
    def get_module_data(self, finhub_module):
        if not finhub_module:
            return {"base_price": 0.0}
        data = frappe.db.get_value("Finhub Module", finhub_module, ["base_price"], as_dict=True)
        return data if data else {"base_price": 0.0}

    @frappe.whitelist()
    def calculate_client_side_totals(self):
        self.calculate_totals()
        self.apply_pricing_rules()
        return self.total_amount

    @frappe.whitelist()
    def send_to_docusign(self):
        frappe.log_error(f"send_to_docusign called for {self.name}", "DocuSign Debug")
        return send_offer_for_signature(self.name)


# ========== DOCUSIGN INTEGRATION FUNCTIONS ==========
import frappe
import requests
import json
import base64
import jwt
import time
from frappe import _
import frappe
import requests
import json
import base64
import jwt
import time
from frappe import _

@frappe.whitelist(allow_guest=True)
def docusign_webhook():
    """Receive webhook from DocuSign and update offer status"""
    try:
        data = frappe.request.data
        if not data:
            return "OK"
        
        # Parse the payload
        data_str = data.decode('utf-8')
        payload = json.loads(data_str)
        
        # Get the event type and envelope data
        event = payload.get("event")
        envelope_data = payload.get("data", {})
        
        # Extract envelope ID
        envelope_id = envelope_data.get("envelopeId")
        
        # Extract status from different possible locations
        status = None
        if "status" in envelope_data:
            status = envelope_data.get("status")
        elif "envelopeSummary" in envelope_data:
            status = envelope_data.get("envelopeSummary", {}).get("status")
        
        # Log ONLY the essential info (fits in 140 chars)
        frappe.log_error(f"Webhook - Event: {event}, Envelope: {envelope_id}, Status: {status}", "DocuSign Webhook")
        
        # Update status when envelope is completed/signed
        if (status == "completed" or event == "envelope-completed" or event == "recipient-signed") and envelope_id:
            offer_name = frappe.db.get_value("Commercial Offer", 
                                              {"docusign_envelope_id": envelope_id}, "name")
            if offer_name:
                frappe.db.set_value("Commercial Offer", offer_name, "status", "Signed")
                frappe.db.commit()
                frappe.log_error(f"✅ Offer {offer_name} updated to Signed", "DocuSign Success")
            else:
                frappe.log_error(f"⚠️ No offer found for envelope: {envelope_id}", "DocuSign Warning")
        
    except Exception as e:
        frappe.log_error(f"Webhook error: {str(e)[:100]}", "DocuSign Webhook Error")
    
    return "OK"

@frappe.whitelist(allow_guest=True)
def docusign_callback():
    """OAuth callback endpoint"""
    return "Callback received"

def get_docusign_token():
    """Obtain access token using JWT grant"""
    config = frappe.conf.get("docusign", {})
    integration_key = config.get("integration_key")
    user_id = config.get("user_id")
    private_key_path = config.get("private_key_path")
    
    if not integration_key or not user_id or not private_key_path:
        frappe.throw("DocuSign credentials missing in site_config.json")
    
    with open(private_key_path, "r") as f:
        private_key = f.read()
    
    now = int(time.time())
    assertion = {
        "iss": integration_key,
        "sub": user_id,
        "aud": "account-d.docusign.com",
        "iat": now,
        "exp": now + 3600,
        "scope": "signature impersonation"
    }
    jwt_token = jwt.encode(assertion, private_key, algorithm="RS256")
    
    response = requests.post(
        "https://account-d.docusign.com/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt_token
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        frappe.log_error(response.text[:100], "DocuSign Token Error")
        frappe.throw(f"DocuSign token error: {response.text[:200]}")
    
    return response.json()["access_token"]

@frappe.whitelist()
def send_offer_for_signature(docname):
    """Send Commercial Offer to DocuSign as an envelope"""
    frappe.log_error(f"send_offer_for_signature started for {docname}", "DocuSign Debug")
    
    try:
        offer = frappe.get_doc("Commercial Offer", docname)
        
        # Allow both 'Approval' and 'Sent' status
        if offer.status not in ["Approval", "Sent"]:
            return {"status": "error", "message": f"Status must be 'Approval' or 'Sent', not '{offer.status}'"}
        
        # Get customer email – fallback to test email if missing
        customer_email = frappe.db.get_value("Customer", offer.customer, "email_id")
        if not customer_email:
            customer_email = "test@example.com"
            frappe.log_error(f"Customer {offer.customer} has no email. Using default: {customer_email}", "DocuSign Warning")
        
        # Minimal test PDF (bypasses wkhtmltopdf issues)
        pdf_base64 = "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL01lZGlhQm94WzAgMCA2MTIgNzkyXS9SZXNvdXJjZXM8PD4+L0NvbnRlbnRzIDQgMCBSPj4KZW5kb2JqCjQgMCBvYmoKPDwvTGVuZ3RoIDc+PgpzdHJlYW0KQlQKL0YxIDI0IFRECjAgMApUZAoKRVQKZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgNQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDA3NyAwMDAwMCBuIAowMDAwMDAwMTI4IDAwMDAwIG4gCjAwMDAwMDAyMzMgMDAwMDAgbiAKdHJhaWxlcgo8PC9TaXplIDUvUm9vdCAxIDAgUj4+CnN0YXJ0eHJlZgoyODAKJSVFT0Y="
        
        envelope_data = {
            "emailSubject": f"Please sign {offer.name} - Commercial Offer",
            "documents": [{
                "documentBase64": pdf_base64,
                "name": f"{offer.name}.pdf",
                "documentId": "1"
            }],
            "recipients": {
                "signers": [{
                    "email": customer_email,
                    "name": offer.customer,
                    "recipientId": "1",
                    "routingOrder": "1",
                    "tabs": {
                        "signHereTabs": [{
                            "documentId": "1",
                            "pageNumber": "1",
                            "xPosition": "200",
                            "yPosition": "400"
                        }]
                    }
                }]
            },
            "status": "sent"
        }
        
        access_token = get_docusign_token()
        config = frappe.conf.get("docusign", {})
        account_id = config.get("account_id")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"https://demo.docusign.net/restapi/v2.1/accounts/{account_id}/envelopes",
            headers=headers,
            json=envelope_data
        )
        
        if response.status_code == 201:
            envelope_id = response.json()["envelopeId"]
            frappe.db.set_value("Commercial Offer", docname, "docusign_envelope_id", envelope_id)
            frappe.db.set_value("Commercial Offer", docname, "status", "Sent")
            frappe.db.commit()
            frappe.log_error(f"Envelope created: {envelope_id}", "DocuSign Success")
            return {"status": "success", "envelope_id": envelope_id}
        else:
            error_msg = response.text[:200]
            frappe.log_error(error_msg, "DocuSign Envelope Error")
            return {"status": "error", "message": error_msg}
            
    except Exception as e:
        frappe.log_error(str(e)[:200], "DocuSign Send Error")
        return {"status": "error", "message": str(e)[:200]}