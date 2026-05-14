import frappe
from frappe.model.document import Document
from frappe.utils import flt

class FinhubOffer(Document):
    def validate(self):
        """Main validation method"""
        self.map_customer_data()
        self.sync_vertical_from_product()
        self.calculate_totals()
    
    def map_customer_data(self):
        """Map customer details to offer"""
        if self.customer:
            c_data = frappe.db.get_value("Customer", self.customer, 
                ["territory", "customer_group", "default_currency"], as_dict=True)
            if c_data:
                if not self.get("territory"):
                    self.territory = c_data.get("territory")
                if not self.get("customer_group"):
                    self.customer_group = c_data.get("customer_group")
                if not self.get("currency"):
                    self.currency = c_data.get("default_currency") or "INR"
    
    def sync_vertical_from_product(self):
        """Set vertical from selected product"""
        if self.product and not self.get("vertical"):
            vertical = frappe.db.get_value("Finhub Product", self.product, "vertical")
            if vertical:
                self.vertical = vertical
    
    def calculate_totals(self):
        """Calculate total amount from items"""
        total = 0
        items = self.get("items") or []
        for item in items:
            # Ensure amount is calculated
            amount = flt(item.qty) * flt(item.rate)
            item.amount = amount
            total += amount
        self.total_amount = total
    
    @frappe.whitelist()
    def get_product_features(self):
        """Fetch product features and apply pricing"""
        if not self.product:
            frappe.msgprint("Please select a product first")
            return []
        
        # Clear existing items
        self.set("items", [])
        
        # Get product document
        try:
            product_doc = frappe.get_doc("Finhub Product", self.product)
        except Exception as e:
            frappe.msgprint(f"Error loading product: {str(e)}")
            return []
        
        # Get pricing rule discount
        discount_percent = 0
        pricing_rule = frappe.db.get_value("Finhub Pricing Rule", 
            {"product": self.product, "is_active": 1}, "discount_percentage")
        if pricing_rule:
            discount_percent = flt(pricing_rule)
        
        # Add features to items
        features_added = 0
        for feature in product_doc.get("product_features", []):
            base_rate = flt(feature.get("price", 0))
            final_rate = base_rate
            
            if discount_percent > 0:
                final_rate = base_rate * (1 - discount_percent / 100.0)
            
            # Create item row
            item = self.append("items", {})
            item.feature_name = feature.get("feature_name")
            item.description = feature.get("description")
            item.qty = 1
            item.base_rate = base_rate
            item.rate = final_rate
            item.amount = final_rate
            item.discount_percentage = discount_percent
            item.is_standard = 1 if feature.get("is_included") else 0
            
            features_added += 1
        
        if features_added > 0:
            frappe.msgprint(f"Added {features_added} features with {discount_percent}% discount")
        else:
            frappe.msgprint("No features found for this product")
        
        self.calculate_totals()
        return self.get("items")
    
    def on_submit(self):
        """When submitted, change status to Open"""
        if self.status == "Draft":
            self.status = "Open"
