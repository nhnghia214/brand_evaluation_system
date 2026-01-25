from db.db_connection import get_connection

def get_products_by_brand_category(brand_id, category_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ProductId, ProductUrl
        FROM Product
        WHERE BrandId = ? AND CategoryId = ?
    """, brand_id, category_id)

    rows = cursor.fetchall()
    conn.close()

    return rows


def insert_product(product_id, product_name, brand_id, category_id, product_url):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM Product WHERE ProductId = ?
        )
        INSERT INTO Product (ProductId, ProductName, BrandId, CategoryId, ProductUrl, CreatedAt)
        VALUES (?, ?, ?, ?, ?, GETDATE())
    """, product_id, product_id, product_name, brand_id, category_id, product_url)

    conn.commit()
    conn.close()
