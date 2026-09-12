"""Generate an animated demonstration video."""

from __future__ import annotations

from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

WIDTH = 768
HEIGHT = 432
FPS = 12
DURATION_SECONDS = 8
OUTPUT = Path(__file__).resolve().parent / "animated_patient_transfer.mp4"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def draw_person(
    drawing: ImageDraw.ImageDraw,
    x: int,
    baseline: int,
    *,
    shirt: str,
    seated: bool,
) -> None:
    drawing.ellipse(
        (x - 17, baseline - 128, x + 17, baseline - 94),
        fill="#f1c7a5",
        outline="#233044",
        width=3,
    )
    drawing.rounded_rectangle(
        (x - 24, baseline - 94, x + 24, baseline - 35),
        radius=8,
        fill=shirt,
        outline="#233044",
        width=3,
    )
    if seated:
        drawing.line((x, baseline - 35, x + 28, baseline - 12), fill="#233044", width=8)
        drawing.line((x + 28, baseline - 12, x + 52, baseline - 12), fill="#233044", width=8)
    else:
        drawing.line((x - 10, baseline - 35, x - 17, baseline), fill="#233044", width=9)
        drawing.line((x + 10, baseline - 35, x + 17, baseline), fill="#233044", width=9)


def draw_wheelchair(drawing: ImageDraw.ImageDraw, x: int, baseline: int) -> None:
    drawing.ellipse((x - 20, baseline - 50, x + 42, baseline + 12), outline="#24364b", width=7)
    drawing.ellipse((x + 45, baseline - 11, x + 65, baseline + 9), outline="#24364b", width=5)
    drawing.line((x - 3, baseline - 78, x + 7, baseline - 24), fill="#24364b", width=7)
    drawing.line((x - 4, baseline - 25, x + 52, baseline - 25), fill="#24364b", width=7)
    drawing.line((x - 8, baseline - 78, x - 30, baseline - 78), fill="#24364b", width=6)


def make_frame(index: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#eef5f8")
    drawing = ImageDraw.Draw(image)

    drawing.rectangle((0, 0, WIDTH, 70), fill="#17324d")
    drawing.text((24, 17), "ANIMATED PATIENT-TRANSFER DEMO", fill="white", font=font(26))

    drawing.rectangle((0, 70, WIDTH, 315), fill="#dce8ed")
    drawing.polygon([(0, 315), (WIDTH, 315), (WIDTH, HEIGHT), (0, HEIGHT)], fill="#c2d2d9")
    drawing.line((0, 315, WIDTH, 315), fill="#8ea5af", width=4)
    for start_x in range(40, WIDTH, 150):
        drawing.line((start_x, HEIGHT, WIDTH // 2, 315), fill="#a7bbc3", width=2)

    drawing.rounded_rectangle(
        (45, 105, 190, 230),
        radius=8,
        fill="#ffffff",
        outline="#79909c",
        width=3,
    )
    drawing.text((76, 145), "HOSPITAL", fill="#365264", font=font(20))
    drawing.text((72, 175), "CORRIDOR", fill="#365264", font=font(20))

    progress = index / (FPS * DURATION_SECONDS - 1)
    group_x = int(180 + progress * 390)
    baseline = 336

    draw_wheelchair(drawing, group_x + 92, baseline)
    draw_person(drawing, group_x + 105, baseline - 25, shirt="#8cc5dd", seated=True)
    draw_person(drawing, group_x, baseline, shirt="#2878a5", seated=False)
    drawing.line(
        (group_x + 20, baseline - 78, group_x + 67, baseline - 93),
        fill="#f1c7a5",
        width=8,
    )

    drawing.rounded_rectangle((group_x - 45, 350, group_x + 45, 383), radius=7, fill="#2878a5")
    drawing.text((group_x - 34, 358), "NURSE", fill="white", font=font(17))
    drawing.rounded_rectangle((group_x + 62, 350, group_x + 150, 383), radius=7, fill="#4d6470")
    drawing.text((group_x + 71, 358), "PATIENT", fill="white", font=font(17))

    drawing.line((group_x - 82, 295, group_x - 35, 295), fill="#e36a2e", width=7)
    drawing.polygon(
        [(group_x - 30, 295), (group_x - 47, 284), (group_x - 47, 306)],
        fill="#e36a2e",
    )
    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    container = av.open(str(OUTPUT), mode="w")
    stream = container.add_stream("libx264", rate=FPS)
    stream.width = WIDTH
    stream.height = HEIGHT
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "22", "preset": "medium"}

    for index in range(FPS * DURATION_SECONDS):
        frame = av.VideoFrame.from_image(make_frame(index))
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.metadata["title"] = "Scenome synthetic patient-transfer demo"
    container.metadata["comment"] = "Programmatically generated; contains no recorded people."
    container.close()


if __name__ == "__main__":
    main()
