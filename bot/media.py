"""
All conversion happens in /tmp, which is wiped when the function instance is
recycled. We never write processed output anywhere persistent -- it goes
straight from /tmp into Telegram via addStickerToSet, then is discarded.
"""
import subprocess
import json
import os
import uuid
from PIL import Image
import imageio_ffmpeg

from bot.config import STICKER_SIZE, MAX_VIDEO_SECONDS

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def tmp_path(suffix: str) -> str:
    return f"/tmp/{uuid.uuid4().hex}{suffix}"


def probe_dimensions(path: str) -> tuple[int, int, bool]:
    """Returns (width, height, is_video). Uses ffprobe bundled alongside ffmpeg."""
    ffprobe = FFMPEG.replace("ffmpeg", "ffprobe")
    if os.path.exists(ffprobe):
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", path],
            capture_output=True, text=True,
        )
        data = json.loads(out.stdout)
        stream = data["streams"][0]
        return stream["width"], stream["height"], True
    # fall back to treating it as a still image
    with Image.open(path) as im:
        return im.width, im.height, False


def needs_crop(width: int, height: int) -> bool:
    return width != height


def crop_box(width: int, height: int, choice: str) -> tuple[int, int, int, int]:
    """
    choice: one of 'left', 'center', 'right' (landscape) or 'top', 'middle', 'bottom' (portrait).
    Returns (x, y, w, h) of the square region to crop.
    """
    side = min(width, height)
    if width > height:  # landscape -> horizontal choices
        if choice == "left":
            x = 0
        elif choice == "right":
            x = width - side
        else:  # center
            x = (width - side) // 2
        y = 0
    else:  # portrait (or square, though square skips this path) -> vertical choices
        if choice == "top":
            y = 0
        elif choice == "bottom":
            y = height - side
        else:  # middle
            y = (height - side) // 2
        x = 0
    return x, y, side, side


def crop_options_for(width: int, height: int) -> list[str]:
    return ["left", "center", "right"] if width > height else ["top", "middle", "bottom"]


def convert_image_to_sticker(src_path: str, crop: tuple[int, int, int, int] | None) -> str:
    out_path = tmp_path(".webp")
    with Image.open(src_path) as im:
        im = im.convert("RGBA")
        if crop:
            x, y, w, h = crop
            im = im.crop((x, y, x + w, y + h))
        im = im.resize((STICKER_SIZE, STICKER_SIZE), Image.LANCZOS)
        im.save(out_path, "WEBP")
    return out_path


def convert_video_to_sticker(src_path: str, crop: tuple[int, int, int, int] | None) -> str:
    out_path = tmp_path(".webm")
    filters = []
    if crop:
        x, y, w, h = crop
        filters.append(f"crop={w}:{h}:{x}:{y}")
    filters.append(f"scale={STICKER_SIZE}:{STICKER_SIZE}")
    filters.append("fps=30")
    vf = ",".join(filters)

    cmd = [
        FFMPEG, "-y", "-i", src_path,
        "-t", str(MAX_VIDEO_SECONDS),
        "-vf", vf,
        "-c:v", "libvpx-vp9",
        "-b:v", "256k",
        "-an",
        out_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_path
