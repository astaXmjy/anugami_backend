from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import Offer
from .serializers import OfferSerializer


class OfferViewSet(viewsets.ModelViewSet):
    queryset = Offer.objects.all().order_by("-created_at")
    serializer_class = OfferSerializer

    @action(detail=False, methods=["get"])
    def filter_by_type(self, request):

        offer_type = request.query_params.get("type", None)
        if offer_type and offer_type in ["default", "category", "url", "product"]:
            offers = Offer.objects.filter(type=offer_type)
        else:
            offers = Offer.objects.all()

        serializer = OfferSerializer(offers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def get_offer(self, request, pk=None):
        offer = get_object_or_404(Offer, pk=pk)
        serializer = OfferSerializer(offer)
        return Response(serializer.data)
