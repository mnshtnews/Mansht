import io
import os
from typing import Optional, Callable

from PIL import Image, ImageDraw, ImageFilter
from io import BytesIO

from image.text_formatter import prepare_ar_text, fit_text
from utils.logger import logger


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_FONT_CANDIDATES = [
    os.path.join(_BASE_DIR, "Cairo-ExtraBold.ttf"),
    os.path.join(_BASE_DIR, "Cairo-Bold.ttf"),
    os.path.join(_BASE_DIR, "Cairo-Black.ttf"),  
]

FONT_PATH: str = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), "")
if not FONT_PATH:
    raise FileNotFoundError(
        "No Cairo font found. Expected one of: " + ", ".join(_FONT_CANDIDATES)
    )

logger.info(f"🔤 Using font: {os.path.basename(FONT_PATH)}")


MAX_FONT_SIZE = 60
MIN_FONT_SIZE = 26
TEXT_COLOR    = (255, 255, 255)


def _build_image_layer(
    base: Image.Image,
    news_img: Optional[Image.Image],
    image_box: tuple,
) -> Image.Image:


    if not news_img:
        return base

    image_x1, image_y1, image_x2, image_y2 = image_box
    box_w   = image_x2 - image_x1
    box_h   = image_y2 - image_y1
    img_w, img_h = news_img.size
    img_ratio    = img_w / img_h
    box_ratio    = box_w / box_h


    if img_ratio > box_ratio:
        bg_h, bg_w = box_h, int(box_h * img_ratio)
    else:
        bg_w, bg_h = box_w, int(box_w / img_ratio)

    bg = news_img.resize((bg_w, bg_h), Image.Resampling.LANCZOS).convert("RGBA")
    bx, by = (bg_w - box_w) // 2, (bg_h - box_h) // 2
    bg = bg.crop((bx, by, bx + box_w, by + box_h))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
    overlay = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 80))
    bg = Image.alpha_composite(bg, overlay)


    if img_ratio > box_ratio:
        fg_w, fg_h = box_w, int(box_w / img_ratio)
    else:
        fg_h, fg_w = box_h, int(box_h * img_ratio)

    fg   = news_img.resize((fg_w, fg_h), Image.Resampling.LANCZOS).convert("RGBA")
    fg_x = (box_w - fg_w) // 2
    fg_y = (box_h - fg_h) // 2

    layer = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    layer.paste(bg, (0, 0))
    layer.paste(fg, (fg_x, fg_y), fg)

    base.paste(layer, (image_x1, image_y1), layer)
    return base


def _draw_title(
    final_img: Image.Image,
    title: str,
    text_box: tuple,
) -> Image.Image:


    text_x1, text_y1, text_x2, text_y2 = text_box
    box_w   = text_x2 - text_x1
    box_h   = text_y2 - text_y1

    draw     = ImageDraw.Draw(final_img)
    ar_title = prepare_ar_text(title)

    font, lines, line_height = fit_text(
        draw, ar_title, FONT_PATH,
        box_w, box_h,
        MAX_FONT_SIZE, MIN_FONT_SIZE,
    )

    if not font:
        logger.error("❌ FONT FIT ERROR — title too long for any supported size")
        return final_img   

    assert lines is not None and line_height is not None

    lines.reverse()  

    total_h = len(lines) * line_height
    y = text_y1 + ((box_h - total_h) // 2)

    for line in lines:
        bbox  = draw.textbbox((0, 0), line, font=font)
        w     = bbox[2] - bbox[0]
        x     = text_x1 + ((box_w - w) // 2)


        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))

        draw.text((x, y), line, font=font, fill=TEXT_COLOR, stroke_width=1, stroke_fill=TEXT_COLOR)

        y += line_height

    return final_img


def generate_post_image(
    title: str,
    image_url: Optional[str],
    news_id: int,
    url: str,
    category: str,
    confidence: float,
    content: Optional[str],
    template_config: dict,
    session,
    upload_fn,
    supabase_storage,
    send_telegram_fn: Optional[Callable] = None,
    send_to_telegram: bool = True,
) -> Optional[str]:
    
    import traceback

    logger.info(f"🎨 Generating image | category={category} | id={news_id}")

    try:
        config = template_config.get(category) or template_config["عام"]

        image_box = config["image_box"]
        text_box  = config["text_box"]

        template_path = config.get("template", "")
        if not template_path or not os.path.exists(template_path):
            logger.error(f"❌ Template not found: {template_path}")
            return None

        template = Image.open(template_path).convert("RGBA")

        news_img = None
        if image_url:
            try:
                resp = session.get(image_url, timeout=20)
                resp.raise_for_status()
                news_img = Image.open(BytesIO(resp.content)).convert("RGBA")
            except Exception as exc:
                logger.warning(f"⚠️ Image download failed: {exc}")
                return None

        base = Image.new("RGBA", template.size, (0, 0, 0, 0))
        base.paste(template, (0, 0))
        base = _build_image_layer(base, news_img, image_box)

        if category in ("عام", "اجتماعية", "فن"):
            final_img = base
        else:
            background = Image.new("RGBA", template.size, (0, 0, 0, 255))
            background.paste(base, (0, 0), base)
            final_img = Image.alpha_composite(background, template)

        final_img = _draw_title(final_img, title, text_box)

        filename   = f"news_{news_id}.jpg"
        upload_fn(final_img, filename)
        public_url = supabase_storage.from_("generated").get_public_url(filename)

        if send_to_telegram and send_telegram_fn:
            buf = io.BytesIO()
            final_img.convert("RGB").save(buf, format="JPEG", quality=85)
            buf.seek(0)
            send_telegram_fn(buf, title, url, category, confidence, content or "")
            logger.info("🖼️ Image generated + sent to Telegram")

        return public_url

    except Exception as exc:
        logger.error(f"❌ Image generation error: {exc}")
        traceback.print_exc()
        return None
