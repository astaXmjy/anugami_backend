from rest_framework import serializers

class AnalyticsReportSerializer(serializers.Serializer):
    orders_active = serializers.IntegerField()
    new_signups = serializers.IntegerField()
    products_count = serializers.IntegerField()
    product_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    categorywise_product_count = serializers.ListField()
    total_earning = serializers.DecimalField(max_digits=10, decimal_places=2)
    admin_earning = serializers.DecimalField(max_digits=10, decimal_places=2)
    seller_earning = serializers.ListField()
    products_sold_out = serializers.IntegerField()
    low_stock_products = serializers.IntegerField()
    seller_details = serializers.DictField()
    top_sellers = serializers.ListField()
    top_categories = serializers.ListField()
    order_outlines = serializers.ListField()
