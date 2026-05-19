"""Generate raster favicons from design tokens (no SVG renderer required)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "public"
BG = (24, 24, 27, 255)
FG = (250, 250, 250, 255)
ACCENT = (59, 130, 246, 255)
INK = (24, 24, 27, 255)


def draw_bot(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(2, size // 16)
    radius = max(4, size // 4)
    draw.rounded_rectangle(
        (pad, pad, size - pad - 1, size - pad - 1),
        radius=radius,
        fill=BG,
    )

    face_w = int(size * 0.5)
    face_h = int(size * 0.42)
    face_x = (size - face_w) // 2
    face_y = int(size * 0.28)
    face_r = max(3, size // 8)
    draw.rounded_rectangle(
        (face_x, face_y, face_x + face_w, face_y + face_h),
        radius=face_r,
        fill=FG,
    )

    eye_r = max(1, size // 18)
    eye_y = face_y + face_h // 3
    draw.ellipse(
        (face_x + face_w // 4 - eye_r, eye_y - eye_r, face_x + face_w // 4 + eye_r, eye_y + eye_r),
        fill=INK,
    )
    draw.ellipse(
        (face_x + 3 * face_w // 4 - eye_r, eye_y - eye_r, face_x + 3 * face_w // 4 + eye_r, eye_y + eye_r),
        fill=INK,
    )

    mouth_w = max(4, face_w // 3)
    mouth_h = max(1, size // 24)
    mouth_x = (size - mouth_w) // 2
    mouth_y = face_y + int(face_h * 0.72)
    draw.rounded_rectangle(
        (mouth_x, mouth_y, mouth_x + mouth_w, mouth_y + mouth_h),
        radius=mouth_h,
        fill=INK,
    )

    stem_w = max(1, size // 20)
    stem_top = int(size * 0.16)
    stem_bottom = face_y
    cx = size // 2
    draw.line((cx, stem_top, cx, stem_bottom), fill=FG, width=stem_w)
    dot_r = max(2, size // 22)
    draw.ellipse((cx - dot_r, stem_top - dot_r - 1, cx + dot_r, stem_top + dot_r - 1), fill=ACCENT)
    return img


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, int] = {
        "favicon-16.png": 16,
        "favicon-32.png": 32,
        "apple-touch-icon.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
    }
    images: list[Image.Image] = []
    for name, px in sizes.items():
        im = draw_bot(px)
        im.save(ROOT / name, format="PNG", optimize=True)
        if px in (16, 32):
            images.append(im)

    ico_path = ROOT / "favicon.ico"
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32)],
        append_images=images[1:],
    )
    print(f"Wrote icons under {ROOT}")


if __name__ == "__main__":
    main()
