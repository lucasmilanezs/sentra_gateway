# test_db.py
import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="sentra",
        password="sentra_secret",
        dbname="sentra_db",
    )
    print("Conexão OK")
    conn.close()
except Exception as e:
    print("ERRO:", e.args[0].encode("utf-8", errors="replace"))