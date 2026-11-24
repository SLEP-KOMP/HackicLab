"""Генерация брендинга HackicLab: логотип, иконки, social preview.

Оригинальная графика без сторонних логотипов: синий градиентный «сквиркл»,
белая монограмма H с дорожкой и узлом (плата/EFI). Запуск:

    python tools/make_branding.py
"""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "hackiclab" / "assets" / "branding"

SIZE = 1024
SS = 4  # суперсэмплинг для сглаживания
C1 = (11, 99, 246)    # #0B63F6
C2 = (0, 212, 255)    # #00D4FF
DARK1 = (10, 18, 32)  # фон баннера
DARK2 = (14, 30, 58)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(size: int, c1=C1, c2=C2) -> Image.Image:
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    n = size * 2
    for i in range(n):
        draw.line([(i, 0), (0, i)], fill=_lerp(c1, c2, i / (n - 1)))
    return img


def logo(size: int = SIZE) -> Image.Image:
    w = size * SS
    grad = _gradient(w)
    mask = Image.new("L", (w, w), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, w - 1, w - 1], radius=int(w * 0.225), fill=255)
    img = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    bar = int(w * 0.085)
    left, right = int(w * 0.295), int(w * 0.705)
    top, bot = int(w * 0.29), int(w * 0.71)
    mid = (top + bot) // 2
    r = int(bar * 0.42)
    draw.rounded_rectangle([left - bar // 2, top, left + bar // 2, bot], radius=r, fill=white)
    draw.rounded_rectangle([right - bar // 2, top, right + bar // 2, bot], radius=r, fill=white)
    draw.rounded_rectangle([left, mid - bar // 2, right, mid + bar // 2], radius=r, fill=white)
    # дорожка к узлу справа — намёк на плату и EFI
    draw.rounded_rectangle([right + bar // 2, mid - bar // 5,
                            int(w * 0.78), mid + bar // 5], radius=bar // 5, fill=white)
    node = int(w * 0.03)
    draw.ellipse([int(w * 0.78) - node, mid - node,
                  int(w * 0.78) + node, mid + node], fill=white)
    return img.resize((size, size), Image.LANCZOS)


def write_icns(out: Path) -> bool:
    """Собирает .icns из PNG-слоёв вручную (Pillow может не уметь ICNS)."""
    layers = [(16, b"icp4"), (32, b"icp5"), (64, b"icp6"),
              (128, b"ic07"), (256, b"ic08"), (512, b"ic09"), (1024, b"ic10")]
    chunks = []
    for size, kind in layers:
        png = OUT / f".tmp-{size}.png"
        logo(size).save(png, "PNG")
        data = png.read_bytes()
        png.unlink()
        chunks.append(kind + struct.pack(">I", 8 + len(data)) + data)
    body = b"".join(chunks)
    out.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + body)
    return True


def social_preview(path: Path) -> None:
    width, height = 1280, 640
    bg = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(bg)
    for y in range(height):
        draw.line([(0, y), (width, y)], fill=_lerp(DARK1, DARK2, y / (height - 1)))
    icon = logo(360)
    bg.paste(icon, (80, 140), icon)
    bold = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 118)
    regular = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 42)
    draw.text((500, 190), "HackicLab", font=bold, fill=(255, 255, 255))
    draw.text((505, 330), "OpenCore EFI builder for Windows", font=regular, fill=(150, 180, 220))
    draw.text((505, 395), "Open source · MIT · RU / EN", font=regular, fill=(110, 140, 180))
    bg.save(path, "PNG")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = logo(SIZE)
    icon.save(OUT / "logo-1024.png", "PNG")
    icon.resize((512, 512), Image.LANCZOS).save(OUT / "logo-512.png", "PNG")
    icon.resize((256, 256), Image.LANCZOS).save(OUT / "logo-256.png", "PNG")
    icon.save(OUT / "icon.ico",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                     (64, 64), (128, 128), (256, 256)])
    write_icns(OUT / "icon.icns")
    social_preview(OUT / "social-preview.png")
    for name in ("logo-1024.png", "logo-512.png", "logo-256.png",
                 "icon.ico", "icon.icns", "social-preview.png"):
        p = OUT / name
        print(f"{name}: {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
