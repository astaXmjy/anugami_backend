from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'order_id', 
        'transaction_id', 
        'amount', 
        'total_amount', 
        'status', 
        'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('order_id', 'transaction_id', 'phonepe_transaction_id')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make certain fields read-only after creation
        """
        if obj:  # editing an existing object
            return self.readonly_fields + ('order_id', 'amount')
        return self.readonly_fields