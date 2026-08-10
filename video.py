import os
import shutil
import subprocess
import tempfile
import textwrap

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 720
BG_COLOR = (13, 17, 23)  # dark editor fon
TEXT_COLOR = (201, 209, 217)
ACCENT_COLOR = (88, 166, 255)
FONT_SIZE = 34
LINE_SPACING = 14
PADDING = 60
FPS = 30
CHARS_PER_SECOND = 18  # yozish tezligi


def _find_monospace_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Monospace shrift topilmadi. `sudo apt install fonts-dejavu-core` bilan o'rnating."
    )


def _wrap_code(code: str, max_chars: int = 60) -> list[str]:
    lines = []
    for raw_line in code.split("\n"):
        if not raw_line.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(raw_line, width=max_chars) or [""]
        lines.extend(wrapped)
    return lines


def _draw_frame(lines: list[str], chars_shown: int, font: ImageFont.FreeTypeFont, title: str) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # sarlavha
    draw.text((PADDING, 30), title, font=font, fill=ACCENT_COLOR)

    y = 100
    remaining = chars_shown
    for line in lines:
        if remaining <= 0:
            visible = ""
        elif remaining >= len(line):
            visible = line
            remaining -= len(line) + 1  # +1 yangi qator uchun
        else:
            visible = line[:remaining]
            remaining = 0
        draw.text((PADDING, y), visible, font=font, fill=TEXT_COLOR)
        y += FONT_SIZE + LINE_SPACING
        if y > HEIGHT - PADDING:
            break
    return img


def generate_code_video(code: str, title: str, output_path: str) -> bool:
    """
    Kod matnini "yozilayotgan" animatsiya sifatida videoga aylantiradi.
    Muvaffaqiyatli bo'lsa True, aks holda False qaytaradi.
    """
    if not shutil.which("ffmpeg"):
        return False

    try:
        font_path = _find_monospace_font()
        font = ImageFont.truetype(font_path, FONT_SIZE)
        title_font = ImageFont.truetype(font_path, FONT_SIZE + 4)
    except Exception:
        return False

    lines = _wrap_code(code)
    total_chars = sum(len(l) + 1 for l in lines)
    if total_chars == 0:
        return False

    duration_seconds = max(3, min(15, total_chars / CHARS_PER_SECOND))
    total_frames = int(duration_seconds * FPS)

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(total_frames):
            progress = (i + 1) / total_frames
            chars_shown = int(total_chars * progress)
            frame = _draw_frame(lines, chars_shown, font, title)
            frame.save(os.path.join(tmpdir, f"frame_{i:05d}.png"))

        # oxirgi kadrni bir necha marta takrorlaymiz, tugagach 1 soniya "to'xtab tursin"
        hold_frames = FPS
        last_frame = _draw_frame(lines, total_chars, font, title)
        for j in range(hold_frames):
            last_frame.save(os.path.join(tmpdir, f"frame_{total_frames + j:05d}.png"))

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-framerate", str(FPS),
                    "-i", os.path.join(tmpdir, "frame_%05d.png"),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path,
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            return os.path.exists(output_path)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
