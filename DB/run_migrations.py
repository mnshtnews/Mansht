import psycopg2

conn = psycopg2.connect(
    dbname="YOUR_DB",
    user="YOUR_USER",
    password="YOUR_PASS",
    host="localhost"
)

cur = conn.cursor()

with open("migrations.sql", "r", encoding="utf-8") as f:
    sql = f.read()

cur.execute(sql)
conn.commit()

cur.close()
conn.close()

print("✅ Migrations applied successfully")