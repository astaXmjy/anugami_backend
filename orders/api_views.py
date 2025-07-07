from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Sum, Count, F
from django.shortcuts import get_object_or_404
from .models import Order, OrderItem
from sellers.models import Seller
from rest_framework import serializers

class OrderItemSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='order.seller.business_name', read_only=True)
    financial_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = '__all__'
    
    def get_financial_breakdown(self, obj):
        return obj.get_financial_breakdown()

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    seller_name = serializers.CharField(source='seller.business_name', read_only=True)
    
    class Meta:
        model = Order
        fields = '__all__'

@api_view(['GET'])
@permission_classes([AllowAny])
def all_orders_products(request):
    '''Get all order items (products) across all orders'''
    
    # Get query parameters
    seller_id = request.query_params.get('seller_id')
    
    # Base queryset
    items = OrderItem.objects.select_related('order', 'order__seller').all()
    
    # Apply seller filter if provided
    if seller_id:
        items = items.filter(order__seller_id=seller_id)
        try:
            seller = Seller.objects.get(id=seller_id)
            seller_info = {
                'id': seller.id,
                'name': seller.business_name,
                'commission_rate': seller.commission_rate
            }
        except Seller.DoesNotExist:
            seller_info = None
    else:
        seller_info = None
    
    # Serialize the data
    serializer = OrderItemSerializer(items, many=True)
    
    # Calculate totals
    total_items = items.count()
    total_sale_amount = sum(float(item.sale_price or 0) * item.quantity for item in items)
    total_commission = sum(float(item.commission_for_each_seller) for item in items)
    total_seller_receives = sum(float(item.amount_seller_receives) for item in items)
    total_profit = sum(float(item.profit_amount) for item in items)
    
    return Response({
        'seller_info': seller_info,
        'summary': {
            'total_items': total_items,
            'total_sale_amount': total_sale_amount,
            'total_commission': total_commission,
            'total_seller_receives': total_seller_receives,
            'total_profit': total_profit,
        },
        'items': serializer.data
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def orders_by_seller(request):
    '''Get orders filtered by seller with commission calculations'''
    
    seller_id = request.query_params.get('seller_id')
    
    if not seller_id:
        return Response(
            {'error': 'seller_id parameter is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get seller
    seller = get_object_or_404(Seller, id=seller_id)
    
    # Get orders for this seller
    orders = Order.objects.filter(seller=seller).prefetch_related('items')
    
    serializer = OrderSerializer(orders, many=True)
    
    # Calculate summary
    total_orders = orders.count()
    all_items = OrderItem.objects.filter(order__seller=seller)
    total_commission = sum(float(item.commission_for_each_seller) for item in all_items)
    total_seller_amount = sum(float(item.amount_seller_receives) for item in all_items)
    
    return Response({
        'seller': {
            'id': seller.id,
            'name': seller.business_name,
            'commission_rate': seller.commission_rate
        },
        'summary': {
            'total_orders': total_orders,
            'total_commission': total_commission,
            'total_seller_amount': total_seller_amount
        },
        'orders': serializer.data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_seller_commission(request):
    '''Update commission rate for a specific seller'''
    
    seller_id = request.data.get('seller_id')
    commission_rate = request.data.get('commission_rate')
    
    if not seller_id or not commission_rate:
        return Response(
            {'error': 'seller_id and commission_rate are required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        seller = Seller.objects.get(id=seller_id)
        old_rate = seller.commission_rate
        seller.commission_rate = float(commission_rate)
        seller.save()
        
        # Update all existing order items for this seller
        orders = Order.objects.filter(seller=seller)
        updated_items = 0
        
        for order in orders:
            for item in order.items.all():
                item.commission_rate = seller.commission_rate
                item.save()  # This will recalculate all amounts
                updated_items += 1
        
        return Response({
            'message': 'Commission rate updated successfully',
            'seller_id': seller.id,
            'seller_name': seller.business_name,
            'old_rate': old_rate,
            'new_commission_rate': seller.commission_rate,
            'updated_items': updated_items
        })
        
    except Seller.DoesNotExist:
        return Response(
            {'error': 'Seller not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except ValueError:
        return Response(
            {'error': 'Invalid commission_rate format'}, 
            status=status.HTTP_400_BAD_REQUEST
        )