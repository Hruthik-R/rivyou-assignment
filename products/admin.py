from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "product_name", "category", "tags")
    list_filter = ("category",)
    search_fields = ("product_name", "tags")
    ordering = ("id",)