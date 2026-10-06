"""Generate the lightweight README demo animation.

The animation is intentionally deterministic: it demonstrates the product flow
without calling paid model APIs or embedding private user data.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "demo" / "ai-private-chef-demo.gif"
WIDTH, HEIGHT = 1280, 720

INK = "#17251f"
MUTED = "#7c847f"
LINE = "#e7e9e7"
SOFT = "#f5f6f5"
ACCENT = "#225f49"
ACCENT_SOFT = "#eaf3ee"
WHITE = "#ffffff"

FONT_PATH = Path("C:/Windows/Fonts/msyh.ttc")
BOLD_FONT_PATH = Path("C:/Windows/Fonts/msyhbd.ttc")


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = BOLD_FONT_PATH if bold and BOLD_FONT_PATH.exists() else FONT_PATH
    return ImageFont.truetype(str(path), size=size)


F10 = font(10)
F13 = font(13)
F14 = font(14)
F16 = font(16)
F18 = font(18)
F22 = font(22, bold=True)
F28 = font(28, bold=True)
F38 = font(38, bold=True)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap(draw: ImageDraw.ImageDraw, text: str, target_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and draw.textlength(candidate, font=target_font) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def multiline(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, target_font: ImageFont.FreeTypeFont, fill: str, max_width: int, line_height: int) -> int:
    x, y = xy
    for paragraph in text.split("\n"):
        if not paragraph:
            y += line_height
            continue
        for line in wrap(draw, paragraph, target_font, max_width):
            draw.text((x, y), line, font=target_font, fill=fill)
            y += line_height
    return y


def base_frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)

    draw.line((0, 62, WIDTH, 62), fill=LINE, width=1)
    rounded(draw, (32, 16, 66, 50), 10, ACCENT)
    draw.text((43, 20), "厨", font=F18, fill=WHITE)
    draw.text((78, 23), "AI 私厨", font=F18, fill=INK)
    draw.ellipse((1127, 28, 1135, 36), fill="#45a174")
    draw.text((1144, 22), "服务在线", font=F13, fill=MUTED)

    rounded(draw, (260, 623, 1020, 685), 28, "#fafbfa", LINE)
    draw.text((286, 643), "+", font=F22, fill=MUTED)
    draw.text((974, 640), "↑", font=F22, fill=WHITE)
    draw.ellipse((958, 634, 1006, 682), fill=ACCENT)
    draw.text((970, 640), "↑", font=F22, fill=WHITE)
    draw.text((505, 694), "支持文字或图片 · 流式生成菜谱", font=F10, fill="#a0a6a2")
    return image, draw


def draw_empty(draw: ImageDraw.ImageDraw) -> None:
    rounded(draw, (598, 150, 682, 234), 27, WHITE, "#ccd1ce", 2)
    # A tiny chef-hat mark drawn as vectors, so the GIF does not depend on an
    # emoji font being available on the machine that regenerates it.
    draw.ellipse((619, 171, 641, 193), outline="#9ca39f", width=3)
    draw.ellipse((632, 164, 654, 190), outline="#9ca39f", width=3)
    draw.ellipse((647, 172, 667, 193), outline="#9ca39f", width=3)
    draw.line((620, 188, 620, 207, 666, 207, 666, 188), fill="#9ca39f", width=3)
    draw.line((630, 198, 656, 198), fill="#9ca39f", width=3)
    draw.text((554, 271), "AI PRIVATE CHEF", font=F13, fill="#9a9f9c")
    draw.text((466, 313), "今天想吃点什么？", font=F38, fill=INK)
    draw.text((456, 375), "描述现有食材，或者直接发一张照片。", font=F16, fill=MUTED)


def draw_user(draw: ImageDraw.ImageDraw) -> None:
    rounded(draw, (676, 104, 1030, 166), 20, SOFT)
    draw.text((698, 123), "我有番茄、鸡蛋和米饭，20 分钟能做什么？", font=F16, fill=INK)


def draw_assistant(draw: ImageDraw.ImageDraw, content: str, status: str, cursor: bool) -> None:
    rounded(draw, (246, 205, 286, 245), 11, ACCENT)
    draw.text((256, 213), "厨", font=F16, fill=WHITE)
    draw.text((305, 210), status, font=F14, fill=MUTED)

    y = multiline(draw, (305, 248), content, F16, "#24312b", 690, 30)
    if cursor:
        draw.rectangle((306, y + 3, 317, y + 25), fill=ACCENT)

    if "完成" in status:
        rounded(draw, (305, y + 14, 448, y + 43), 15, "#f7fbf8", "#dce8e1")
        draw.text((320, y + 20), "本地知识 · 无需联网", font=F10, fill=ACCENT)


def draw_composer_text(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.text((336, 644), text, font=F14, fill=INK)


def make_frames() -> tuple[list[Image.Image], list[int]]:
    frames: list[Image.Image] = []
    durations: list[int] = []

    image, draw = base_frame()
    draw_empty(draw)
    draw.text((336, 644), "输入食材或添加图片…", font=F14, fill="#a5aaa7")
    frames.append(image)
    durations.append(900)

    image, draw = base_frame()
    draw_empty(draw)
    draw_composer_text(draw, "我有番茄、鸡蛋和米饭，20 分钟能做什么？")
    frames.append(image)
    durations.append(850)

    image, draw = base_frame()
    draw_user(draw)
    draw_assistant(draw, "", "正在理解你的食材和时间要求…", True)
    frames.append(image)
    durations.append(700)

    stages = [
        "可以做一道简单下饭的番茄炒蛋盖饭。",
        "可以做一道简单下饭的番茄炒蛋盖饭。\n\n【番茄炒蛋盖饭】  约 18 分钟 · 1–2 人份",
        "可以做一道简单下饭的番茄炒蛋盖饭。\n\n【番茄炒蛋盖饭】  约 18 分钟 · 1–2 人份\n\n食材：番茄 2 个、鸡蛋 3 个、米饭 1 碗。",
        "可以做一道简单下饭的番茄炒蛋盖饭。\n\n【番茄炒蛋盖饭】  约 18 分钟 · 1–2 人份\n\n食材：番茄 2 个、鸡蛋 3 个、米饭 1 碗。\n\n1. 鸡蛋加少许盐打散，热锅快炒后盛出。",
        "可以做一道简单下饭的番茄炒蛋盖饭。\n\n【番茄炒蛋盖饭】  约 18 分钟 · 1–2 人份\n\n食材：番茄 2 个、鸡蛋 3 个、米饭 1 碗。\n\n1. 鸡蛋加少许盐打散，热锅快炒后盛出。\n2. 番茄炒软出汁，再放回鸡蛋翻匀。",
        "可以做一道简单下饭的番茄炒蛋盖饭。\n\n【番茄炒蛋盖饭】  约 18 分钟 · 1–2 人份\n\n食材：番茄 2 个、鸡蛋 3 个、米饭 1 碗。\n\n1. 鸡蛋加少许盐打散，热锅快炒后盛出。\n2. 番茄炒软出汁，再放回鸡蛋翻匀。\n3. 浇在热米饭上即可。",
    ]
    for index, text in enumerate(stages):
        image, draw = base_frame()
        draw_user(draw)
        draw_assistant(draw, text, "正在流式生成菜谱…", True)
        frames.append(image)
        durations.append(340 if index else 650)

    image, draw = base_frame()
    draw_user(draw)
    draw_assistant(draw, stages[-1], "推荐完成", False)
    frames.append(image)
    durations.append(2600)
    return frames, durations


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames, durations = make_frames()
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"generated {OUTPUT} ({OUTPUT.stat().st_size} bytes, {len(frames)} frames)")


if __name__ == "__main__":
    main()
