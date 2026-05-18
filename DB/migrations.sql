
ALTER TABLE news_queue 
ADD COLUMN IF NOT EXISTS image_url TEXT;

ALTER TABLE news_queue 
ADD COLUMN IF NOT EXISTS generated_image TEXT;


ALTER TABLE news_queue 
ADD COLUMN IF NOT EXISTS telegram_status TEXT DEFAULT 'pending';

ALTER TABLE news_queue 
ADD COLUMN IF NOT EXISTS facebook_status TEXT DEFAULT 'pending';


ALTER TABLE news_queue 
ADD COLUMN IF NOT EXISTS scheduled_publish_time TIMESTAMP;

ALTER TABLE news_queue 
ADD COLUMN IF NOT EXISTS published_at TIMESTAMP;