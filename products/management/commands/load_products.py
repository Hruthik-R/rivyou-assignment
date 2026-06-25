import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from products.models import Product


class Command(BaseCommand):
    help = "Load products from products_data.csv located in BASE_DIR"

    def handle(self, *args, **options):
        csv_path = Path(settings.BASE_DIR) / "products_data.csv"

        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        # Fetch all existing ids to skip duplicates
        existing_ids = set(Product.objects.values_list("id", flat=True))

        to_create = []

        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)

            for row in reader:
                row = {k.strip(): v.strip() for k, v in row.items()}

                product_id = int(row["id"])
                if product_id in existing_ids:
                    continue

                tags_raw = row.get("tags", "")
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

                to_create.append(
                    Product(
                        id=product_id,
                        product_name=row["product_name"],
                        product_description=row["product_description"],
                        category=row["category"],
                        tags=tags,
                    )
                )

        if not to_create:
            self.stdout.write(self.style.WARNING("No new products to load."))
            return

        BATCH_SIZE = 100
        Product.objects.bulk_create(to_create, batch_size=BATCH_SIZE)

        self.stdout.write(
            self.style.SUCCESS(f"Loaded {len(to_create)} products successfully")
        )