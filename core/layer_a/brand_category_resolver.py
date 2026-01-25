"""
brand_category_resolver.py

Layer A – Brand & category resolution

Responsibility:
- Validate brand and category existence
- Normalize input into internal IDs
- Guard invalid requests before evaluation
"""
from pathlib import Path
import sys
import os

BASE_DIR = Path(__file__).resolve().parents[2]  # brand_evaluation_system
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

from typing import Optional

from crawler.db.db_connection import get_connection
from core.dto.resolve_result import ResolveResult


class BrandCategoryResolver:

    def resolve(
        self,
        brand_name: str,
        category_name: Optional[str]
    ) -> ResolveResult:
        """
        Resolve brand and category names into internal IDs.

        :param brand_name: brand name from user / system
        :param category_name: category name or None (ALL)
        :return: ResolveResult
        """

        conn = get_connection()
        cursor = conn.cursor()

        # ===============================
        # RESOLVE BRAND
        # ===============================
        cursor.execute(
            """
            SELECT BrandId
            FROM Brand
            WHERE BrandName = ?
            """,
            (brand_name,)
        )

        brand_row = cursor.fetchone()
        if not brand_row:
            return ResolveResult(
                status="INVALID_BRAND",
                brand_id=None,
                category_id=None
            )

        brand_id = brand_row[0]

        # ===============================
        # RESOLVE CATEGORY (OPTIONAL)
        # ===============================
        if category_name is None:
            return ResolveResult(
                status="VALID",
                brand_id=brand_id,
                category_id=None
            )

        cursor.execute(
            """
            SELECT CategoryId
            FROM Category
            WHERE CategoryName = ?
            """,
            (category_name,)
        )

        category_row = cursor.fetchone()
        if not category_row:
            return ResolveResult(
                status="INVALID_CATEGORY",
                brand_id=brand_id,
                category_id=None
            )

        return ResolveResult(
            status="VALID",
            brand_id=brand_id,
            category_id=category_row[0]
        )

resolver = BrandCategoryResolver()

print(resolver.resolve("Dell", "Laptop"))
print(resolver.resolve("Dell", None))
print(resolver.resolve("BrandKhongTonTai", "Laptop"))
