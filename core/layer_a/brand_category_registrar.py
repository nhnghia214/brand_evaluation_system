from crawler.db.db_connection import get_connection
from datetime import datetime


class BrandCategoryRegistrar:
    def get_or_create_brand(self, brand_name: str) -> int:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT BrandId FROM Brand WHERE BrandName = ?",
            (brand_name,)
        )
        row = cursor.fetchone()

        if row:
            conn.close()
            return row.BrandId

        cursor.execute(
            "INSERT INTO Brand (BrandName, CreatedAt) VALUES (?, ?)",
            (brand_name, datetime.now())
        )
        conn.commit()

        brand_id = cursor.execute(
            "SELECT SCOPE_IDENTITY()"
        ).fetchone()[0]

        conn.close()
        return int(brand_id)

    def get_or_create_category(
        self, category_name: str, platform="Shopee"
    ) -> int:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT CategoryId
            FROM Category
            WHERE CategoryName = ? AND Platform = ?
            """,
            (category_name, platform)
        )
        row = cursor.fetchone()

        if row:
            conn.close()
            return row.CategoryId

        cursor.execute(
            """
            INSERT INTO Category (CategoryName, Platform, CreatedAt)
            VALUES (?, ?, ?)
            """,
            (category_name, platform, datetime.now())
        )
        conn.commit()

        category_id = cursor.execute(
            "SELECT SCOPE_IDENTITY()"
        ).fetchone()[0]

        conn.close()
        return int(category_id)
    
    def get_or_create_brand_with_flag(self, brand_name: str) -> tuple[int, bool]:
        """
        Return:
        - brand_id
        - is_new (True nếu brand vừa được INSERT)
        """

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT BrandId FROM Brand WHERE BrandName = ?",
            (brand_name,)
        )
        row = cursor.fetchone()

        if row:
            conn.close()
            return row.BrandId, False

        # ✅ INSERT + lấy ID an toàn
        cursor.execute(
            """
            INSERT INTO Brand (BrandName, CreatedAt)
            OUTPUT INSERTED.BrandId
            VALUES (?, ?)
            """,
            (brand_name, datetime.now())
        )

        brand_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        return int(brand_id), True

