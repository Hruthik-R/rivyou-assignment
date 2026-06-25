from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
class Product(models.Model):

    class Category(models.TextChoices):
        SMARTPHONES = "Smartphones", "Smartphones"
        CHARGERS = "Chargers", "Chargers"
        BACK_COVERS = "Back Covers", "Back Covers"

    id = models.AutoField(primary_key=True)
    product_name = models.CharField(max_length=255)
    product_description = models.TextField()
    category = models.CharField(
        max_length=50,
        choices=Category.choices,
    )
    tags = ArrayField(
        base_field=models.CharField(max_length=100),
        blank=True,
        default=list,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["category"], name="product_category_idx"),
           GinIndex(fields=["tags"], name="product_tags_idx"),
        ]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.product_name