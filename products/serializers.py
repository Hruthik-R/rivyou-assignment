from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    relevance_score = serializers.FloatField(read_only=True, default=0.0)
    rank_reason = serializers.CharField(read_only=True, default="")

    class Meta:
        model = Product
        fields = [
            "id",
            "product_name",
            "product_description",
            "category",
            "tags",
            "created_at",
            "relevance_score",
            "rank_reason",
        ]
        read_only_fields = ["id", "created_at", "relevance_score", "rank_reason"]