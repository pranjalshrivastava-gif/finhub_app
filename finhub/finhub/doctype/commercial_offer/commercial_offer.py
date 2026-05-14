import frappe
from frappe.model.document import Document
from frappe.utils import flt

class CommercialOffer(Document):
    def validate(self):
        """Standard Frappe validation trigger"""
        self.calculate_totals()
        self.apply_pricing_rules()

    def calculate_totals(self):
        """Requirement 1.4: Auto-calculate totals for line items"""
        total = 0.0
        if not self.get("items"):
            self.total_amount = 0.0
            return

        for item in self.items:
            # Defensive check for None values
            qty = flt(item.qty) if item.qty else 0.0
            rate = flt(item.rate) if item.rate else 0.0
            item.amount = qty * rate
            total += item.amount
        
        self.total_amount = total

    def apply_pricing_rules(self):
        """Requirement 1.6: Apply vertical-based pricing discounts"""
        if not self.vertical or flt(self.total_amount) <= 0:
            return
        
        # Optimized lookup using cache
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
        """Whitelisted API for JS to fetch base price safely"""
        if not finhub_module:
            return {"base_price": 0.0}
        
        data = frappe.db.get_value("Finhub Module", finhub_module, ["base_price"], as_dict=True)
        return data if data else {"base_price": 0.0}

    @frappe.whitelist()
    def calculate_client_side_totals(self):
        """
        Special method to trigger a full recalculation and return the value 
        to the JS UI before the document is actually saved.
        """
        self.calculate_totals()
        self.apply_pricing_rules()
        return self.total_amount