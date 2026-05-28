
import frappe

def assign_lead(doc, method=None):
    """Auto-assign lead based on rules"""
    if doc.assigned_to:
        return
    
    rules = frappe.get_all("Lead Assignment Rule", filters={"enabled": 1}, order_by="priority asc")
    
    for rule_data in rules:
        rule = frappe.get_doc("Lead Assignment Rule", rule_data.name)
        
        if matches_rule(doc, rule):
            assigned_user = None
            
            if rule.assignment_type == "Specific User":
                assigned_user = rule.assigned_user
            elif rule.assignment_type == "Round Robin":
                assigned_user = get_round_robin_user(rule)
            elif rule.assignment_type == "Region Manager":
                assigned_user = get_region_manager(doc.region)
            
            if assigned_user:
                doc.assigned_to = assigned_user
                doc.save()
                send_notification(doc)
                break

def matches_rule(lead, rule):
    """Check if lead matches rule criteria"""
    if rule.region and lead.region != rule.region:
        return False
    if rule.vertical and lead.vertical != rule.vertical:
        return False
    if rule.source and lead.source != rule.source:
        return False
    if rule.priority_level and lead.priority != rule.priority_level:
        return False
    return True

def get_round_robin_user(rule):
    """Get next user in round-robin"""
    if not rule.assignment_users:
        return None
    
    users = [u.user for u in rule.assignment_users]
    if not users:
        return None
    
    last_assigned = frappe.db.get_value("FinHub Lead",
        filters={"assigned_to": ["in", users]},
        fieldname="assigned_to",
        order_by="creation desc"
    )
    
    if not last_assigned:
        return users[0]
    
    try:
        idx = users.index(last_assigned)
        next_idx = (idx + 1) % len(users)
        return users[next_idx]
    except ValueError:
        return users[0]

def get_region_manager(region):
    """Get user for region"""
    if not region:
        return None
    
    territory = frappe.db.get_value("Territory", region, "territory_manager")
    return territory

def send_notification(lead):
    """Send assignment notification"""
    if lead.assigned_to:
        user_email = frappe.db.get_value("User", lead.assigned_to, "email")
        if user_email:
            frappe.sendmail(
                recipients=[user_email],
                subject=f"New Lead: {lead.lead_name}",
                message=f"Lead {lead.lead_name} has been assigned to you."
            )
