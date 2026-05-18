import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from DB.db import get_conn

conn = get_conn()


conn.autocommit = True

cursor = conn.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    title TEXT UNIQUE,
    url TEXT UNIQUE,
    image TEXT,
    category TEXT,
    confidence REAL,
    content TEXT,
    reviewed BOOLEAN DEFAULT FALSE,
    locked_by TEXT,
    locked_at TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS confirmed_training (
    id SERIAL PRIMARY KEY,
    title TEXT UNIQUE,
    category TEXT,
    confidence REAL,
    source TEXT DEFAULT 'auto',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS news_queue (
    id SERIAL PRIMARY KEY,

    article_id INT,
    title TEXT,
    url TEXT,
    content TEXT,

    created_at DOUBLE PRECISION,

    keyword_score FLOAT DEFAULT 0,
    aging_score FLOAT DEFAULT 0,
    ai_score FLOAT DEFAULT 0,
    final_score FLOAT DEFAULT 0,

    status TEXT DEFAULT 'pending',

    telegram_status TEXT DEFAULT 'pending',
    facebook_status TEXT DEFAULT 'pending',

    generated_image TEXT,
    image_url TEXT,

    scheduled_publish_time TIMESTAMP,
    published_at TIMESTAMP,

    last_updated TIMESTAMP DEFAULT NOW()
);
""")


cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_news_reviewed
ON news(reviewed);
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_news_confidence
ON news(confidence);
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_news_created_at
ON news(created_at DESC);
""")



cursor.close()
conn.close()

print("✅ Tables + indexes created successfully")