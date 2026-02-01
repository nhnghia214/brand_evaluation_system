from crawler.db.db_connection import get_connection
from core.layer_b.analysis_service import AnalysisService

analysis = AnalysisService()

conn = get_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT DISTINCT BrandId, CategoryId
    FROM BrandAnalysisResult
""")

pairs = cursor.fetchall()
conn.close()

print(f"Rebuilding score for {len(pairs)} brand-category pairs")

for row in pairs:
    analysis._analyze_by_id(row.BrandId, row.CategoryId)

print("DONE")
