import frappe
import hmac
import hashlib
import time
from frappe import _

def dynamic_security(route_name):
    """
    Enterprise-grade dynamic security middleware decorator for Frappe APIs.
    Reads rules dynamically from 'FinHub API Rule' DocType.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 1. Database Configuration Lookup
            if not frappe.db.exists("FinHub API Rule", route_name):
                frappe.throw(_("Access Denied: Unregistered integration route."), frappe.PermissionError)
            
            rule = frappe.get_doc("FinHub API Rule", route_name)
            if not rule.is_active:
                return func(*args, **kwargs)
                
            request = frappe.local.request

            # 2. IP Whitelisting Check
            if rule.ip_whitelist:
                allowed_ips = [ip.strip() for ip in rule.ip_whitelist.split(",")]
                if request.remote_addr not in allowed_ips:
                    frappe.throw(_("Access Denied: Unauthorized request origin."), frappe.PermissionError)
            
            # 3. Token Authentication
            if rule.token_required:
                provided_token = request.headers.get("X-FinHub-Token")
                system_token = frappe.conf.get("finhub_api_token")
                if not provided_token or provided_token != system_token:
                    frappe.throw(_("Invalid or missing API Token."), frappe.PermissionError)
                    
            # 4. HMAC SHA256 Signature & Replay Attack Protection
            if rule.signature_required:
                timestamp = request.headers.get("X-FinHub-Timestamp")
                provided_sig = request.headers.get("X-FinHub-Signature")
                raw_payload = request.get_data(as_text=True)
                
                # Replay mitigation: Reject requests outside a strict 5-minute window
                if not timestamp or abs(int(time.time()) - int(timestamp)) > 300:
                    frappe.throw(_("Request rejected: Timestamp skew exceeded validation window."), frappe.PermissionError)
                
                signing_secret = frappe.conf.get("finhub_signing_secret")
                if not signing_secret:
                    frappe.throw(_("Configuration Error: Missing signing secret key."), frappe.ValidationError)
                
                # Reconstruct signing block: timestamp.payload
                signed_block = f"{timestamp}.{raw_payload}".encode('utf-8')
                expected_sig = hmac.new(signing_secret.encode('utf-8'), signed_block, hashlib.sha256).hexdigest()
                
                # Constant-time comparison to eliminate timing vulnerability side-channels
                if not hmac.compare_digest(expected_sig, provided_sig or ""):
                    frappe.throw(_("Access Denied: Security signature verification failed."), frappe.PermissionError)
            
            # 5. Redis-backed Sliding Window Rate Limiting
            if rule.rate_limit_count:
                cache_key = f"rate_limit:{route_name}:{request.remote_addr}"
                current_hits = frappe.cache().get_value(cache_key) or 0
                
                if int(current_hits) >= rule.rate_limit_count:
                    frappe.respond_as_web_notes(status=429)
                    frappe.throw(_("Rate limit exceeded. Request throttled."), frappe.RateLimitExceededError)
                
                # Set TTL window in seconds based on DocType selection
                window_ttl = 60 if rule.rate_limit_window == "Minute" else (3600 if rule.rate_limit_window == "Hour" else 86400)
                frappe.cache().set_value(cache_key, int(current_hits) + 1, expires_in_sec=window_ttl)

            return func(*args, **kwargs)
        return wrapper
    return decorator