"""
All conversion happens in /tmp, which is wiped when the function instance is
recycled. We never write processed output anywhere persistent -- it goes
straight from /tmp into Telegram via addStickerToSet, then is discarded.
"""
import subprocess
import json
import os
import uuid
from collections import deque
from PIL import Image, ImageDraw, ImageChops
import imageio_ffmpeg

from bot.config import STICKER_SIZE, MAX_VIDEO_SECONDS

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

SHAPES = ("square", "rounded", "circle")


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


def remove_background_simple(im: Image.Image, tolerance: int = 30) -> Image.Image:
    """
    Lightweight, no-ML background removal: flood-fills transparency inward
    from the four corners for pixels close in color to the corner they touch.
    Runs on the already-resized 512x512 image so it stays fast (pure Python,
    no extra dependency). Works well for solid or near-solid backgrounds
    (product shots, plain walls); won't cleanly separate a subject from a
    busy, textured, or gradient background -- that needs real ML segmentation.
    """
    im = im.convert("RGBA")
    w, h = im.size
    pixels = im.load()
    visited = bytearray(w * h)
    q = deque()

    def close_enough(c1, c2):
        return abs(c1[0] - c2[0]) <= tolerance and abs(c1[1] - c2[1]) <= tolerance and abs(c1[2] - c2[2]) <= tolerance

    for cx, cy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        idx = cy * w + cx
        if not visited[idx]:
            visited[idx] = 1
            q.append((cx, cy, pixels[cx, cy][:3]))

    while q:
        x, y, ref = q.popleft()
        r, g, b, a = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                idx = ny * w + nx
                if not visited[idx] and close_enough(pixels[nx, ny][:3], ref):
                    visited[idx] = 1
                    q.append((nx, ny, ref))
    return im


def apply_shape_mask(im: Image.Image, shape: str) -> Image.Image:
    """Combines with any existing alpha (e.g. from background removal) rather
    than replacing it, so a circle-shaped, background-removed sticker gets
    both effects at once instead of one clobbering the other."""
    if shape not in ("rounded", "circle"):
        return im
    im = im.convert("RGBA")
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    if shape == "circle":
        draw.ellipse((0, 0, w, h), fill=255)
    else:
        draw.rounded_rectangle((0, 0, w, h), radius=min(w, h) // 6, fill=255)
    r, g, b, a = im.split()
    im.putalpha(ImageChops.multiply(a, mask))
    return im


def _build_shape_mask_png(shape: str) -> str:
    mask_path = tmp_path(".png")
    mask = Image.new("L", (STICKER_SIZE, STICKER_SIZE), 0)
    draw = ImageDraw.Draw(mask)
    if shape == "circle":
        draw.ellipse((0, 0, STICKER_SIZE, STICKER_SIZE), fill=255)
    else:
        draw.rounded_rectangle((0, 0, STICKER_SIZE, STICKER_SIZE), radius=STICKER_SIZE // 6, fill=255)
    mask.save(mask_path, "PNG")
    return mask_path


def convert_image_to_sticker(src_path: str, crop: tuple[int, int, int, int] | None,
                              shape: str = "square", remove_bg: bool = False) -> str:
    out_path = tmp_path(".webp")
    with Image.open(src_path) as im:
        im = im.convert("RGBA")
        if crop:
            x, y, w, h = crop
            im = im.crop((x, y, x + w, y + h))
        im = im.resize((STICKER_SIZE, STICKER_SIZE), Image.LANCZOS)
        if remove_bg:
            im = remove_background_simple(im)
        im = apply_shape_mask(im, shape)
        im.save(out_path, "WEBP")
    return out_path


def convert_video_to_sticker(src_path: str, crop: tuple[int, int, int, int] | None,
                              shape: str = "square") -> str:
    out_path = tmp_path(".webm")
    filters = []
    if crop:
        x, y, w, h = crop
        filters.append(f"crop={w}:{h}:{x}:{y}")
    filters.append(f"scale={STICKER_SIZE}:{STICKER_SIZE}")
    filters.append("fps=30")
    vf = ",".join(filters)

    if shape in ("rounded", "circle"):
        mask_path = _build_shape_mask_png(shape)
        try:
            cmd = [
                FFMPEG, "-y", "-i", src_path, "-loop", "1", "-i", mask_path,
                "-filter_complex",
                f"[0:v]{vf},format=rgba[base];[1:v]format=gray[mask];[base][mask]alphamerge",
                "-t", str(MAX_VIDEO_SECONDS),
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-b:v", "256k",
                "-an", "-shortest",
                out_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        finally:
            os.remove(mask_path)
        return out_path

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
