"""
brand_category_resolver.py

Layer A – Brand & category resolution

Responsibility:
- Validate brand and category existence
- Normalize input into internal IDs
- Resolve common categories by NAME (not ID)
"""

from typing import Optional
from crawler.db.db_connection import get_connection
from core.dto.resolve_result import ResolveResult


class BrandCategoryResolver:

    # ===============================
    # RESOLVE SINGLE BRAND / CATEGORY
    # ===============================
    def resolve(
        self,
        brand_name: str,
        category_name: Optional[str]
    ) -> ResolveResult:

        conn = get_connection()
        cursor = conn.cursor()

        # ---- Resolve Brand ----
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
            conn.close()
            return ResolveResult(
                status="INVALID_BRAND",
                brand_id=None,
                category_id=None
            )

        brand_id = brand_row.BrandId

        # ---- Resolve Category (optional) ----
        if category_name is None:
            conn.close()
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
        conn.close()

        if not category_row:
            return ResolveResult(
                status="INVALID_CATEGORY",
                brand_id=brand_id,
                category_id=None
            )

        return ResolveResult(
            status="VALID",
            brand_id=brand_id,
            category_id=category_row.CategoryId
        )

    # ===============================
    # ALL CATEGORIES OF A BRAND
    # ===============================
    def get_categories_of_brand(self, brand_id: int) -> list[int]:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT CategoryId
            FROM Product
            WHERE BrandId = ?
        """, (brand_id,))

        rows = cursor.fetchall()
        conn.close()

        return [r.CategoryId for r in rows]

    # ===============================
    # COMMON CATEGORIES (BY NAME)
    # ===============================
    def get_common_categories(self, brand_ids: list[int]) -> list[str]:
        """
        Return common category NAMES across brands
        (semantic comparison, not ID-based)
        """
        conn = get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(brand_ids))

        cursor.execute(f"""
            SELECT c.CategoryName
            FROM Product p
            JOIN Category c ON p.CategoryId = c.CategoryId
            WHERE p.BrandId IN ({placeholders})
            GROUP BY c.CategoryName
            HAVING COUNT(DISTINCT p.BrandId) = ?
        """, (*brand_ids, len(brand_ids)))

        rows = cursor.fetchall()
        conn.close()

        return [r.CategoryName for r in rows]

    # ===============================
    # MAP CATEGORY NAME → ID (PER BRAND)
    # ===============================
    def get_category_id_by_name(
        self,
        brand_id: int,
        category_name: str
    ) -> Optional[int]:

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 1 c.CategoryId
            FROM Product p
            JOIN Category c ON p.CategoryId = c.CategoryId
            WHERE p.BrandId = ?
              AND c.CategoryName = ?
        """, (brand_id, category_name))

        row = cursor.fetchone()
        conn.close()

        return row.CategoryId if row else None


resolver = BrandCategoryResolver()
