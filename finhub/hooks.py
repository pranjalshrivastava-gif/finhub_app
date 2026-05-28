
app_name = "finhub"
app_title = "Finhub"
app_publisher = "Pranjal"
app_description = "Sales Automation"
app_email = "admin@finhub.com"
app_license = "mit"

doc_events = {
    "Commercial Offer": {
        "before_save": "finhub.api.automation.map_entity_on_save",
        "on_submit": "finhub.api.automation.auto_create_ticket"
    }
}

# ============================================
# FinHub Automation
# ============================================

doc_events = {
    "FinHub Lead": {
        "after_insert": "finhub.automation.lead_automation.assign_lead"
    },
    "FinHub Ticket": {
        "after_insert": "finhub.automation.ticket_automation.assign_ticket"
    }
}

scheduler_events = {
    "hourly": []
}
fixtures = [
    {
        "dt": "DocType",
        "filters": [["name", "=", "Business Vertical"]]
    }
]