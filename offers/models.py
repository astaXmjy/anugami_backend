from django.db import models


class Offer(models.Model):
    OFFER_TYPES = [
        ("default", "Default"),
        ("category", "Category"),
        ("url", "URL"),
        ("product", "Product"),
    ]

    type = models.CharField(max_length=20, choices=OFFER_TYPES)
    image = models.ImageField(upload_to="offers/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} Offer"
