"""Generate public README images, GIF, and MP4 using example data only."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo"
W, H = 1280, 720
INK, MUTED, LINE = "#17251f", "#758079", "#e2e8e4"
SOFT, ACCENT, ACCENT_SOFT = "#f4f7f5", "#225f49", "#eaf3ee"
ORANGE, CREAM, WHITE = "#ef6a45", "#fbfaf5", "#ffffff"


def resolve_font(bold: bool = False) -> Path:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path(
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
            if bold
            else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        ),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    return next(path for path in candidates if path.exists())


FONT, FONT_BOLD = resolve_font(), resolve_font(True)


def f(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT), size=size)


def rr(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str,
    outline: str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
    width: int = W,
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (box[2] - box[0])) / 2, y), text, font=font, fill=fill)


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: str = ACCENT_SOFT,
    color: str = ACCENT,
) -> None:
    x, y = xy
    font = f(17)
    width = int(draw.textlength(text, font=font)) + 34
    rr(draw, (x, y, x + width, y + 38), 19, fill)
    draw.text((x + 17, y + 8), text, font=font, fill=color)


def wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int
) -> list[str]:
    lines, current = [], ""
    for char in text:
        if current and draw.textlength(current + char, font=font) > max_width:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines


def paragraph(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_height: int,
) -> int:
    x, y = xy
    for block in text.split("\n"):
        if not block:
            y += line_height
            continue
        for line in wrap(draw, block, font, max_width):
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height
    return y


def brand(draw: ImageDraw.ImageDraw, x: int = 52, y: int = 34, light: bool = False) -> None:
    rr(draw, (x, y, x + 46, y + 46), 13, WHITE if light else ACCENT)
    draw.text((x + 12, y + 8), "厨", font=f(23, True), fill=ACCENT if light else WHITE)
    draw.text((x + 60, y + 8), "AI 私厨", font=f(24, True), fill=WHITE if light else INK)


def food_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    """Stylized ingredient photo drawn locally without external assets."""
    x1, y1, x2, y2 = box
    rr(draw, box, 26, "#26332d")
    scale_x, scale_y = (x2 - x1) / 715, (y2 - y1) / 383

    def sx(value: int) -> int:
        return int(x1 + value * scale_x)

    def sy(value: int) -> int:
        return int(y1 + value * scale_y)

    draw.ellipse((sx(330), sy(38), sx(520), sy(220)), fill="#d9d3c4")
    draw.ellipse((sx(348), sy(56), sx(502), sy(202)), fill="#fffaf0")
    for cx, cy, radius in [(102, 103, 47), (192, 76, 42), (172, 158, 43)]:
        draw.ellipse(
            (sx(cx - radius), sy(cy - radius), sx(cx + radius), sy(cy + radius)), fill="#ef6046"
        )
        draw.polygon(
            [
                (sx(cx), sy(cy - radius - 4)),
                (sx(cx - 12), sy(cy - radius + 13)),
                (sx(cx + 13), sy(cy - radius + 13)),
            ],
            fill="#4b8d5f",
        )
    for cx, cy in [(103, 260), (185, 250), (147, 321)]:
        draw.ellipse((sx(cx - 31), sy(cy - 39), sx(cx + 31), sy(cy + 39)), fill="#d8a76e")
    for offset in range(0, 45, 9):
        draw.line(
            (sx(305 + offset), sy(345), sx(456 + offset), sy(230)),
            fill="#4fa06b",
            width=max(3, int(7 * scale_x)),
        )
        draw.line(
            (sx(299 + offset), sy(349), sx(319 + offset), sy(333)),
            fill="#f3eee1",
            width=max(4, int(9 * scale_x)),
        )
    pill(draw, (x1 + 20, y2 - 55), "示例食材图片", WHITE, ACCENT)


def node(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    title: str,
    subtitle: str,
    active: bool = False,
    width: int = 225,
) -> None:
    x, y = center
    fill = ACCENT if active else WHITE
    rr(
        draw,
        (x - width // 2, y - 62, x + width // 2, y + 62),
        22,
        fill,
        ACCENT if active else LINE,
        2,
    )
    title_box = draw.textbbox((0, 0), title, font=f(22, True))
    draw.text(
        (x - (title_box[2] - title_box[0]) / 2, y - 35),
        title,
        font=f(22, True),
        fill=WHITE if active else INK,
    )
    sub_box = draw.textbbox((0, 0), subtitle, font=f(13))
    draw.text(
        (x - (sub_box[2] - sub_box[0]) / 2, y + 8),
        subtitle,
        font=f(13),
        fill="#dcebe4" if active else MUTED,
    )


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    draw.line((*start, *end), fill="#aebbb4", width=4)
    x, y = end
    draw.polygon([(x, y), (x - 14, y - 8), (x - 14, y + 8)], fill="#aebbb4")


def make_overview() -> Image.Image:
    image = Image.new("RGB", (1600, 900), CREAM)
    draw = ImageDraw.Draw(image)
    brand(draw, 68, 55)
    draw.text((72, 175), "一张图，一句话，", font=f(57, True), fill=INK)
    draw.text((72, 245), "生成适合当下的家常菜。", font=f(57, True), fill=ACCENT)
    paragraph(
        draw,
        "支持文字与图片输入，自动识别食材，按需调用 Tavily，\n并通过流式输出返回可执行的菜谱。",
        (76, 350),
        f(23),
        MUTED,
        600,
        40,
    )
    pill(draw, (76, 476), "Qwen 多模态")
    pill(draw, (255, 476), "LangGraph Agent")
    pill(draw, (469, 476), "NDJSON 流式输出")
    rr(draw, (76, 570, 650, 775), 28, WHITE, LINE)
    draw.text((110, 605), "识别结果", font=f(18, True), fill=ACCENT)
    for index, (name, detail, score) in enumerate(
        [("番茄", "2 个 · 新鲜", "98%"), ("鸡蛋", "3 个 · 完整", "97%"), ("米饭", "约 1 碗", "96%")]
    ):
        y = 652 + index * 44
        draw.text((110, y), name, font=f(19, True), fill=INK)
        draw.text((210, y + 2), detail, font=f(15), fill=MUTED)
        draw.text((555, y), score, font=f(16, True), fill=ACCENT)
    rr(draw, (725, 90, 1530, 825), 38, WHITE, LINE)
    draw.text((770, 126), "图片输入", font=f(18, True), fill=ACCENT)
    food_panel(draw, (770, 172, 1485, 555))
    rr(draw, (820, 600, 1485, 760), 25, SOFT)
    draw.text((850, 625), "我手头有这些食材，20 分钟能做什么？", font=f(21), fill=INK)
    draw.text((850, 683), "正在流式生成：番茄炒蛋盖饭…", font=f(20, True), fill=ACCENT)
    draw.rectangle((1332, 684, 1343, 712), fill=ACCENT)
    return image


def make_architecture() -> Image.Image:
    image = Image.new("RGB", (1600, 900), "#f7f9f8")
    draw = ImageDraw.Draw(image)
    draw.text((70, 55), "Agent 工作流与数据链路", font=f(45, True), fill=INK)
    draw.text(
        (72, 116), "每一步都可追踪、可降级，并通过 thread_id 隔离会话状态。", font=f(20), fill=MUTED
    )
    centers = [(165, 310), (455, 310), (745, 310), (1035, 310), (1325, 310)]
    labels = [
        ("文字 / 图片", "统一输入框"),
        ("食材识别", "OSS + Qwen Vision"),
        ("工具决策", "LangGraph 路由"),
        ("Tavily 搜索", "仅在需要时调用"),
        ("菜谱生成", "Qwen 流式输出"),
    ]
    for index, (center, label) in enumerate(zip(centers, labels, strict=True)):
        node(draw, center, *label, active=index in {1, 2, 4})
        if index < len(centers) - 1:
            arrow(draw, (center[0] + 114, center[1]), (centers[index + 1][0] - 126, center[1]))
    rr(draw, (165, 500, 1435, 780), 32, WHITE, LINE)
    draw.text((210, 535), "运行基础设施", font=f(25, True), fill=INK)
    infra = [
        ("FastAPI", "上传、校验、NDJSON 流"),
        ("PostgreSQL", "Checkpoint 与多轮会话"),
        ("LangSmith", "节点、工具原因、耗时、错误"),
        ("Docker Compose", "应用与数据库编排"),
    ]
    for index, (title, body) in enumerate(infra):
        x = 215 + index * 300
        rr(draw, (x, 605, x + 255, 735), 20, SOFT)
        draw.text((x + 22, 628), title, font=f(21, True), fill=ACCENT)
        paragraph(draw, body, (x + 22, 670), f(14), MUTED, 210, 23)
    return image


def make_observability() -> Image.Image:
    image = Image.new("RGB", (1600, 900), "#eef4f1")
    draw = ImageDraw.Draw(image)
    draw.text((68, 55), "可观测、可解释、可持久化", font=f(45, True), fill=INK)
    draw.text(
        (70, 116),
        "不只展示结果，还能回答：为什么搜索？经过了哪些节点？状态保存在哪里？",
        font=f(20),
        fill=MUTED,
    )
    rr(draw, (70, 185, 985, 825), 32, WHITE, LINE)
    draw.text((110, 220), "LangSmith Studio / Trace", font=f(25, True), fill=ACCENT)
    graph_nodes = [
        ((525, 315), "prepare_request"),
        ((525, 425), "recognize_image"),
        ((525, 535), "decide_tool"),
        ((335, 660), "search_web"),
        ((710, 660), "generate_recipe"),
    ]
    for index, (center, title) in enumerate(graph_nodes):
        node(
            draw,
            center,
            title,
            "节点输入 / 输出 / 耗时",
            active=title in {"recognize_image", "decide_tool", "generate_recipe"},
            width=270,
        )
        if index < 2:
            next_center = graph_nodes[index + 1][0]
            arrow(draw, (center[0], center[1] + 64), (next_center[0], next_center[1] - 72))
    arrow(draw, (500, 598), (390, 600))
    arrow(draw, (550, 598), (655, 600))
    rr(draw, (1030, 185, 1530, 825), 32, WHITE, LINE)
    draw.text((1070, 225), "本机只读后台", font=f(25, True), fill=INK)
    for index, (label, value) in enumerate(
        [("会话数量", "8"), ("Checkpoint", "101"), ("存储后端", "PostgreSQL")]
    ):
        y = 300 + index * 135
        rr(draw, (1070, y, 1490, y + 105), 20, SOFT)
        draw.text((1095, y + 18), label, font=f(15), fill=MUTED)
        draw.text((1095, y + 50), value, font=f(29, True), fill=ACCENT)
    pill(draw, (1070, 720), "隐私保护：签名 URL 不持久化")
    return image


def chat_frame(stage: int, progress: float = 1.0) -> Image.Image:
    image = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(image)
    brand(draw, 34, 17)
    draw.line((0, 72, W, 72), fill=LINE, width=1)
    draw.ellipse((1128, 32, 1138, 42), fill="#45a174")
    draw.text((1148, 25), "服务在线", font=f(14), fill=MUTED)
    rr(draw, (250, 630, 1030, 694), 28, "#fafbfa", LINE)
    draw.text((278, 646), "+", font=f(24), fill=MUTED)
    draw.ellipse((968, 638, 1016, 686), fill=ACCENT)
    draw.text((982, 644), "↑", font=f(22, True), fill=WHITE)
    if stage == 0:
        centered(draw, "AI PRIVATE CHEF", 214, f(14, True), "#9a9f9c")
        centered(draw, "今天想吃点什么？", 262, f(43, True), INK)
        centered(draw, "描述现有食材，或者直接发一张照片。", 332, f(18), MUTED)
        draw.text((326, 649), "输入食材或添加图片…", font=f(15), fill="#a5aaa7")
    elif stage == 1:
        rr(draw, (740, 102, 1050, 330), 25, SOFT)
        food_panel(draw, (770, 126, 1020, 290))
        draw.text((758, 352), "这些食材能做什么？", font=f(17), fill=INK)
        rr(draw, (225, 130, 650, 510), 26, WHITE, LINE)
        draw.text((260, 165), "食材识别", font=f(20, True), fill=ACCENT)
        items = [("番茄", "98%"), ("鸡蛋", "97%"), ("米饭", "96%")]
        for index, (name, score) in enumerate(items[: max(1, int(progress * len(items) + 0.99))]):
            y = 225 + index * 80
            rr(draw, (260, y, 610, y + 58), 16, ACCENT_SOFT)
            draw.text((285, y + 14), name, font=f(18, True), fill=INK)
            draw.text((540, y + 15), score, font=f(16, True), fill=ACCENT)
    elif stage == 2:
        draw.text((75, 105), "LangGraph 正在选择下一步", font=f(27, True), fill=INK)
        steps = [(185, "prepare"), (440, "recognize"), (695, "decide_tool"), (950, "generate")]
        active_index = min(len(steps) - 1, int(progress * len(steps)))
        for index, (x, title) in enumerate(steps):
            node(draw, (x, 285), title, "state → node", active=index <= active_index, width=190)
            if index < len(steps) - 1:
                arrow(draw, (x + 98, 285), (steps[index + 1][0] - 108, 285))
        rr(draw, (310, 420, 970, 555), 24, SOFT)
        draw.text((345, 450), "工具决策：无需联网", font=f(24, True), fill=ACCENT)
        draw.text(
            (345, 495), "常规家常菜可由模型内部知识完成，跳过 Tavily。", font=f(17), fill=MUTED
        )
    elif stage == 3:
        rr(draw, (720, 95, 1050, 155), 20, SOFT)
        draw.text((745, 113), "我有番茄、鸡蛋和米饭，20 分钟能做什么？", font=f(15), fill=INK)
        rr(draw, (225, 190, 267, 232), 12, ACCENT)
        draw.text((236, 199), "厨", font=f(17), fill=WHITE)
        draw.text((285, 196), "正在流式生成菜谱…", font=f(14), fill=MUTED)
        full = (
            "番茄炒蛋盖饭 · 约 18 分钟 · 1–2 人份\n\n"
            "食材：番茄 2 个、鸡蛋 3 个、米饭 1 碗。\n\n"
            "1. 鸡蛋加盐打散，热锅快炒后盛出。\n"
            "2. 番茄炒软出汁，再放回鸡蛋翻匀。\n"
            "3. 浇在热米饭上即可。"
        )
        shown = full[: max(1, int(len(full) * progress))]
        y = paragraph(draw, shown, (285, 240), f(18), "#24312b", 720, 32)
        draw.rectangle((286, y + 2, 298, y + 29), fill=ACCENT)
    return image


def title_frame(title: str, subtitle: str, progress: float = 1.0) -> Image.Image:
    image = Image.new("RGB", (W, H), ACCENT)
    draw = ImageDraw.Draw(image)
    brand(draw, 58, 48, light=True)
    draw.text((84, 236), title, font=f(54, True), fill=WHITE)
    draw.text((86, 316), subtitle, font=f(23), fill="#dcebe4")
    for index, text in enumerate(["图片食材识别", "按需 Tavily", "流式菜谱", "LangSmith 可观测"]):
        if index / 4 <= progress:
            pill(draw, (86 + index * 270, 424), text, WHITE, ACCENT)
    draw.text((86, 620), "示例数据演示 · 不包含真实用户信息", font=f(15), fill="#bcd2c7")
    return image


def build_gif() -> None:
    frames = [chat_frame(0), chat_frame(1), chat_frame(2)] + [
        chat_frame(3, p) for p in (0.15, 0.32, 0.5, 0.68, 0.84, 1.0)
    ]
    frames[0].save(
        OUT / "ai-private-chef-demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=[1000, 1300, 1300, 350, 350, 350, 350, 350, 2600],
        loop=0,
        optimize=True,
        disposal=2,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_overview().save(OUT / "product-overview.png", optimize=True)
    make_architecture().save(OUT / "architecture.png", optimize=True)
    make_observability().save(OUT / "observability.png", optimize=True)
    build_gif()
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            print(f"generated {path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
