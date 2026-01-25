from crawler.db.connection import get_connection

def run():       
    conn = get_connection()
    print("DB OK")
