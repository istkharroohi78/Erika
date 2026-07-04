# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License.

import os
import aiohttp

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
    ImageStat,
)

from anony import config
from anony.helpers import Track

CANVAS_SIZE = (1280, 720)

# --- Card layout (matches the reference screenshot) ---
CARD_SIZE = (620, 560)          # whole card (cover + bottom info bar)
IMAGE_HEIGHT = 360               # height of the cover-art portion
CORNER_RADIUS = 30

AVATAR_SIZE = 80
AVATAR_PAD = 18

BRAND_NAME = "Chahat x mAsTeR"   # shown in the top-left pill / "Powered By" line


class Thumbnail:
    def __init__(self):
        self.fill = (255, 255, 255)
        self.font_title = ImageFont.truetype(
            "anony/helpers/Poppins-ExtraBold.ttf", 40
        )
        self.font_subtitle = ImageFont.truetype(
            "anony/helpers/Raleway-Bold.ttf", 22
        )
        self.font_channel = ImageFont.truetype(
            "anony/helpers/Raleway-Bold.ttf", 20
        )
        self.font_pill = ImageFont.truetype(
            "anony/helpers/Raleway-Bold.ttf", 22
        )
        self.font_note = ImageFont.truetype(
            "anony/helpers/Raleway-Bold.ttf", 42
        )

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                open(output_path, "wb").write(await resp.read())
            return output_path

    def fit_image(self, image, size):
        return ImageOps.fit(
            image,
            size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

    def add_round_corners(self, image, radius, corners=(True, True, True, True)):
        """corners = (top_left, top_right, bottom_right, bottom_left)"""
        rounded = image.convert("RGBA")
        w, h = rounded.size
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)

        draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)

        # square off corners that should NOT be rounded
        tl, tr, br, bl = corners
        if not tl:
            draw.rectangle((0, 0, radius, radius), fill=255)
        if not tr:
            draw.rectangle((w - radius, 0, w, radius), fill=255)
        if not br:
            draw.rectangle((w - radius, h - radius, w, h), fill=255)
        if not bl:
            draw.rectangle((0, h - radius, radius, h), fill=255)

        output = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        output.paste(rounded, (0, 0), mask)
        return output

    def truncate(self, text: str, limit: int) -> str:
        return text[: limit - 3] + "..." if len(text) > limit else text

    def rounded_pill(self, draw, xy, text, font, fg=(255, 255, 255),
                      bg=(15, 15, 15, 200), pad_x=16, pad_y=8):
        x, y = xy
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        box = [x, y, x + w + pad_x * 2, y + h + pad_y * 2]
        draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=bg)
        draw.text((x + pad_x, y + pad_y - bbox[1]), text, font=font, fill=fg)
        return box

    async def get_user_dp(self, client, user_id, output_path: str):
        """Downloads the requester's Telegram profile photo. Returns the
        local file path, or None if the user has no profile photo / it
        couldn't be fetched (caller should fall back to the note icon)."""
        if client is None or user_id is None:
            return None
        try:
            photos = await client.get_profile_photos(user_id, limit=1)
            if not photos or getattr(photos, "total_count", len(photos)) == 0:
                return None
            file_id = photos[0].file_id
            path = await client.download_media(file_id, file_name=output_path)
            return path
        except Exception:
            return None

    async def generate(self, song: Track, client=None, user_id=None, size=(1280, 720)) -> str:
        try:
            os.makedirs("cache", exist_ok=True)

            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"

            if os.path.exists(output):
                os.remove(output)

            await self.save_thumb(temp, song.thumbnail)

            cover = Image.open(temp).convert("RGBA")

            # requester's Telegram profile photo (falls back to None)
            dp_temp = f"cache/dp_{song.id}.jpg"
            dp_path = await self.get_user_dp(client, user_id, dp_temp)

            # --- dominant color sample (kept for future tinting use) ---
            small = cover.resize((50, 50))
            r, g, b = ImageStat.Stat(small.convert("RGB")).mean[:3]

            # --- Blurred, darkened background ---
            background = self.fit_image(cover, CANVAS_SIZE)
            background = background.filter(ImageFilter.GaussianBlur(35))
            background = ImageEnhance.Brightness(background).enhance(0.55)

            canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 255))
            canvas.alpha_composite(background)

            # --- Card shadow (subtle) ---
            shadow = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
            sdraw = ImageDraw.Draw(shadow)
            cx = (CANVAS_SIZE[0] - CARD_SIZE[0]) // 2
            cy = (CANVAS_SIZE[1] - CARD_SIZE[1]) // 2
            sdraw.rounded_rectangle(
                (cx - 6, cy - 6, cx + CARD_SIZE[0] + 6, cy + CARD_SIZE[1] + 6),
                radius=CORNER_RADIUS + 6,
                fill=(0, 0, 0, 120),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(18))
            canvas.alpha_composite(shadow)

            # --- Build the card itself ---
            card = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))

            # card background (dark, rounded on all corners)
            card_mask = Image.new("L", CARD_SIZE, 0)
            ImageDraw.Draw(card_mask).rounded_rectangle(
                (0, 0, CARD_SIZE[0], CARD_SIZE[1]), radius=CORNER_RADIUS, fill=255
            )
            bg_layer = Image.new("RGBA", CARD_SIZE, (32, 32, 34, 255))
            card.paste(bg_layer, (0, 0), card_mask)

            # cover art, rounded only on the top corners
            art = self.fit_image(cover, (CARD_SIZE[0], IMAGE_HEIGHT))
            art = self.add_round_corners(
                art, CORNER_RADIUS, corners=(True, True, False, False)
            )
            card.alpha_composite(art, (0, 0))

            draw = ImageDraw.Draw(card)

            # top-left pill: brand tag
            self.rounded_pill(draw, (18, 18), BRAND_NAME, self.font_pill)

            # top-right pill: duration
            duration = song.duration
            bbox = draw.textbbox((0, 0), duration, font=self.font_pill)
            w = bbox[2] - bbox[0]
            self.rounded_pill(
                draw, (CARD_SIZE[0] - w - 18 - 32, 18), duration, self.font_pill
            )

            # bottom-left pill (on the image), channel name
            channel_short = self.truncate(song.channel_name, 14)
            self.rounded_pill(
                draw, (18, IMAGE_HEIGHT - 56), channel_short, self.font_pill
            )

            # --- Bottom info bar ---
            info_top = IMAGE_HEIGHT

            # requester DP tile — falls back to a music-note icon if no DP
            icon_box = (
                AVATAR_PAD,
                info_top + AVATAR_PAD,
                AVATAR_PAD + AVATAR_SIZE,
                info_top + AVATAR_PAD + AVATAR_SIZE,
            )

            if dp_path and os.path.exists(dp_path):
                dp_img = Image.open(dp_path).convert("RGBA")
                dp_img = self.fit_image(dp_img, (AVATAR_SIZE, AVATAR_SIZE))
                dp_img = self.add_round_corners(dp_img, 14)
                card.alpha_composite(dp_img, (AVATAR_PAD, info_top + AVATAR_PAD))
            else:
                accent = (
                    min(int(r) + 30, 255),
                    min(int(g) + 30, 255),
                    min(int(b) + 30, 255),
                )
                draw.rounded_rectangle(icon_box, radius=14, fill=accent)
                note = "\u266A"  # ♪
                nbbox = draw.textbbox((0, 0), note, font=self.font_note)
                nw, nh = nbbox[2] - nbbox[0], nbbox[3] - nbbox[1]
                note_x = icon_box[0] + (AVATAR_SIZE - nw) / 2 - nbbox[0]
                note_y = icon_box[1] + (AVATAR_SIZE - nh) / 2 - nbbox[1]
                draw.text((note_x, note_y), note, font=self.font_note, fill=(255, 255, 255))

            text_x = AVATAR_PAD + AVATAR_SIZE + 18

            title = self.truncate(song.title, 22)
            draw.text(
                (text_x, info_top + 14),
                title,
                font=self.font_title,
                fill=(255, 255, 255),
            )

            draw.text(
                (text_x, info_top + 66),
                f"Powered By : {BRAND_NAME}",
                font=self.font_subtitle,
                fill=(210, 210, 210),
            )

            channel_full = self.truncate(song.channel_name, 24)
            draw.text(
                (text_x, info_top + 98),
                f"{channel_full}  |  {duration}",
                font=self.font_channel,
                fill=(180, 180, 180),
            )

            canvas.alpha_composite(card, (cx, cy))

            canvas.convert("RGB").save(output, format="PNG", optimize=True)

            try:
                os.remove(temp)
            except Exception:
                pass

            try:
                if dp_path and os.path.exists(dp_path):
                    os.remove(dp_path)
            except Exception:
                pass

            return output

        except Exception:
            return config.DEFAULT_THUMB
