# -*- coding: utf-8 -*-
"""
终末地 · 电池配比计算器
=========================================
主题切换版（tkinter，无需第三方依赖）
    默认「黄灰」主题，右上角可切换「白蓝」「黄紫」

打包成单文件 exe（resource 文件夹里是电池图片和 logo，必须一起打包）：
    python -m PyInstaller --noconfirm endfield_battery.spec
    （项目里的 build_exe.bat 已经这么做，双击即可）

界面说明：
    左侧选择电池种类（下拉框带图片，发电量自动带入）、填写「系统总耗电」，
    用滑轨选择电池获取速率（6 ~ 30 个/分钟，步进 6），点击「开始计算」
    即可得到配比方案。

关闭行为：
    点关闭按钮会让你选择「退出应用 / 最小化到任务栏 / 取消」。
    勾选「本次运行不再提示」后，本次运行期间关闭会直接执行该选择，
    但选择只保存在内存里，程序重启后会自动恢复为每次询问。
"""

import base64
import math
import os
import struct
import sys
import tkinter as tk
import zlib
from collections import Counter
from tkinter import font as tkfont
from tkinter import ttk

# ================================================================= 配色主题
# 命名约定：表面色 + 强调色，例如「黄灰」= 灰表面 + 黄强调
THEMES = {
    "黄灰": {
        "BG": "#1E1E1E", "PANEL": "#2A2A2A", "PANEL_HI": "#363636",
        "ROW_SEL": "#3C3300", "INPUT_BG": "#242424", "BORDER": "#4A4A4A",
        "TRACK": "#5A5A5A",
        "ACCENT": "#FFD400", "ACCENT_HI": "#FFE45C", "ACCENT_DIM": "#9A8000",
        "ON_ACCENT": "#141414", "HINT_ON_ACCENT": "#000000",
        "TEXT": "#F2F2F2", "MUTED": "#A8A8A8",
        "AMBER": "#FFB020", "DANGER": "#FF6B6B", "PLACEHOLDER": "#6E6E6E",
        "TITLEBAR": "#1E1E1E", "TITLEBAR_TEXT": "#F2F2F2", "DARK_TITLEBAR": True,
    },
    "白蓝": {
        "BG": "#EDF1F7", "PANEL": "#FFFFFF", "PANEL_HI": "#E4EBF5",
        "ROW_SEL": "#D9E8FB", "INPUT_BG": "#F7FAFD", "BORDER": "#CDD9E8",
        "TRACK": "#C0CEDF",
        "ACCENT": "#1E6FD9", "ACCENT_HI": "#3D8BE8", "ACCENT_DIM": "#9CBEE8",
        "ON_ACCENT": "#FFFFFF", "HINT_ON_ACCENT": "#EAF2FF",
        "TEXT": "#1B2733", "MUTED": "#6C7C8F",
        "AMBER": "#B87300", "DANGER": "#D24040", "PLACEHOLDER": "#9AA8B8",
        "TITLEBAR": "#EDF1F7", "TITLEBAR_TEXT": "#1B2733", "DARK_TITLEBAR": False,
    },
    "黄紫": {
        "BG": "#191223", "PANEL": "#241A33", "PANEL_HI": "#322246",
        "ROW_SEL": "#3E3206", "INPUT_BG": "#1E1730", "BORDER": "#41335C",
        "TRACK": "#4E3E6E",
        "ACCENT": "#FFD400", "ACCENT_HI": "#FFE45C", "ACCENT_DIM": "#8A7200",
        "ON_ACCENT": "#191223", "HINT_ON_ACCENT": "#000000",
        "TEXT": "#F1ECFA", "MUTED": "#A79BC0",
        "AMBER": "#FFB020", "DANGER": "#FF6B6B", "PLACEHOLDER": "#6B5F85",
        "TITLEBAR": "#191223", "TITLEBAR_TEXT": "#F1ECFA", "DARK_TITLEBAR": True,
    },
}
THEME_KEYS = ["黄灰", "白蓝", "黄紫"]
THEME_LABELS = {"黄灰": "黄灰主题", "白蓝": "白蓝主题", "黄紫": "黄紫主题"}
DEFAULT_THEME = "黄灰"

# 圆角半径（设计像素，实际按 DPI 缩放）
R_PANEL = 32
R_FIELD = 22
R_BUTTON = 26
R_POPUP = 26
R_SEG = 20

# 窗口左右留白（设计像素）
SIDE_MARGIN = 36


def apply_theme(name):
    """切换到指定主题：就地刷新模块级调色板（控件在创建时读取）"""
    globals().update(THEMES[name])
    # 只有放大查看窗口的窗体底色跟主题走；蓝图纸面与网格保持游戏里那种浅灰
    globals().update({"BP_WIN": THEMES[name]["BG"]})


apply_theme(DEFAULT_THEME)

FONT_UI = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

RATE_VALUES = [6, 12, 18, 24, 30]   # 个/分钟

# 电池种类（发电量单位：每秒）
BATTERIES = [
    {"name": "谷底低容电池", "power": 220,  "file": "gudi_low.png"},
    {"name": "谷底中容电池", "power": 420,  "file": "gudi_mid.png"},
    {"name": "谷底高容电池", "power": 1100, "file": "gudi_high.png"},
    {"name": "武陵低容电池", "power": 1600, "file": "wuling_low.png"},
    {"name": "武陵中容电池", "power": 3200, "file": "wuling_mid.png"},
]

# 搭建演示用的元件图（文件, 名称, 显示档位）
#   档位 big = 大方块/宽图，small = 传送带那种小图标
BUILD_TILES = [
    ("build_gate_gudi_low.png",    "物品准入口", "big"),
    ("build_gate_gudi_mid.png",    "物品准入口", "big"),
    ("build_gate_gudi_high.png",   "物品准入口", "big"),
    ("build_gate_wuling_low.png",  "物品准入口", "big"),
    ("build_gate_wuling_mid.png",  "物品准入口", "big"),
    ("build_pickup.png",   "仓库取货口", "big"),
    ("build_deposit.png",  "仓库存货口", "big"),
    ("build_thermal.png",  "热能池",     "big"),
    ("build_splitter.png", "分流器",     "big"),
    ("build_merger.png",   "汇流器",     "big"),
    ("build_belt.png",     "传送带",     "small"),
    ("build_corner.png",   "传送带拐角", "small"),
    ("build_bridge.png",   "物流桥",     "big"),
]

# 蓝图配色（保持游戏里那种浅灰方格，不随主题变）
BP_PAGE = "#F1F1F1"
BP_LINE = "#D6D6D6"
BP_TEXT = "#2B2B2B"
BP_SUB = "#6A6A6A"
BP_LABEL = "#FFFFFF"


def blueprint_files():
    """网格蓝图会用到的所有元件图"""
    names = ["build_pickup.png", "build_deposit.png", "build_thermal.png",
             "build_thermal_big.png", "build_bridge.png"]
    for base in ("build_belt", "build_corner", "build_splitter", "build_merger"):
        names += [f"{base}_{i}.png" for i in range(4)]
    names += [f"build_corner_m{i}.png" for i in range(4)]
    # 物品准入口：五种电池各一张
    names += ["build_gate_%s" % b["file"] for b in BATTERIES]
    return names


def enable_dpi_awareness():
    """Windows 高分屏下避免界面被拉伸模糊"""
    if not sys.platform.startswith("win"):
        return
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def resource_dir():
    """
    定位 resource 目录，按优先级依次尝试：
        1. 打包进 exe 的临时目录（--add-data 打进去的）
        2. exe 同目录 / onedir 模式的 _internal
        3. exe 所在目录的上一级（例如 exe 在 dist 里，resource 在项目根目录）
        4. 源码运行时的脚本目录
    """
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if meipass:
            candidates.append(meipass)
        candidates.append(exe_dir)
        candidates.append(os.path.join(exe_dir, "_internal"))
        candidates.append(os.path.dirname(exe_dir))
    else:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))

    probe = BATTERIES[0]["file"]
    for base in candidates:
        path = os.path.join(base, "resource")
        if os.path.isfile(os.path.join(path, probe)):
            return path
    return os.path.join(candidates[0], "resource")


def hide_console_window():
    """万一被打包成带控制台的 exe，启动后把黑框隐藏掉"""
    if not getattr(sys, "frozen", False) or not sys.platform.startswith("win"):
        return
    try:
        from ctypes import windll
        hwnd = windll.kernel32.GetConsoleWindow()
        if hwnd:
            windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def install_crash_dialog():
    """打包后没有控制台时，未捕获异常弹窗提示，避免程序静默消失"""
    if not getattr(sys, "frozen", False):
        return

    def hook(exc_type, exc_value, exc_tb):
        import traceback
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            from ctypes import windll
            windll.user32.MessageBoxW(None, text[-1800:],
                                      "终末地电池配比计算器 · 运行出错", 0x10)
        except Exception:
            pass

    sys.excepthook = hook


def colorref(hex_color: str) -> int:
    """#RRGGBB -> Windows COLORREF（0x00BBGGRR）"""
    value = hex_color.lstrip("#")
    red, green, blue = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def apply_titlebar_color(window):
    """把窗口标题栏改成当前主题的配色（Windows 10/11）"""
    if not sys.platform.startswith("win"):
        return
    try:
        from ctypes import byref, c_int, sizeof, windll
        window.update_idletasks()
        hwnd = windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        dark = c_int(1 if DARK_TITLEBAR else 0)
        for attr in (20, 19):
            windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, byref(dark), sizeof(dark))
        caption = c_int(colorref(TITLEBAR))
        windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption), sizeof(caption))
        text = c_int(colorref(TITLEBAR_TEXT))
        windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, byref(text), sizeof(text))
    except Exception:
        pass


# ================================================================= 圆角绘制工具
def _rgb(hex_color):
    return (int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))


def _png_bytes(width, height, rows):
    """把 RGBA 像素行编码成 PNG 字节（不依赖 Pillow）"""
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


_CORNER_CACHE = {}

# 4×4 Bayer 抖动矩阵：弹窗只有“整像素透明”，靠抖动来模拟半透明边缘
_BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def corner_photo(radius, fill, outline, page_bg, corner, dither=False):
    """
    生成 radius×radius 的抗锯齿圆角贴图（四分之一圆），
    让圆角边缘平滑而不是锯齿状的“马赛克”。
    dither=True 时用抖动近似半透明（弹窗只有整像素透明可用）。
    """
    key = (radius, fill, outline, page_bg, corner, dither)
    photo = _CORNER_CACHE.get(key)
    if photo is not None:
        return photo

    fr, fg, fb = _rgb(fill)
    orr, og, ob = _rgb(outline)
    br, bg, bb = _rgb(page_bg)
    left = corner in ("tl", "bl")
    top = corner in ("tl", "tr")
    border = 1.25

    rows = []
    for j in range(radius):
        row = bytearray()
        for i in range(radius):
            dx = (radius - (i + 0.5)) if left else (i + 0.5)
            dy = (radius - (j + 0.5)) if top else (j + 0.5)
            d = math.hypot(dx, dy)
            cover = min(max(radius - d + 0.5, 0.0), 1.0)
            inner = min(max(radius - border - d + 0.5, 0.0), 1.0)
            if dither:
                threshold = (_BAYER4[j % 4][i % 4] + 0.5) / 16.0
                if cover <= threshold:
                    row += bytes((br, bg, bb, 255))          # 透出画布底色 -> 透明
                elif inner < 0.5:
                    row += bytes((orr, og, ob, 255))
                else:
                    row += bytes((fr, fg, fb, 255))
                continue
            r = orr + (fr - orr) * inner
            g = og + (fg - og) * inner
            b = ob + (fb - ob) * inner
            r = br + (r - br) * cover
            g = bg + (g - bg) * cover
            b = bb + (b - bb) * cover
            row += bytes((int(r + 0.5), int(g + 0.5), int(b + 0.5), 255))
        rows.append(row)

    photo = tk.PhotoImage(data=base64.b64encode(_png_bytes(radius, radius, rows)))
    _CORNER_CACHE[key] = photo
    return photo


def draw_round_panel(canvas, width, height, radius, fill, outline, page_bg,
                     tags=("__fill__", "__border__", "__corner__"),
                     lower_fill=True, dither=False):
    """在画布上画一个抗锯齿圆角面板（直线段 + 四角贴图）"""
    tag_fill, tag_border, tag_corner = tags
    width = max(int(width), 2)
    height = max(int(height), 2)
    radius = max(2, min(int(radius), width // 2, height // 2))

    canvas.delete(tag_fill)
    canvas.delete(tag_border)
    canvas.delete(tag_corner)

    canvas.create_rectangle(0, 0, width, height, fill=fill, outline="",
                            tags=tag_fill)
    if lower_fill:
        canvas.tag_lower(tag_fill)
    else:
        canvas.tag_raise(tag_fill)

    if outline and outline != fill:
        # 描边用 1 像素宽的矩形而不是直线：直线的取整方式会让右边和下边画到画布外
        for x1, y1, x2, y2 in ((radius, 0, width - radius, 1),
                               (radius, height - 1, width - radius, height),
                               (0, radius, 1, height - radius),
                               (width - 1, radius, width, height - radius)):
            canvas.create_rectangle(x1, y1, x2, y2, fill=outline, outline="",
                                    tags=tag_border)

    positions = {"tl": (0, 0), "tr": (width - radius, 0),
                 "bl": (0, height - radius), "br": (width - radius, height - radius)}
    for corner, (x, y) in positions.items():
        photo = corner_photo(radius, fill, outline or fill, page_bg, corner, dither)
        canvas.create_image(x, y, anchor="nw", image=photo, tags=tag_corner)


class RoundedBox(tk.Canvas):
    """圆角面板：内容放进 self.body"""

    def __init__(self, master, px, radius=R_PANEL, fill=PANEL, outline=BORDER,
                 page_bg=BG, inner_pad=1, autosize=False, **kw):
        super().__init__(master, bg=page_bg, highlightthickness=0, bd=0, **kw)
        self.px = px
        self.radius = px(radius)
        self.fill = fill
        self.outline = outline
        self.page_bg = page_bg
        # Tk 里嵌入窗口永远画在画布图形之上，所以内容框必须内缩到圆角曲线以内，
        # 否则它会用直角把圆角盖掉（0.293R 是圆角曲线与对角线的交点）
        self.inner_pad = max(px(inner_pad), int(math.ceil(self.radius * 0.30)) + 1)
        self._req = (0, 0)

        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(self.inner_pad, self.inner_pad,
                                       anchor="nw", window=self.body)
        self.bind("<Configure>", self._redraw)
        if autosize:
            self.body.bind("<Configure>", self._fit)

    def _redraw(self, event=None):
        width = event.width if event else self.winfo_width()
        height = event.height if event else self.winfo_height()
        pad = self.inner_pad
        self.coords(self._win, pad, pad)
        self.itemconfigure(self._win, width=max(width - 2 * pad, 1),
                           height=max(height - 2 * pad, 1))
        draw_round_panel(self, width, height, self.radius, self.fill,
                         self.outline, self.page_bg)

    def _fit(self, event=None):
        width = self.body.winfo_reqwidth() + 2 * self.inner_pad
        height = self.body.winfo_reqheight() + 2 * self.inner_pad
        if (width, height) != self._req:
            self._req = (width, height)
            self.configure(width=width, height=height)

    def set_outline(self, color):
        self.outline = color
        self._redraw()


class RoundedButton(tk.Canvas):
    """圆角按钮；可在右下角放一个小提示（例如 Enter 计算）"""

    def __init__(self, master, text, command, px, font, fill, fg, hover,
                 page_bg=BG, radius=R_BUTTON, height=56, width=160,
                 hint=None, hint_fg="#000000", hint_font=None,
                 outline=None, outline_width=1, **kw):
        super().__init__(master, bg=page_bg, highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=True, **kw)
        self.px = px
        self.text = text
        self.command = command
        self.fill = fill
        self.fg = fg
        self.hover = hover
        self.radius = px(radius)
        self.hint = hint
        self.hint_fg = hint_fg
        self.hint_font = hint_font
        self.font = font
        self.outline = outline
        self.outline_width = outline_width
        self.page_bg = page_bg
        self._hovered = False
        self._pressed = False

        self.configure(width=px(width), height=px(height))
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self._press())
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)

    def _activate(self, event=None):
        self.command()
        return "break"

    def _set_hover(self, hovered):
        self._hovered = hovered
        self._redraw()

    def _press(self):
        self._pressed = True
        self.focus_set()
        self._redraw()

    def _release(self, event):
        if self._pressed:
            self._pressed = False
            self._redraw()
            if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
                self.command()

    def _redraw(self):
        width, height = self.winfo_width(), self.winfo_height()
        if width <= 1:
            return
        self.delete("all")
        fill = self.hover if (self._hovered or self._pressed) else self.fill
        draw_round_panel(self, width, height, self.radius, fill,
                         self.outline or fill, self.page_bg)
        if self.hint:
            self.create_text(width / 2, height / 2, text=self.text,
                             fill=self.fg, font=self.font)
            self.create_text(width - self.px(8), height - self.px(4),
                             text=self.hint, fill=self.hint_fg,
                             font=self.hint_font, anchor="se")
        else:
            self.create_text(width / 2, height / 2, text=self.text,
                             fill=self.fg, font=self.font)


class Segmented(tk.Canvas):
    """圆角分段选择器（简单模式 / 精确模式）"""

    def __init__(self, master, options, value, command, px, font,
                 page_bg=PANEL, radius=R_SEG, height=44, **kw):
        super().__init__(master, bg=page_bg, highlightthickness=0, bd=0, **kw)
        self.options = list(options)
        self.value = value
        self.command = command
        self.px = px
        self.font = font
        self.radius = px(radius)
        self.configure(height=px(height), cursor="hand2")
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Button-1>", self._click)

    def set_value(self, value):
        self.value = value
        self._redraw()

    def _redraw(self):
        width, height = self.winfo_width(), self.winfo_height()
        if width <= 1:
            return
        self.delete("all")
        draw_round_panel(self, width, height, self.radius, PANEL_HI, BORDER, PANEL)
        count = len(self.options)
        seg = (width - 2) / count
        for index, (key, label) in enumerate(self.options):
            x1 = 1 + index * seg
            x2 = x1 + seg
            if key == self.value:
                draw_round_panel(self, int(x2 - x1 - self.px(6)),
                                 height - self.px(6), self.radius - self.px(2),
                                 ACCENT, ACCENT, PANEL_HI,
                                 tags=("__sfill__", "__sborder__", "__scorner__"),
                                 lower_fill=False)
                # 把高亮块挪到对应位置
                for tag in ("__sfill__", "__sborder__", "__scorner__"):
                    self.move(tag, x1 + self.px(3), self.px(3))
                fg = ON_ACCENT
            else:
                fg = MUTED
            self.create_text((x1 + x2) / 2, height / 2, text=label, fill=fg,
                             font=self.font)

    def _click(self, event):
        count = len(self.options)
        seg = (self.winfo_width() - 2) / count
        index = min(int(event.x / seg), count - 1)
        key = self.options[index][0]
        if key != self.value:
            self.set_value(key)
            self.command(key)


# ================================================================= 计算核心
def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    limit = int(math.isqrt(n))
    i = 5
    while i <= limit:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def smallest_prime_factor(n: int) -> int:
    if n % 2 == 0:
        return 2
    p = 3
    while p * p <= n:
        if n % p == 0:
            return p
        p += 2
    return n


def prime_factorization(n: int) -> Counter:
    """标准质因数分解，返回 Counter {质数: 指数}"""
    factors = Counter()
    temp = n
    while temp % 2 == 0:
        factors[2] += 1
        temp //= 2
    p = 3
    while p * p <= temp:
        while temp % p == 0:
            factors[p] += 1
            temp //= p
        p += 2
    if temp > 1:
        factors[temp] += 1
    return factors


def recursive_decompose(n: int) -> Counter:
    """
    对 n 执行特殊分解（质数>3则加1后继续，合数则除以最小质因子），
    返回所有出现的质数及其次数。
    """
    factors = Counter()
    cur = n
    while cur > 1:
        if is_prime(cur):
            factors[cur] += 1
            if cur > 3:
                cur += 1
            else:
                break
        else:
            p = smallest_prime_factor(cur)
            factors[p] += 1
            cur //= p
    return factors


def decompose_target(n: int):
    """精确模式的分解：返回 (total: Counter, rules: {质数: Counter})
    total 直接就是 n 的质因数 —— 质数分流器内部怎么搭写在 rules 里，
    不能再把它内部的 2 分/3 分重复算成额外的分流器。"""
    base = prime_factorization(n)
    total = Counter(base)
    rules = {}
    for p in base:
        if p > 3:
            rules[p] = prime_factorization(p + 1)
    return total, rules


def format_output_lines(n: int):
    """原 format_output 的图形界面版本，返回 [(文本, 标签), ...]"""
    total, rules = decompose_target(n)

    big_primes = sorted([p for p in total if p > 3], reverse=True)
    parts = [f"{total[p]}个{p}分" for p in big_primes]
    if total.get(2, 0):
        parts.append(f"{total[2]}个2分")
    if total.get(3, 0):
        parts.append(f"{total[3]}个3分")

    lines = []
    if len(parts) == 1:
        lines.append(("需要" + parts[0], "body"))
    elif parts:
        lines.append(("需要" + "、".join(parts[:-1]) + "和" + parts[-1], "body"))

    sorted_rules = sorted(rules.keys(), reverse=True)
    for idx, p in enumerate(sorted_rules):
        decomp = rules[p]
        sub_parts = [f"{decomp[q]}个{q}分" for q in sorted(decomp.keys())]
        if len(sub_parts) == 1:
            rule_str = f"{p}分可以视为{p + 1}分，即" + sub_parts[0]
        else:
            rule_str = (f"{p}分可以视为{p + 1}分，即"
                        + "、".join(sub_parts[:-1]) + "和" + sub_parts[-1])
        lines.append((("其中" if idx == 0 else "    ") + rule_str,
                      "body" if idx == 0 else "muted"))
    return lines


def fmt_num(x) -> str:
    """数字美化：整数不显示小数点，小数保留两位"""
    if isinstance(x, float) and abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def calculate(total_power: float, battery_output: float, rate_per_min: int, precise_mode: bool):
    """完整计算流程，返回 (结果行列表, 概要文本或 None, 搭建信息 dict 或 None)"""
    lines = []

    consume = total_power - 200.0
    if consume <= 0:
        lines.append(("系统总耗电不高于系统自带的 200，无需使用电池。", "warn"))
        return lines, None, None
    if battery_output <= 0:
        lines.append(("单电池发电量必须大于 0。", "error"))
        return lines, None, None

    number = 0
    while number * battery_output < consume:
        number += 1

    model = 60.0 / rate_per_min
    gap = consume - (number - 1) * battery_output      # 掉电期间每秒的净耗电量

    time_sec = int(40 * battery_output // gap)         # 理论间隔时间（秒）
    total = int(3600 // time_sec + 90 * (number - 1))
    deadline = int(100000 // gap) + 40                 # 耗尽时间（秒）

    lines.append((f"需要 {number} 个电池", "big"))

    # ---- ① 间隔时间不到电池的 40 秒发电时间：改用 40 秒 ----
    interval = time_sec
    if interval <= 40:
        interval = 40
        lines.append((f"由于计算所得实际间隔时间 {time_sec} 秒小于或等于 40 秒，"
                      "而电池的发电时间为 40 秒，故将间隔时间改为 40 秒。", "warn"))

    # ---- ② 系统电量会先耗尽：改用耗尽时间 ----
    if deadline < interval:
        interval = deadline
        lines.append((f"由于系统内电量耗尽时热能池仍未获得电池，"
                      f"将间隔时间改为耗尽时间 {deadline} 秒。", "warn"))

    # ---- ③ 间隔时间按电池获取速率换算成“比例” ----
    ratio_target = interval * rate_per_min / 60.0
    lines.append((f"应每隔 {interval} 秒使用一次电池，"
                  f"按 {rate_per_min} 个/分钟换算的比例为 {int(ratio_target)}。", "body"))

    if precise_mode:
        ratio = max(int(ratio_target), 1)
        build_interval = interval          # 搭建演示里显示的目标间隔

        def _ok(n):
            """是否可接受：只看质数分解层数（层数过多时实际意义较小）"""
            return n >= 2 and _ratio_depth(n) <= MAX_DEPTH

        if not _ok(ratio):
            original = ratio
            while ratio > 2 and not _ok(ratio):
                ratio -= 1
            if ratio != original:
                lines.append((
                    f"比例 {original} 的质数分解层数过多、实际意义较小；"
                    f"已改用接近的 {ratio}（{_factor_text(ratio)}）代替。", "warn"))
                # 比例下调后，搭建演示的目标间隔也跟着改成下调后的时间
                build_interval = ratio * model
        lines.append(("因子分解", "section"))
        lines.extend(format_output_lines(ratio))
        lines.append((f"一小时理论消耗 {total + 1} 个电池", "accent"))
        factors, rules = decompose_target(ratio)
        info = {
            "mode": "precise", "number": number, "rate": rate_per_min, "model": model,
            "battery": battery_output, "interval": build_interval, "time_sec": time_sec,
            "deadline": deadline, "ratio": ratio,
            "factors": dict(sorted(factors.items())),
            "rules": {p: dict(sorted(c.items())) for p, c in sorted(rules.items())},
            "hour": total + 1,
        }
        return lines, f"{number} 个电池 · 1 小时约 {total + 1} 个", info

    search_max = max(ratio_target, 1)
    max3 = int(math.log(search_max, 3))
    max2 = int(math.log(search_max, 2))

    result, result_2, result_3 = 0, 0, 0
    for count_3 in range(0, max3 + 1):
        for count_2 in range(0, max2 + 1):
            value = (2 ** count_2) * (3 ** count_3)
            if result <= value <= ratio_target:
                result = value
                result_2 = count_2
                result_3 = count_3
    result = max(result, 1)

    actual_gap = interval - result * model
    project = int(3600 // (result * model) + 90 * (number - 1))
    percent = (project + 1) / (total + 1) * 100 - 100

    lines.append((f"{result_2} 个二分 和 {result_3} 个三分 可以完成任务", "big"))
    lines.append((f"实际计算比例为 {result}，间隔时间为 {fmt_num(result * model)} 秒，"
                  f"目标间隔时间为 {interval} 秒，差距为 {fmt_num(actual_gap)} 秒。", "body"))
    lines.append((f"一小时理论消耗 {total + 1} 个电池，实际消耗 {project + 1} 个电池，"
                  f"百分比误差为 {percent:.2f}%", "accent"))
    info = {
        "mode": "simple", "number": number, "rate": rate_per_min, "model": model,
        "battery": battery_output, "interval": interval, "time_sec": time_sec,
        "deadline": deadline, "ratio": ratio_target,
        "result": result, "pow2": result_2, "pow3": result_3,
        "actual_interval": result * model,
        "hour": project + 1,
    }
    return lines, f"{number} 个电池 · {result_2} × 二分 + {result_3} × 三分", info


# ================================================================= 游戏内网格蓝图（竖排）
# 方向：N=0, E=1, S=2, W=3（顺时针）
DIR_N, DIR_E, DIR_S, DIR_W = 0, 1, 2, 3


class Geo:
    """一条主链的列几何"""

    def __init__(self, chain, fb_lanes, belts_l, belts_r, dump_l, dump_r):
        self.chain = chain
        self.fb_lanes = fb_lanes
        self.belts_l = belts_l
        self.belts_r = belts_r
        self.dump_l = dump_l            # 往左回收时的通道列
        self.dump_r = dump_r

    def fb(self, level):
        return self.fb_lanes[min(level, len(self.fb_lanes) - 1)]


# 单链（9 列）：0-2 左存货口 | 1 左通道 | 2 左带 | 3 回流 | 4 主链 | 5,6 右带 | 7 右通道 | 6-8 右存货口
GEO_SINGLE = Geo(4, (3, 5, 2, 6), (2,), (5, 6), 1, 7)
# 全速双份（17 列）：左右各一份完整单链，中间一列做二分/合流
# 紧凑双份（13 列，每份只有一条返回支路时用）
GEO_A = Geo(4, (5, 3, 2, 1), (3, 2), (), 2, None)   # 回流走内侧，多余出口全部朝外
GEO_B = Geo(8, (7, 9, 10, 11), (), (9, 10), None, 10)
CENTER = 6
COLS_SINGLE, COLS_DOUBLE = 9, 13
# 宽双份（17 列，某一份需要第二条返回支路时用）
# 副本主链内收到 5 / 11 列，中间列 8：两侧横带从 3 格缩到 2 格
# 回收通道再内收一格（3 / 13）：多余出口横带只剩 1 格
GEO_A2 = Geo(5, (6, 4, 7, 2), (4,), (7,), 3, 7)
GEO_B2 = Geo(11, (10, 12, 9, 14), (9,), (12,), 9, 13)
CENTER2, COLS_DOUBLE2 = 8, 15


class Blueprint:
    """一格一个元件；仓库端口占 1×3（中间一格接线）；热能池占 2×2"""

    def __init__(self, cols):
        self.cells = {}
        self.cols = cols
        self.rows = 0
        self.dumps = []                 # (行, 链列, 方向, 通道列)
        self.ports = set()              # (列, 行, 侧)：已经被占用的元件输出口
        self.fb_path = set()            # (列, 行)：回流带占用；交叉处换物流桥
        self.warnings = []

    def put(self, col, row, file, label="", span=1, span_rows=1):
        if col < 0 or row < 0:
            return
        self.cells[(col, row)] = {"file": file, "label": label,
                                  "span": span, "span_rows": span_rows}
        self.cols = max(self.cols, col + span)
        self.rows = max(self.rows, row + span_rows)

    def belt(self, col, row, direction):
        self.put(col, row, "build_belt_%d.png" % ((direction - DIR_E) % 4))

    def corner(self, col, row, enter, out):
        k = (enter - 2) % 4
        if out == (enter - 1) % 4:
            self.put(col, row, "build_corner_%d.png" % k)
        else:
            self.put(col, row, "build_corner_m%d.png" % k)

    def device(self, col, row, kind, rot, label=""):
        self.put(col, row, "build_%s_%d.png" % (kind, rot), label)

    def bridge(self, col, row):
        self.put(col, row, "build_bridge.png", "物流桥")

    def dump(self, row, chain, side, lane):
        self.dumps.append((row, chain, side, lane))


def _gate_tile(info):
    """物品准入口的图：按电池种类选（与 BATTERIES 同序）"""
    if not info:
        return None
    power = info.get("battery")
    for b in BATTERIES:
        if abs(b["power"] - (power or 0)) < 1e-6:
            return "build_gate_%s" % b["file"]
    return None


def _top_ports(p):
    """这个质数块最上面那个分流器有几个输出口（2 或 3）

    块里每个分流器都要向上输出（占一个口），顶上那个还要同时管本块回流，
    所以口多的必须摆上面。"""
    last = _factor_seq(p + 1, False)[-1]
    return last if last <= 3 else _top_ports(last)


def _factor_seq(n, wrap=False):
    """因子链顺序（从下往上）

    规则（实测）：
      1) 输出口多的排上面 —— 3 分比 2 分多一个口；比到块时，看这个块最上面
         那个分流器有几个口。这样顶上才有口同时给"本块回流 + 向上输出"。
      2) 输出口数量相同的，先摆较大的那个质数（大的靠下）。
    例：13 分 = 三个 2 分组成的 7 分块（顶上是个 2 分）在下，再串一个 2 分在上；
        5 分套了偶数层包裹后，3 分块（顶上 2 分）在下、2 分块（顶上 3 分）在上。
    """
    primes = prime_factorization(n)
    seq = []
    for prime in sorted((x for x in primes if x > 3), reverse=True):
        seq += [prime] * primes[prime]
    for prime in (2, 3):
        if prime in primes:
            seq += [prime] * primes[prime]

    def port_count(f):
        if f <= 3 and not wrap:
            return f                          # 普通 2 分 / 3 分
        return _top_ports(f)                  # 包了一层的子块

    return sorted(seq, key=lambda f: (port_count(f), -f))


# ---------------------------------------------------------------- 块的几何
def _block_height(p, wrap=False, buf=0, borrow=False):
    """块占的行数；wrap=True 时每个因子都再包一层"改"结构（层数 +1）

    buf：本块汇流器下面要不要留一格传送带缓冲。
    主链上"分流器 -> 汇流器"直接相邻时必须留：质数分流器的回流会把汇流器堵住，
    本该向上走的电池就被挤进两侧的返货支路，比例跟着跑偏。

    borrow：本块下面紧挨着的就是父块的汇流器 —— 那就复用它，本块不再单独立一个
    （汇流器串联等价于一个汇流器：主链 + 本块回流 + 父块回流，正好 S/W/E 三个口）。
    """
    h = 0 if borrow else 1 + (buf or 0)      # 回流汇流器（+ 缓冲区格数）
    for i, f in enumerate(_factor_seq(p + 1, wrap)):
        if f > 3 or wrap:
            # 第一个因子下面就是本块的汇流器（复用，不再单独立），其余都在分流器之上
            h += _block_height(f, False, 0 if i == 0 else 1, borrow=(i == 0))
        else:
            h += 1
    return h


def _leads_to_lane(bp, geo, row, lane):
    """从主链那一格水平铺带走到本层通道列（不够近就补格，遇到别的线用桥）"""
    if lane > geo.chain:
        cc, step = geo.chain + 1, DIR_E
    else:
        cc, step = geo.chain - 1, DIR_W
    while cc != lane:
        if (cc, row) in bp.cells:
            bp.bridge(cc, row)
        else:
            bp.belt(cc, row, step)
        cc += 1 if step == DIR_E else -1


def _emit_dump(bp, geo, row, side):
    lane = geo.dump_l if side == DIR_W else geo.dump_r
    bp.dump(row, geo.chain, side, lane)


def _place_block(bp, base, p, geo, level=0, need_output=False, wrap=False, buf=0,
                 rate=None, ascending=False, borrow=False):
    """摆一个质数分流器块（嵌套质数递归展开）

    borrow=True：本块下面紧挨着的就是父块的汇流器，直接把回流并进去，
    不再单独立一个汇流器（省一格，流量不变）。

    返回 (块上方第一行, 末级行, 末级空出来的输出侧, 汇流器行, 汇流器空闲侧)
    """
    lane = geo.fb(level)
    fb_side = DIR_W if lane < geo.chain else DIR_E
    outer = DIR_E if fb_side == DIR_W else DIR_W

    # 缓冲带在汇流器【下方】：从上一级分流器一路连续接到汇流器，长度 = buf
    # （所以汇流器整体上移 buf 格，下面空出来的格子铺成连续传送带）
    row = base
    if borrow:
        fb_row = base + 1                    # 就是父块那个汇流器所在的行
    else:
        if buf:
            for rr in range(base - buf + 1, base + 1):
                bp.belt(geo.chain, rr, DIR_N)
            row = base - buf
        bp.device(geo.chain, row, "merger", 0, "%d 分·回流" % p)
        fb_row = row
        row -= 1

    factors = _factor_seq(p + 1, wrap)
    last_row = fb_row
    free_at = None
    fb_ok = True
    for i, f in enumerate(factors):
        is_last = (i == len(factors) - 1)
        if f <= 3 and not wrap:
            bp.device(geo.chain, row, "splitter", 0, "%d 分" % f)
            if is_last:
                _leads_to_lane(bp, geo, row, lane)
                bp.corner(lane, row, DIR_E if fb_side == DIR_W else DIR_W, DIR_S)
                bp.fb_path.add((lane, row))
                bp.ports.add((geo.chain, row, fb_side))
                if f < 3:
                    # 二分只有两个输出口：keep + 本块回流，已经满了，没有多余口给上层
                    free_at = None
                else:
                    # 三分有 2 个侧口：一个给本块回流，另一个留给上一级的汇流器
                    free_at = (row, outer)
            else:
                _emit_dump(bp, geo, row, outer)
                if f >= 3:
                    _emit_dump(bp, geo, row, fb_side)
            last_row = row
            row -= 1
        else:
            # 嵌套子块：第一个因子下面接着本块的汇流器（直接复用），其余坐在分流器上
            row, top, inner_free, kid_mg, kid_mg_free = _place_block(
                bp, row, f, geo, level + 1,
                need_output=is_last,
                buf=(0 if i == 0 else 1), ascending=ascending,
                borrow=(i == 0))
            last_row = top
            if not is_last:
                continue
            # 子块末级是三分时会给上一级留一个侧口：把它接到本块（上一级）的汇流器上
            if inner_free:
                r2, side = inner_free
                if (side == DIR_E) == (lane > geo.chain):
                    rng = (range(geo.chain + 1, lane) if side == DIR_E
                           else range(lane + 1, geo.chain))
                    step = DIR_E if side == DIR_E else DIR_W
                    enter = DIR_W if side == DIR_E else DIR_E
                    for cc in rng:
                        if (cc, r2) in bp.cells:
                            bp.bridge(cc, r2)
                        else:
                            bp.belt(cc, r2, step)
                    bp.corner(lane, r2, enter, DIR_S)
                    bp.fb_path.add((lane, r2))
                    last_row = max(last_row, r2)
                    fb_ok = True
                else:
                    bp.warnings.append(
                        "%d 分块给上层留的侧口在另一侧，这一级回流改从本块末级接出" % p)
            free_at = None
    mg_free = (fb_side == DIR_W and DIR_E) or (fb_side == DIR_E and DIR_W)
    if not fb_ok:                             # 这条回流没有可用来源，整条都不画
        return row, last_row, free_at, fb_row, mg_free
    for rr in range(last_row + 1, fb_row):
        if (lane, rr) in bp.cells:            # 已经有别的线，改放物流桥跨过去
            bp.bridge(lane, rr)
        else:
            bp.belt(lane, rr, DIR_S)
        bp.fb_path.add((lane, rr))
    step = DIR_E if lane < geo.chain else DIR_W
    bp.corner(lane, fb_row, DIR_N, step)
    rng = (range(lane + 1, geo.chain) if lane < geo.chain
           else range(geo.chain + 1, lane))
    for cc in rng:
        if (cc, fb_row) in bp.cells:
            bp.bridge(cc, fb_row)
        else:
            bp.belt(cc, fb_row, step)
            bp.fb_path.add((cc, fb_row))
    bp.fb_path.add((lane, fb_row))
    return row, last_row, free_at, fb_row, mg_free


def _factor_depth(p):
    """这个质数块的嵌套层数：p 用 p+1 的因子链，其中 >3 的因子还要再套一层"""
    if p <= 3:
        return 1
    deeper = [_factor_depth(f) for f in _factor_seq(p + 1) if f > 3]
    return 1 + (max(deeper) if deeper else 0)


def _ratio_depth(n):
    """整个比例的最大嵌套层数"""
    if n <= 1:
        return 1
    return max(_factor_depth(p) for p in prime_factorization(n))


MAX_DEPTH = 2        # 允许的嵌套层数上限（13 / 19 这类两层正好，37 以上就太深了）


def _factor_text(n):
    parts = []
    for prime, cnt in sorted(prime_factorization(n).items()):
        parts.append(str(prime) if cnt == 1 else "%d^%d" % (prime, cnt))
    return " × ".join(parts)


def _needs_inner(p):
    """块内是否需要第二条返回通道（非末级三分、或含嵌套质数块）"""
    factors = _factor_seq(p + 1)
    for i, f in enumerate(factors):
        last = (i == len(factors) - 1)
        if f > 3 or (not last and f >= 3):
            return True
    return False


def _place_double_blocks(bp, bottom, p, ga, gb, buf=0):
    """两份并行块（副本里 2 分靠前、3 分靠后更省空间）；返回 (合流行, 二分行)"""
    rows = _block_height(p, False, buf)
    top = bottom - rows + 1
    _place_block(bp, bottom, p, ga, 0, buf=buf, ascending=True)
    _place_block(bp, bottom, p, gb, 0, buf=buf, ascending=True)
    return top - 1, bottom + 1


def _place_double_join(bp, merge_row, split_row, ga, gb, center):
    """中间列：底部分流用二分，顶部合流用汇流器；横带遇到通道格改放物流桥"""
    def lay(cc, row, direction):
        if (cc, row) in bp.cells:
            bp.bridge(cc, row)
        else:
            bp.belt(cc, row, direction)

    bp.corner(ga.chain, merge_row, DIR_S, DIR_E)
    bp.corner(gb.chain, merge_row, DIR_S, DIR_W)
    for cc in range(ga.chain + 1, center):
        lay(cc, merge_row, DIR_E)
    for cc in range(center + 1, gb.chain):
        lay(cc, merge_row, DIR_W)
    bp.put(center, merge_row, "build_merger_0.png", "合流")

    # 拐角直接压在副本汇流器下面（汇流器可以直接连拐角，不需要中间再垫传送带）
    for cc, side in ((ga.chain, DIR_E), (gb.chain, DIR_W)):
        cur = bp.cells.get((cc, split_row))
        if cur is not None and "belt" not in cur["file"]:
            continue                       # 已有拐角/汇流器就保留
        bp.cells.pop((cc, split_row), None)   # 普通传送带让位给拐角
        bp.corner(cc, split_row, side, DIR_N)
    for cc in range(ga.chain + 1, center):
        lay(cc, split_row, DIR_W)
    for cc in range(center + 1, gb.chain):
        lay(cc, split_row, DIR_E)
    bp.put(center, split_row, "build_splitter_0.png", "二分·全速")


# ---------------------------------------------------------------- 连通性
def _tile_ports(cell):
    """(输入侧, 输出侧)：侧就是罗盘方向，表示这一侧接着哪个方向"""
    if cell is None:
        return set(), set()
    f = cell["file"]
    if f.startswith("build_splitter"):
        rot = int(f[-5])
        return {(DIR_S + rot) % 4}, {(d + rot) % 4 for d in (DIR_N, DIR_W, DIR_E)}
    if f.startswith("build_merger"):
        rot = int(f[-5])
        return ({(d + rot) % 4 for d in (DIR_S, DIR_W, DIR_E)},
                {(DIR_N + rot) % 4})
    if f.startswith("build_belt_"):
        d = (int(f[11]) + 1) % 4
        return {(d + 2) % 4}, {d}
    if f.startswith("build_corner_m"):
        enter = (int(f[-5]) + 2) % 4
        return {enter}, {(enter + 1) % 4}
    if f.startswith("build_corner_"):
        enter = (int(f[-5]) + 2) % 4
        return {enter}, {(enter - 1) % 4}
    if f.startswith("build_bridge"):
        all4 = {DIR_N, DIR_E, DIR_S, DIR_W}
        return set(all4), set(all4)
    if f.startswith("build_thermal"):
        return set(), {DIR_S}
    if f.startswith("build_pickup"):
        return set(), {DIR_N}
    if f.startswith("build_gate"):
        return {DIR_S}, {DIR_N}
    if f.startswith("build_deposit"):
        return {DIR_N}, set()
    return set(), set()


def _accepts(cell, side):
    """这一格能不能接住从 side 这一侧流进来的东西（side 指向来源）"""
    ins, _outs = _tile_ports(cell)
    return side in ins


def _route_line(bp, row, src_col, side, lane):
    """从 src_col 的 side 侧横着铺到 lane；路上遇到别的带子就用物流桥跨过去。
    先整条路检查一遍，走得通才动笔（不留半截路）"""
    dc = -1 if side == DIR_W else 1
    cc = src_col + dc
    cells = []
    while 0 <= cc < bp.cols and cc != lane:
        cells.append(cc)
        cc += dc
    if cc != lane:
        return False
    for x in cells:
        cur = bp.cells.get((x, row))
        if cur is not None and not cur["file"].startswith(("build_belt",
                                                         "build_bridge")):
            return False                    # 中间杵着设备，这条路走不通
    for x in cells:
        if (x, row) in bp.cells:
            bp.bridge(x, row)
        else:
            bp.belt(x, row, side)
    return True


def _draw_dumps(bp, joins=None):
    """铺横向多余出口传送带；跨过纵向回流带/别的带子时用物流桥。
    真正接上返货通道的行记进 joins[lane][row] = 流向"""
    if joins is None:
        joins = {}
    for row, chain, side, lane in bp.dumps:
        if lane is None:
            continue
        if _route_line(bp, row, chain, side, lane):
            joins.setdefault(lane, {})[row] = side
    return joins


def _fix_three_ports(bp, channels, joins):
    """三分分流器有 3 个输出口：只要有一个口没接上，游戏里它就退化成二分，
    比例也跟着错。缺哪侧就从哪侧接到最近的一条返货通道去（路上遇到带子就用桥跨过去）。

    channels 是所有能一路通到仓库存货口的竖列：两侧的返货通道，加上组合接法里
    副本出口用的内侧通道。由近到远挨个试，哪条走得通就走哪条。"""
    for (cc, rr), cell in sorted(list(bp.cells.items()),
                                 key=lambda kv: (kv[0][1], kv[0][0])):
        lab = cell.get("label") or ""
        if "splitter" not in cell["file"] or not lab.startswith("3 "):
            continue
        for side in (DIR_W, DIR_E):
            dc = -1 if side == DIR_W else 1
            nb = bp.cells.get((cc + dc, rr))
            if _accepts(nb, (side + 2) % 4):
                continue
            if nb is not None and not nb["file"].startswith(("build_belt",
                                                             "build_bridge")):
                continue                    # 那边是设备/拐角，动不了，跳过
            cands = [l for l in channels
                     if (l < cc) == (side == DIR_W) and abs(l - cc) > 1]
            for lane in sorted(cands, key=lambda l: abs(l - cc)):
                if _route_line(bp, rr, cc, side, lane):
                    joins.setdefault(lane, {})[rr] = side
                    break
    return joins


def _build_lanes(bp, joins, port_row, geo):
    """返货通道：左右各一条直线，整条线由汇流器串起来（不拐弯），
    主回路出来的返回带直接横着接进汇流器，最下面一格接仓库存货口。

    组合接法里副本的出口落在中间那几条竖列上（两侧都被副本主链挡住），
    这些内通道同样一条直线走到底，再横一格并进两侧通道一起下去。"""
    lane_l, lane_r = geo.dump_l, geo.dump_r
    jog_row = port_row - 1
    for lane in sorted(l for l in joins if l not in (lane_l, lane_r)):
        rows = joins.pop(lane)
        if not rows:
            continue
        top = min(rows)
        for rr in range(top, jog_row):
            cur = bp.cells.get((lane, rr))
            if cur is not None and not cur["file"].startswith("build_belt"):
                continue
            if rr in rows:
                bp.device(lane, rr, "merger", 2)
            else:
                bp.belt(lane, rr, DIR_S)
        flow = DIR_W if lane < geo.chain else DIR_E
        target = lane_l if flow == DIR_W else lane_r
        if target is None:
            continue
        flow = DIR_W if target < lane else DIR_E      # 朝目标那一侧走，别走反
        bp.corner(lane, jog_row, DIR_N, flow)
        cc = lane + (-1 if flow == DIR_W else 1)
        while cc != target:
            if (cc, jog_row) not in bp.cells:
                bp.belt(cc, jog_row, flow)
            else:
                bp.bridge(cc, jog_row)
            cc += -1 if flow == DIR_W else 1
        joins.setdefault(target, {})[jog_row] = flow
    for lane in (lane_l, lane_r):
        rows = joins.get(lane) or {}
        if not rows:
            continue
        top = min(rows)
        for rr in range(top, port_row):
            cur = bp.cells.get((lane, rr))
            if cur is not None and not cur["file"].startswith("build_belt"):
                continue                    # 已经有汇流器/物流桥，保留
            if rr in rows:
                bp.device(lane, rr, "merger", 2)
            else:
                bp.belt(lane, rr, DIR_S)


def _occupied(bp, col, row):
    """这一格有没有东西（多格元件占的那几格也算）"""
    if (col, row) in bp.cells:
        return True
    for (c0, r0), cell in bp.cells.items():
        span, span_rows = cell.get("span", 1), cell.get("span_rows", 1)
        if span == 1 and span_rows == 1:
            continue
        if c0 <= col < c0 + span and r0 <= row < r0 + span_rows:
            return True
    return False


def _compact(bp, top=2):
    """把整张蓝图往上压紧：热能池固定占 0~1 行，主链第一格紧贴着它"""
    rows = [r for (_c, r), cell in bp.cells.items()
            if not cell["file"].startswith("build_thermal")]
    if not rows:
        return
    shift = min(rows) - top
    if shift <= 0:
        return
    bp.cells = {(c, r - shift): cell for (c, r), cell in bp.cells.items()}
    bp.dumps = [(r - shift,) + tuple(rest) for r, *rest in bp.dumps]
    bp.ports = {(c, r - shift, d) for (c, r, d) in bp.ports}
    bp.fb_path = {(c, r - shift) for (c, r) in bp.fb_path}
    bp.rows = 0
    for (c, r), cell in bp.cells.items():
        bp.rows = max(bp.rows, r + cell.get("span_rows", 1))
        cell.pop("row", None)


def _trim_columns(bp):
    """去掉左右空出来的列（返货通道内收之后边上会剩一列空格）"""
    if not bp.cells:
        return
    left = min(c for (c, _r) in bp.cells)
    right = max(c + cell.get("span", 1) - 1 for (c, _r), cell in bp.cells.items())
    if left == 0 and right == bp.cols - 1:
        return
    if left:
        bp.cells = {(c - left, r): cell for (c, r), cell in bp.cells.items()}
        bp.dumps = [(r, c - left, s, None if l is None else l - left)
                    for r, c, s, l in bp.dumps]
        bp.ports = {(c - left, r, d) for (c, r, d) in bp.ports}
        bp.fb_path = {(c - left, r) for (c, r) in bp.fb_path}
    bp.cols = right - left + 1


def _put_thermal(bp, geo):
    """放热能池（2x2，占 0~1 行），并把中格到主链之间接满传送带"""
    for cc in (geo.chain - 1, geo.chain):
        for rr in (0, 1):
            bp.cells.pop((cc, rr), None)
    bp.put(geo.chain - 1, 0, "build_thermal_big.png", "热能池", span=2, span_rows=2)
    for rr in range(2, bp.rows):
        if (geo.chain, rr) in bp.cells:
            break
        bp.belt(geo.chain, rr, DIR_N)


def build_blueprint(info):
    if not info:
        return None
    full = info["rate"] > 18

    stages = []
    if info["mode"] == "simple":
        stages += [("n", 2)] * info["pow2"] + [("n", 3)] * info["pow3"]
    else:
        for p, cnt in sorted(info["factors"].items()):
            stages += [("n", p) if p <= 3 else ("P", p)] * cnt
    if not stages:
        return None

    # 速率 > 18 时前置质数块必须用组合（二分 -> 并联两份 -> 汇流）接法，
    # 实测只有这样时间才准（单链会因回流跟不上而失准）。
    lead_double = full and stages[0][0] == "P"
    lead = stages[0] if lead_double else None
    rest = stages[1:] if lead_double else stages

    # 缓冲口径（实测）：
    #   主链上"分流器 -> 汇流器"直接贴在一起时，质数分流器的回流会把汇流器堵住，
    #   本该向上走的电池就被挤进两侧返货支路 —— 中间必须塞一格传送带；
    #   汇流器下面是汇流器/拐角时不用塞。
    #   另外：入口 30 / 24 个每分钟、且准入口后面直接接的是普通二分
    #   （不是组合式质数分流器）时，这个二分和它上面那个汇流器之间要留两格。
    first_plain_two = (not lead_double and stages[0][0] == "n"
                       and stages[0][1] == 2)

    stage_bufs = []
    prev_is_splitter = False
    block_seen = False
    for kind, _value in rest:
        if kind != "P":
            stage_bufs.append(0)
        else:
            b = 1 if prev_is_splitter else 0
            # 入口那个普通二分正下方就是它，这里要放宽到两格
            if b and not block_seen and first_plain_two and info["rate"] in (24, 30):
                b = 2
            block_seen = True
            stage_bufs.append(b)
        prev_is_splitter = True

    rest_rows = 0
    for (kind, value), b in zip(rest, stage_bufs):
        if kind == "n":
            rest_rows += 1
        else:
            rest_rows += _block_height(value, lead_double, b)
    lead_rows = (_block_height(lead[1], False, 0) + 3) if lead_double else 0
    chain_rows = lead_rows + rest_rows + 1              # +1 给物品准入口
    chain_top = 2
    chain_bottom = chain_top + chain_rows - 1
    port_row = chain_bottom + 1

    bp = Blueprint(COLS_DOUBLE if lead_double else COLS_SINGLE)
    # 每份只有一条返回支路 -> 紧凑 13 列；要两条 -> 用 17 列（带内侧通道）
    wide = lead_double and _needs_inner(lead[1])
    ga, gb = (GEO_A2, GEO_B2) if wide else (GEO_A, GEO_B)
    if wide:
        bp = Blueprint(COLS_DOUBLE2)
    mid = CENTER2 if wide else CENTER
    # 两侧返货通道尽量贴着复本：复本在 4 / 8 列、通道 0/2/3 与 9/10/11 列里
    # 2 / 10 是空着的（第 2、10 列只有在更深的嵌套里才会用到），
    # 放在这里横带最短只剩一格，仓库口也就不必顶到最边上。
    lane_l_act = GEO_A2.dump_l if wide else 2
    lane_r_act = GEO_B2.dump_r if wide else 10
    geo = (Geo(mid, (mid - 1, mid + 1, mid - 2, mid + 2),
               (mid - 2, mid - 3), (mid + 2, mid + 3), lane_l_act, lane_r_act)
           if lead_double else GEO_SINGLE)

    merge_row_d = split_row_d = None
    r = chain_bottom - 1                    # 最下面一行留给物品准入口
    if lead_double:
        # 组合接法：底部二分 -> 两份并行块 -> 合流汇流器，合流行在副本块顶上
        merge_row_d, split_row_d = _place_double_blocks(
            bp, chain_bottom - 2, lead[1], ga, gb, 0)
        r = merge_row_d - 1

    for (kind, value), b in zip(rest, stage_bufs):
        if kind == "n":
            bp.device(geo.chain, r, "splitter", 0, "%d 分" % value)
            _emit_dump(bp, geo, r, DIR_W)
            if value >= 3:
                _emit_dump(bp, geo, r, DIR_E)
            r -= 1
        else:
            # 组合接法下游的质数块：因子逐级包一层"改"结构，把回路层数推成偶数
            r = _place_block(bp, r, value, geo, 0, wrap=lead_double, buf=b)[0]

    # ---- 分支：多余出口 + 三分补口 -> 两侧返货通道 ----
    joins = _draw_dumps(bp)
    # 能通到仓库口的竖列：两侧通道 + （组合接法才有）副本出口用的内侧通道
    channels = {c for c in (geo.dump_l, geo.dump_r) if c is not None}
    if lead_double:
        channels |= {c for c in (ga.dump_l, ga.dump_r, gb.dump_l, gb.dump_r)
                     if c is not None}
    _fix_three_ports(bp, channels, joins)
    _build_lanes(bp, joins, port_row, geo)
    if lead_double:                       # 通道铺好后再铺中间的二分/合流（跨通道处用桥）
        _place_double_join(bp, merge_row_d, split_row_d, ga, gb, mid)
        for rr in range(2, merge_row_d):  # 合流汇流器 -> 热能池
            if (mid, rr) not in bp.cells:
                bp.belt(mid, rr, DIR_N)

    # ---- 端口（存货口中格 = 通道列） ----
    lane_l = geo.dump_l if geo.dump_l is not None else 1
    lane_r = geo.dump_r if geo.dump_r is not None else (bp.cols - 2)
    if joins.get(lane_l):
        bp.put(lane_l - 1, port_row, "build_deposit.png", "仓库存货口", span=3)
    if lead_double:
        bp.put(mid - 1, port_row, "build_pickup.png", "仓库取货口", span=3)
        # 取货口 -> 中间列 -> 二分（从二分行下方一路补到端口行）
        for rr in range(split_row_d + 1, port_row):
            if (mid, rr) not in bp.cells:
                bp.belt(mid, rr, DIR_N)
    else:
        bp.put(geo.chain - 1, port_row, "build_pickup.png", "仓库取货口", span=3)
    if joins.get(lane_r):
        bp.put(lane_r - 1, port_row, "build_deposit.png", "仓库存货口", span=3)

    # ---- 物品准入口：直接摆在取货口输出口上（不用传送带中转） ----
    gate_col = mid if lead_double else geo.chain
    gate_file = _gate_tile(info)
    if gate_file:
        bname = ""
        for b in BATTERIES:
            if abs(b["power"] - (info.get("battery") or 0)) < 1e-6:
                bname = b["name"]
        bp.put(gate_col, port_row - 1, gate_file,
               "物品准入口 %s %d/分" % (bname, info.get("rate", 0)))

    # ---- 压紧：主链第一格紧贴热能池，不留空带 ----
    _compact(bp, chain_top)

    _put_thermal(bp, geo)

    # ---- 三分"keep"的那个口必须接上（二分留空是故意的，别补） ----
    for (cc, rr), cell in sorted(list(bp.cells.items()),
                                 key=lambda kv: (kv[0][1], kv[0][0])):
        lab = cell.get("label") or ""
        if "splitter" not in cell["file"] or not lab.startswith("3 "):
            continue
        if rr > 0 and not _occupied(bp, cc, rr - 1):
            bp.belt(cc, rr - 1, DIR_N)

    # 收尾自检：回流汇流器左右都没接东西时，说明这一级回流没找到来源，
    # 图上先按"并列汇流"画（游戏里能跑，但比例需要对照参考图确认）
    for (cc, rr), cell in list(bp.cells.items()):
        lab = cell.get("label") or ""
        if "merger" not in cell["file"] or "回流" not in lab:
            continue
        if (cc - 1, rr) in bp.cells or (cc + 1, rr) in bp.cells:
            continue
        bp.warnings.append(
            "%s 这一级回流没有找到可用来源，图上按并列汇流摆放，"
            "比例请对照参考图确认" % lab)
    _trim_columns(bp)
    return bp


# ================================================================= 自定义滑轨
class StepSlider(tk.Canvas):
    """圆润的离散滑轨：可点击、可拖动、可用方向键"""

    def __init__(self, master, values, index, command, px, font_num, font_num_bold,
                 page_bg=PANEL, **kw):
        self.px = px
        super().__init__(master, bg=page_bg, height=px(80),
                         highlightthickness=0, bd=0, takefocus=True, **kw)
        self.values = list(values)
        self.index = index
        self.command = command
        self.font_num = font_num
        self.font_num_bold = font_num_bold
        self.pad = px(26)
        self.track_y = px(28)

        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Left>", lambda e: self.step(-1))
        self.bind("<Right>", lambda e: self.step(1))
        self.bind("<FocusIn>", lambda e: self.redraw())
        self.bind("<FocusOut>", lambda e: self.redraw())

    def _xs(self):
        width = self.winfo_width()
        n = len(self.values)
        left, right = self.pad, width - self.pad
        span = max(right - left, 1)
        return [left + span * i / (n - 1) for i in range(n)]

    def redraw(self):
        self.delete("all")
        if self.winfo_width() <= 1:
            return
        xs = self._xs()
        y = self.track_y
        focused = self.focus_get() is self

        self.create_line(xs[0], y, xs[-1], y, fill=TRACK,
                         width=self.px(8), capstyle="round")
        if self.index > 0:
            self.create_line(xs[0], y, xs[self.index], y, fill=ACCENT,
                             width=self.px(8), capstyle="round")

        for i, (x, value) in enumerate(zip(xs, self.values)):
            self.create_text(x, y + self.px(31), text=str(value),
                             fill=ACCENT if i == self.index else MUTED,
                             font=(self.font_num_bold if i == self.index
                                   else self.font_num))

        knob_x = xs[self.index]
        k = self.px(13)
        ring = self.px(4)
        dot = self.px(4.5)
        knob_fill = ACCENT_HI if focused else ACCENT
        self.create_image(knob_x, y, image=circle_photo(2 * k, BG, PANEL))
        self.create_image(knob_x, y, image=circle_photo(2 * k - 2 * ring,
                                                        knob_fill, BG))
        self.create_image(knob_x, y, image=circle_photo(2 * dot, BG, knob_fill))

    def _on_press(self, event):
        self.focus_set()
        self._move_to(event.x)

    def _on_drag(self, event):
        self._move_to(event.x)

    def _move_to(self, x):
        xs = self._xs()
        self.set_index(min(range(len(xs)), key=lambda i: abs(xs[i] - x)))

    def step(self, delta):
        self.set_index(self.index + delta)

    def set_index(self, index):
        index = max(0, min(len(self.values) - 1, index))
        changed = index != self.index
        self.index = index
        self.redraw()
        if changed and self.command:
            self.command(self.values[index])


# ================================================================= 弹出层工具
POPUP_MAGIC = "#FE01FE"


def make_popup(parent, page_bg):
    """创建圆角弹出窗口，返回 (窗口, 画布, 内容容器, 窗口项, 是否支持透明)"""
    pop = tk.Toplevel(parent)
    pop.overrideredirect(True)
    transparent = False
    try:
        pop.configure(bg=POPUP_MAGIC)
        pop.attributes("-transparentcolor", POPUP_MAGIC)
        transparent = True
    except tk.TclError:
        pop.configure(bg=page_bg)
    canvas = tk.Canvas(pop, bg=POPUP_MAGIC if transparent else page_bg,
                       highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)
    holder = tk.Frame(canvas, bg=PANEL)
    item = canvas.create_window(0, 0, anchor="nw", window=holder)
    return pop, canvas, holder, item, transparent


def _polygon_round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """
    多边形近似的圆角矩形（仅用于弹窗）。
    弹窗靠 -transparentcolor 做圆角透明，抗锯齿边缘会与“透明色”混色留下毛边，
    所以这里退而使用无抗锯齿的平滑多边形。
    """
    radius = max(2, min(int(radius), int((x2 - x1) / 2), int((y2 - y1) / 2)))
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=48, **kwargs)


_CIRCLE_CACHE = {}


def circle_photo(diameter, color, page_bg):
    """生成抗锯齿实心圆贴图（滑轨圆点、滑块用）"""
    diameter = max(int(diameter), 2)
    key = (diameter, color, page_bg)
    photo = _CIRCLE_CACHE.get(key)
    if photo is not None:
        return photo
    radius = diameter / 2.0
    cr, cg, cb = _rgb(color)
    br, bg, bb = _rgb(page_bg)
    rows = []
    for j in range(diameter):
        row = bytearray()
        for i in range(diameter):
            d = math.hypot(i + 0.5 - radius, j + 0.5 - radius)
            cover = min(max(radius - d + 0.5, 0.0), 1.0)
            row += bytes((int(br + (cr - br) * cover + 0.5),
                          int(bg + (cg - bg) * cover + 0.5),
                          int(bb + (cb - bb) * cover + 0.5), 255))
        rows.append(row)
    photo = tk.PhotoImage(data=base64.b64encode(_png_bytes(diameter, diameter, rows)))
    _CIRCLE_CACHE[key] = photo
    return photo


def finish_popup(pop, canvas, holder, item, transparent, px, width, height, radius):
    """按内容尺寸定位弹窗并画圆角背景（透明模式下用抖动做平滑边缘）"""
    pop.geometry(f"{width}x{height}")
    pop.update_idletasks()
    canvas.delete("__shape__")
    r = px(radius)
    if transparent:
        pad = int(math.ceil(r * 0.30)) + 1
        draw_round_panel(canvas, width, height, r, PANEL, ACCENT_DIM,
                         POPUP_MAGIC, dither=True)
    else:
        pad = px(2)
        _polygon_round_rect(canvas, 1, 1, width - 1, height - 1, r,
                            fill=PANEL, outline=ACCENT_DIM, width=1,
                            tags="__shape__")
        canvas.tag_lower("__shape__")
    canvas.coords(item, pad, pad)
    canvas.itemconfigure(item, width=max(width - 2 * pad, 1),
                         height=max(height - 2 * pad, 1))


# ================================================================= 电池下拉框
class BatterySelect(RoundedBox):
    """带图片的电池种类下拉框（圆角）"""

    def __init__(self, master, items, photos, px, fonts, index=0, command=None):
        super().__init__(master, px, radius=R_FIELD, fill=INPUT_BG,
                         outline=BORDER, page_bg=PANEL, inner_pad=1, autosize=True)
        self.configure(takefocus=True)
        self.items = items
        self.photos = photos
        self.fonts = fonts
        self.index = index
        self.command = command

        self.popup = None
        self.rows = []
        self.row_index = {}
        self.hover_index = None

        box = self.body
        self.thumb = tk.Label(box, bg=INPUT_BG, bd=0, image=photos[index]["big"])
        self.thumb.pack(side="left", padx=(px(8), px(12)), pady=px(8))

        info = tk.Frame(box, bg=INPUT_BG)
        info.pack(side="left", fill="x", expand=True)
        self.name_lbl = tk.Label(info, text="", bg=INPUT_BG, fg=TEXT,
                                 font=fonts["label"], anchor="w")
        self.name_lbl.pack(fill="x")
        self.value_lbl = tk.Label(info, text="", bg=INPUT_BG, fg=ACCENT,
                                  font=fonts["small"], anchor="w")
        self.value_lbl.pack(fill="x")

        self.arrow = tk.Label(box, text="▾", bg=INPUT_BG, fg=ACCENT,
                              font=fonts["label"], padx=px(12))
        self.arrow.pack(side="right")

        for widget in (self, box, self.thumb, info, self.name_lbl,
                       self.value_lbl, self.arrow):
            widget.bind("<Button-1>", self.toggle)
            widget.bind("<Return>", self.toggle)
            widget.bind("<space>", self.toggle)
            widget.bind("<Escape>", lambda e: self.close_popup())
            widget.configure(cursor="hand2")
        self.bind("<FocusIn>", lambda e: self.set_outline(ACCENT))
        self.bind("<FocusOut>", lambda e: self.set_outline(BORDER))
        self.refresh()

    @property
    def current(self):
        return self.items[self.index]

    def refresh(self):
        item = self.current
        self.thumb.configure(image=self.photos[self.index]["big"])
        self.name_lbl.configure(text=item["name"])
        self.value_lbl.configure(text=f"每秒发电 {item['power']} 单位")

    def set_index(self, index, notify=True):
        index = max(0, min(len(self.items) - 1, index))
        changed = index != self.index
        self.index = index
        self.refresh()
        if changed and notify and self.command:
            self.command(self.current)

    # ---------------------------------------------------------- 弹出层
    def toggle(self, event=None):
        if self.popup is not None:
            self.close_popup()
        else:
            self.open_popup()
        return "break"

    def open_popup(self):
        self.focus_set()
        px = self.px
        pop, canvas, holder, item, transparent = make_popup(self, PANEL)
        self.popup = pop
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass

        self.rows = []
        self.row_index = {}
        self.hover_index = None

        for i, one in enumerate(self.items):
            row = tk.Frame(holder, bg=PANEL, cursor="hand2")
            row.pack(fill="x")
            marker = tk.Frame(row, bg=PANEL, width=px(4))
            marker.pack(side="left", fill="y")
            thumb = tk.Label(row, bg=PANEL, bd=0, image=self.photos[i]["small"])
            thumb.pack(side="left", padx=(px(14), px(16)), pady=px(9))
            text = tk.Frame(row, bg=PANEL)
            text.pack(side="left", fill="x", expand=True, pady=px(9))
            name = tk.Label(text, text=one["name"], bg=PANEL, fg=TEXT,
                            font=self.fonts["label"], anchor="w")
            name.pack(fill="x")
            value = tk.Label(text, text=f"每秒发电 {one['power']} 单位", bg=PANEL,
                             fg=MUTED, font=self.fonts["small"], anchor="w")
            value.pack(fill="x")
            check = tk.Label(row, text="✓", bg=PANEL, fg=ACCENT,
                             font=self.fonts["label"], padx=px(18))
            check.pack(side="right")

            widgets = [row, marker, thumb, text, name, value, check]
            for widget in widgets:
                self.row_index[widget] = i
                widget.bind("<Button-1>", lambda e, k=i: self._choose(k))
                widget.bind("<Motion>", self._on_motion)
            self.rows.append({"frame": row, "marker": marker, "thumb": thumb,
                              "text": text, "name": name, "value": value, "check": check})

        self._paint_rows()

        holder.update_idletasks()
        pad = int(math.ceil(px(R_POPUP) * 0.30)) + 1 if transparent else px(2)
        width = max(self.winfo_width(), holder.winfo_reqwidth() + 2 * pad)
        height = holder.winfo_reqheight() + 2 * pad
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + px(6)
        if y + height > self.winfo_screenheight() - px(20):
            y = max(self.winfo_rooty() - height - px(6), 0)
        finish_popup(pop, canvas, holder, item, transparent, px, width, height, R_POPUP)
        pop.geometry(f"{width}x{height}+{x}+{y}")

        pop.bind("<Button-1>", lambda e: self.close_popup())
        pop.bind("<Escape>", lambda e: self.close_popup())
        pop.bind("<Up>", lambda e: self._move(-1))
        pop.bind("<Down>", lambda e: self._move(1))
        pop.bind("<Return>", lambda e: self._choose(
            self.hover_index if self.hover_index is not None else self.index))
        try:
            pop.grab_set()
        except tk.TclError:
            pass
        pop.focus_set()

    def close_popup(self):
        if self.popup is None:
            return
        pop, self.popup = self.popup, None
        try:
            pop.grab_release()
        except tk.TclError:
            pass
        pop.destroy()
        self.rows = []
        self.row_index = {}
        self.hover_index = None

    def _choose(self, index):
        self.close_popup()
        self.set_index(index)
        return "break"

    def _move(self, delta):
        base = self.hover_index if self.hover_index is not None else self.index
        self.hover_index = max(0, min(len(self.items) - 1, base + delta))
        self._paint_rows()

    def _on_motion(self, event):
        widget = self.popup.winfo_containing(event.x_root, event.y_root) if self.popup else None
        index = None
        while widget is not None:
            if widget in self.row_index:
                index = self.row_index[widget]
                break
            widget = getattr(widget, "master", None)
        if index != self.hover_index:
            self.hover_index = index
            self._paint_rows()

    def _paint_rows(self):
        for i, row in enumerate(self.rows):
            selected = (i == self.index)
            hovered = (i == self.hover_index)
            bg = ROW_SEL if selected else (PANEL_HI if hovered else PANEL)
            for key in ("frame", "thumb", "text", "name", "value", "check"):
                row[key].configure(bg=bg)
            row["marker"].configure(bg=ACCENT if selected else bg)
            row["name"].configure(fg=ACCENT if selected else TEXT)
            row["value"].configure(fg=ACCENT_DIM if selected else MUTED)
            row["check"].configure(text="✓" if selected else "")


# ================================================================= 主题下拉框
class ThemeSelect(RoundedBox):
    """右上角的配色下拉框：色块 + 主题名（圆角）"""

    def __init__(self, master, keys, labels, current, px, fonts, command):
        super().__init__(master, px, radius=R_FIELD, fill=PANEL_HI,
                         outline=BORDER, page_bg=BG, inner_pad=1, autosize=True)
        self.configure(takefocus=True)
        self.keys = list(keys)
        self.labels = labels
        self.current = current
        self.command = command
        self.fonts = fonts

        self.popup = None
        self.rows = []
        self.row_index = {}
        self.hover_index = None

        box = self.body
        self.swatch = tk.Frame(box, bg=PANEL_HI)
        self.swatch.pack(side="left", padx=(px(14), px(10)), pady=px(10))
        self.sw1 = tk.Frame(self.swatch, width=px(11), height=px(20))
        self.sw1.pack(side="left")
        self.sw2 = tk.Frame(self.swatch, width=px(11), height=px(20))
        self.sw2.pack(side="left")

        self.name_lbl = tk.Label(box, text="", bg=PANEL_HI, fg=ACCENT,
                                 font=fonts["small"], anchor="w")
        self.name_lbl.pack(side="left", padx=(0, px(4)))
        self.arrow = tk.Label(box, text="▾", bg=PANEL_HI, fg=ACCENT,
                              font=fonts["small"], padx=px(12))
        self.arrow.pack(side="right")

        for widget in (self, box, self.swatch, self.sw1, self.sw2,
                       self.name_lbl, self.arrow):
            widget.bind("<Button-1>", self.toggle)
            widget.bind("<Return>", self.toggle)
            widget.bind("<space>", self.toggle)
            widget.configure(cursor="hand2")
        self.refresh()

    def refresh(self):
        self.sw1.configure(bg=THEMES[self.current]["PANEL"])
        self.sw2.configure(bg=THEMES[self.current]["ACCENT"])
        self.name_lbl.configure(text=self.labels[self.current])

    def toggle(self, event=None):
        if self.popup is not None:
            self.close_popup()
        else:
            self.open_popup()
        return "break"

    def open_popup(self):
        self.focus_set()
        px = self.px
        pop, canvas, holder, item, transparent = make_popup(self, PANEL)
        self.popup = pop
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass

        self.rows = []
        self.row_index = {}
        self.hover_index = None

        for key in self.keys:
            theme = THEMES[key]
            row = tk.Frame(holder, bg=PANEL, cursor="hand2")
            row.pack(fill="x")
            marker = tk.Frame(row, bg=PANEL, width=px(4))
            marker.pack(side="left", fill="y")
            swatch = tk.Frame(row, bg=PANEL)
            swatch.pack(side="left", padx=(px(16), px(12)), pady=px(11))
            a = tk.Frame(swatch, width=px(13), height=px(23), bg=theme["PANEL"])
            a.pack(side="left")
            b = tk.Frame(swatch, width=px(13), height=px(23), bg=theme["ACCENT"])
            b.pack(side="left")
            name = tk.Label(row, text=self.labels[key], bg=PANEL, fg=TEXT,
                            font=self.fonts["label"], anchor="w", padx=px(2))
            name.pack(side="left", fill="x", expand=True, pady=px(11))
            check = tk.Label(row, text="", bg=PANEL, fg=ACCENT,
                             font=self.fonts["label"], padx=px(16))
            check.pack(side="right")

            widgets = [row, marker, swatch, a, b, name, check]
            for widget in widgets:
                self.row_index[widget] = key
                widget.bind("<Button-1>", lambda e, k=key: self._choose(k))
                widget.bind("<Motion>", self._on_motion)
            self.rows.append({"key": key, "frame": row, "marker": marker,
                              "swatch": swatch, "sw1": a, "sw2": b,
                              "name": name, "check": check})

        self._paint_rows()

        holder.update_idletasks()
        pad = int(math.ceil(px(R_POPUP) * 0.30)) + 1 if transparent else px(2)
        width = max(self.winfo_width(), holder.winfo_reqwidth() + 2 * pad)
        height = holder.winfo_reqheight() + 2 * pad
        x = self.winfo_rootx() + self.winfo_width() - width
        y = self.winfo_rooty() + self.winfo_height() + px(6)
        if y + height > self.winfo_screenheight() - px(20):
            y = max(self.winfo_rooty() - height - px(6), 0)
        finish_popup(pop, canvas, holder, item, transparent, px, width, height, R_POPUP)
        pop.geometry(f"{width}x{height}+{max(x, 0)}+{y}")

        pop.bind("<Button-1>", lambda e: self.close_popup())
        pop.bind("<Escape>", lambda e: self.close_popup())
        pop.bind("<Up>", lambda e: self._move(-1))
        pop.bind("<Down>", lambda e: self._move(1))
        pop.bind("<Return>", lambda e: self._choose(self.hover_index or self.current))
        try:
            pop.grab_set()
        except tk.TclError:
            pass
        pop.focus_set()

    def close_popup(self):
        if self.popup is None:
            return
        pop, self.popup = self.popup, None
        try:
            pop.grab_release()
        except tk.TclError:
            pass
        pop.destroy()
        self.rows = []
        self.row_index = {}
        self.hover_index = None

    def _choose(self, key):
        self.close_popup()
        if key != self.current and self.command:
            self.command(key)
        return "break"

    def _move(self, delta):
        base = self.hover_index if self.hover_index in self.keys else self.current
        index = self.keys.index(base)
        self.hover_index = self.keys[max(0, min(len(self.keys) - 1, index + delta))]
        self._paint_rows()

    def _on_motion(self, event):
        widget = self.popup.winfo_containing(event.x_root, event.y_root) if self.popup else None
        key = None
        while widget is not None:
            if widget in self.row_index:
                key = self.row_index[widget]
                break
            widget = getattr(widget, "master", None)
        if key != self.hover_index:
            self.hover_index = key
            self._paint_rows()

    def _paint_rows(self):
        for row in self.rows:
            selected = (row["key"] == self.current)
            hovered = (row["key"] == self.hover_index)
            bg = ROW_SEL if selected else (PANEL_HI if hovered else PANEL)
            for key in ("frame", "swatch", "name", "check"):
                row[key].configure(bg=bg)
            theme = THEMES[row["key"]]
            row["sw1"].configure(bg=theme["PANEL"])
            row["sw2"].configure(bg=theme["ACCENT"])
            row["marker"].configure(bg=ACCENT if selected else bg)
            row["name"].configure(fg=ACCENT if selected else TEXT)
            row["check"].configure(text="✓" if selected else "")


# ================================================================= 主窗口
class BatteryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("终末地 · 电池配比计算器")
        self.configure(bg=BG)

        self.scale = max(self.winfo_fpixels("1i") / 96.0, 1.0)

        self.theme_name = DEFAULT_THEME
        self.mode_var = tk.StringVar(value="normal")
        self.total_var = tk.StringVar()
        self._last_segments = None
        self._last_info = None
        self.output_mode = "result"
        self._close_dialog_open = False
        self.close_action = ""

        self.minsize(self.px(1180), self.px(770))
        self._build_fonts()
        self.battery_photos = self._load_battery_photos()
        self.build_tiles = self._load_build_tiles()
        self._set_window_icon()
        self._build_header()
        self._build_body()
        self._center(1280, 820)
        apply_titlebar_color(self)

        self.bind("<Return>", lambda e: self.on_calculate())
        self.protocol("WM_DELETE_WINDOW", self.on_close_request)

        self.after(80, lambda: self.total_entry.focus_set())
        self.show_placeholder()

    # ---------------------------------------------------------- 工具
    def px(self, value):
        return int(round(value * self.scale))

    def _load_battery_photos(self):
        """载入电池图片：大图给输入框，小图给下拉列表"""
        big_f, small_f = (2, 4) if self.scale >= 2 else (4, 8)
        folder = resource_dir()
        photos = []
        self.missing_images = []
        for item in BATTERIES:
            path = os.path.join(folder, item["file"])
            try:
                raw = tk.PhotoImage(file=path)
            except tk.TclError:
                self.missing_images.append(item["file"])
                raw = tk.PhotoImage(width=224, height=224)
                raw.put(PANEL_HI, to=(0, 0, 224, 224))
            photos.append({"raw": raw,
                           "big": raw.subsample(big_f),
                           "small": raw.subsample(small_f)})
        return photos

    def _set_window_icon(self, win=None):
        """把软件图标设为 logo（win=None 时设置主窗口自己的图标）"""
        win = win or self
        folder = resource_dir()
        try:
            win.iconbitmap(os.path.join(folder, "logo.ico"))
            return
        except tk.TclError:
            pass
        try:
            if not hasattr(self, "logo_raw"):
                self.logo_raw = tk.PhotoImage(file=os.path.join(folder, "logo.png"))
            win.iconphoto(True, self.logo_raw)
        except tk.TclError:
            pass

    # ---------------------------------------------------------- 字体
    def _build_fonts(self):
        self.f_title = tkfont.Font(family=FONT_UI, size=20, weight="bold")
        self.f_sub = tkfont.Font(family=FONT_MONO, size=9)
        self.f_section = tkfont.Font(family=FONT_UI, size=12, weight="bold")
        self.f_label = tkfont.Font(family=FONT_UI, size=12)
        self.f_entry = tkfont.Font(family=FONT_MONO, size=16)
        self.f_btn = tkfont.Font(family=FONT_UI, size=12, weight="bold")
        self.f_hint = tkfont.Font(family=FONT_UI, size=7)
        self.f_small = tkfont.Font(family=FONT_UI, size=11)
        self.f_bp = tkfont.Font(family=FONT_UI, size=7)
        self.f_mono = tkfont.Font(family=FONT_MONO, size=12)
        self.f_mono_b = tkfont.Font(family=FONT_MONO, size=12, weight="bold")
        self.f_mono_big = tkfont.Font(family=FONT_MONO, size=15, weight="bold")
        self.f_num = tkfont.Font(family=FONT_MONO, size=13)
        self.f_num_bold = tkfont.Font(family=FONT_MONO, size=14, weight="bold")
        self.fonts = {"label": self.f_label, "small": self.f_small,
                      "section": self.f_section}

    def _center(self, width, height):
        width, height = self.px(width), self.px(height)
        self.update_idletasks()
        x = max((self.winfo_screenwidth() - width) // 2, 0)
        y = max((self.winfo_screenheight() - height) // 3, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ---------------------------------------------------------- 顶部
    def _build_header(self):
        margin = self.px(SIDE_MARGIN)
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=margin, pady=(self.px(18), 0))

        texts = tk.Frame(header, bg=BG)
        texts.pack(side="left")
        tk.Label(texts, text="终末地 · 电池配比计算器", bg=BG, fg=TEXT,
                 font=self.f_title).pack(anchor="w")
        tk.Label(texts, text="ENDFIELD  /  BATTERY  RATIO  CALCULATOR", bg=BG,
                 fg=ACCENT_DIM, font=self.f_sub).pack(anchor="w", pady=(self.px(4), 0))

        self.theme_select = ThemeSelect(header, THEME_KEYS, THEME_LABELS,
                                        self.theme_name, self.px, self.fonts,
                                        self.switch_theme)
        self.theme_select.pack(side="right", pady=(self.px(8), 0))

        line = tk.Frame(self, bg=BG)
        line.pack(fill="x", padx=margin, pady=(self.px(14), self.px(16)))
        tk.Frame(line, bg=ACCENT, height=self.px(3), width=self.px(130)).pack(side="left")
        tk.Frame(line, bg=BORDER, height=self.px(3)).pack(side="left", fill="x", expand=True)

    # ---------------------------------------------------------- 主体
    def _build_body(self):
        margin = self.px(SIDE_MARGIN)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=margin, pady=(0, self.px(22)))
        body.columnconfigure(0, weight=0, minsize=self.px(452))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.left_panel = RoundedBox(body, self.px, radius=R_PANEL, fill=PANEL,
                                     outline=BORDER, page_bg=BG)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(24)))
        self.right_panel = RoundedBox(body, self.px, radius=R_PANEL, fill=PANEL,
                                      outline=BORDER, page_bg=BG)
        self.right_panel.grid(row=0, column=1, sticky="nsew")

        self._build_left(self.left_panel.body)
        self._build_right(self.right_panel.body)

    # ---------------------------------------------------------- 搭建演示素材
    def _load_build_tiles(self):
        """载入元件图：基点图给图例，四向版本给网格蓝图"""
        big_f, small_f = (2, 4) if self.scale >= 2 else (4, 8)
        folder = resource_dir()
        tiles = {}
        for name, label, size in BUILD_TILES:
            try:
                raw = tk.PhotoImage(file=os.path.join(folder, name))
            except tk.TclError:
                continue
            tiles[name] = {"label": label, "raw": raw,
                           "big": raw.subsample(big_f),
                           "small": raw.subsample(small_f)}
        # 蓝图用的所有小图（224 原始尺寸，绘制时再 zoom/subsample）
        self.bp_raw = {}
        for name in blueprint_files():
            try:
                self.bp_raw[name] = tk.PhotoImage(file=os.path.join(folder, name))
            except tk.TclError:
                pass
        self._bp_cache = {}
        return tiles

    # ---------------------------------------------------------- 蓝图绘制工具
    def _bp_scale(self, target):
        """挑一组 zoom/subsample，让元件图正好占一格"""
        best = None
        for k in range(1, 5):
            for m in range(1, 13):
                size = 224.0 * k / m
                diff = abs(size - target)
                if best is None or diff < best[0]:
                    best = (diff, k, m, int(round(size)))
        return best[1], best[2], best[3]

    def _bp_photo(self, name, k, m):
        key = (name, k, m)
        if key in self._bp_cache:
            return self._bp_cache[key]
        raw = getattr(self, "bp_raw", {}).get(name)
        if raw is None:
            return None
        photo = raw.zoom(k) if k > 1 else raw
        if m > 1:
            photo = photo.subsample(m)
        self._bp_cache[key] = photo
        return photo

    def _draw_blueprint(self, parent, bp, cell=None):
        """把网格蓝图画成游戏蓝图预览那种样子"""
        if cell is None:
            avail = 0
            try:
                avail = self.right_panel.body.winfo_width() - self.px(76)
            except Exception:
                pass
            if avail < self.px(320):
                avail = self.px(320)
            target = max(self.px(24), min(self.px(72), avail // max(bp.cols, 1)))
            k, m, cell = self._bp_scale(target)
        else:
            k, m, cell = self._bp_scale(cell)

        width, height = cell * bp.cols, cell * bp.rows
        canvas = tk.Canvas(parent, width=width, height=height, bg=BP_PAGE,
                           highlightthickness=1, bd=0, highlightbackground=BP_LINE)
        canvas.pack(pady=(0, self.px(6)))

        for c in range(bp.cols + 1):
            canvas.create_line(c * cell, 0, c * cell, height, fill=BP_LINE)
        for r in range(bp.rows + 1):
            canvas.create_line(0, r * cell, width, r * cell, fill=BP_LINE)

        for (col, row), info in sorted(bp.cells.items()):
            photo = self._bp_photo(info["file"], k, m)
            if photo is None:
                continue
            x, y = col * cell, row * cell
            # 多格元件（1×3 端口、2×2 热能池）本身就按 N 格出图，整张画一次
            canvas.create_image(x, y, image=photo, anchor="nw")
            label = info.get("label")
            if label and cell >= self.px(30):
                cx = x + (cell * info.get("span", 1)) // 2
                ty = y + cell * info.get("span_rows", 1) - self.px(2)
                tw = self.f_bp.measure(label)
                th = self.f_bp.metrics("linespace")
                canvas.create_rectangle(
                    cx - tw // 2 - self.px(3), ty - th - self.px(2),
                    cx + tw // 2 + self.px(3), ty + self.px(1),
                    fill=BP_LABEL, outline=BP_LINE)
                canvas.create_text(cx, ty - self.px(1), text=label,
                                   fill=BP_TEXT, font=self.f_bp, anchor="s")
        return canvas

    def open_blueprint_window(self):
        """把蓝图放到独立窗口里放大查看"""
        bp = build_blueprint(self._last_info) if getattr(self, "_last_info", None) else None
        if bp is None:
            return
        win = tk.Toplevel(self)
        win.title("网格蓝图 · 放大查看")
        self._set_window_icon(win)
        win.configure(bg=BP_WIN)
        apply_titlebar_color(win)          # 标题栏跟主题走
        win.minsize(self.px(420), self.px(320))

        holder = tk.Frame(win, bg=BP_WIN)
        holder.pack(fill="both", expand=True)
        canvas = tk.Canvas(holder, bg=BP_PAGE, highlightthickness=0)
        hbar = self._make_scrollbar(holder, "horizontal")
        vbar = self._make_scrollbar(holder, "vertical")
        canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BP_PAGE)
        canvas.create_window(0, 0, window=inner, anchor="nw")
        self._draw_blueprint(inner, bp, cell=self.px(58))
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        info = self._last_info
        tk.Label(win, text=f"{bp.cols} 列 × {bp.rows} 行　·　"
                           f"速率 {info['rate']} 个/分钟　·　"
                           f"目标间隔 {fmt_num(info['interval'])} 秒",
                 bg=BP_WIN, fg=MUTED, font=self.f_small).pack(
                     side="bottom", pady=self.px(6))

        # ---- 鼠标滚轮 / 触控板：上下滚，Shift 横向滚 ----
        def _popup_wheel(event):
            step = 0
            num = getattr(event, "num", None)
            if num == 4:
                step = -1
            elif num == 5:
                step = 1
            else:
                delta = getattr(event, "delta", 0) or 0
                if delta:
                    step = -1 if delta > 0 else 1
            if not step:
                return "break"
            if getattr(event, "state", 0) & 0x1:
                canvas.xview_scroll(step, "units")
            else:
                canvas.yview_scroll(step, "units")
            return "break"

        def _bind_popup(widget):
            for seq in ("<MouseWheel>", "<Shift-MouseWheel>",
                        "<Button-4>", "<Button-5>"):
                try:
                    widget.bind(seq, _popup_wheel)
                except tk.TclError:
                    pass
            for child in widget.winfo_children():
                _bind_popup(child)

        win.update_idletasks()
        _bind_popup(win)
        win.update_idletasks()
        want_w = min(self.px(1000), inner.winfo_reqwidth() + self.px(48))
        want_h = min(self.px(660), inner.winfo_reqheight() + self.px(76))
        win.geometry("%dx%d+%d+%d" % (
            max(self.px(460), want_w), max(self.px(360), want_h),
            max(0, self.winfo_rootx() + (self.winfo_width() - want_w) // 2),
            max(0, self.winfo_rooty() + (self.winfo_height() - want_h) // 2)))
        win.transient(self)
        win.lift()
        win.focus_force()
        # 窗口真正映射出来之后再刷两次标题栏配色（第一次调用往往还没生效）
        win.update_idletasks()
        win.update()
        apply_titlebar_color(win)
        win.update()
        apply_titlebar_color(win)

    # ---------------------------------------------------------- 左侧参数区
    def _build_left(self, parent):
        inner = tk.Frame(parent, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=self.px(18), pady=self.px(14))

        buttons = tk.Frame(inner, bg=PANEL)
        buttons.pack(side="bottom", fill="x", pady=(self.px(16), 0))
        self.calc_button = RoundedButton(
            buttons, "开始计算", self.on_calculate, self.px, self.f_btn,
            fill=ACCENT, fg=ON_ACCENT, hover=ACCENT_HI, page_bg=PANEL,
            height=46, hint="Enter 计算", hint_fg=HINT_ON_ACCENT,
            hint_font=self.f_hint)
        self.calc_button.pack(side="left", fill="x", expand=True, padx=(0, self.px(14)))
        self.clear_button = RoundedButton(
            buttons, "清空", self.on_clear, self.px, self.f_btn,
            fill=PANEL, fg=ACCENT, hover=PANEL_HI, page_bg=PANEL,
            height=46, width=140, outline=ACCENT_DIM)
        self.clear_button.pack(side="left")

        self._section(inner, "计算模式")
        self.mode_seg = Segmented(inner, [("normal", "简单模式"), ("precise", "精确模式")],
                                  self.mode_var.get(), self.set_mode, self.px, self.f_btn)
        self.mode_seg.pack(fill="x", pady=(self.px(10), self.px(6)))

        self.mode_hint = tk.Label(inner, text="", bg=PANEL, fg=MUTED, font=self.f_small,
                                  justify="left", anchor="w", wraplength=self.px(360))
        self.mode_hint.pack(fill="x", pady=(0, self.px(8)))

        self._section(inner, "系统总耗电")
        self.total_entry = self._field(inner, self.total_var)

        self._section(inner, "电池种类")
        self.battery_select = BatterySelect(inner, BATTERIES, self.battery_photos,
                                            self.px, self.fonts,
                                            command=self.on_battery_change)
        self.battery_select.pack(fill="x", pady=(self.px(10), self.px(2)))

        if self.missing_images:
            tk.Label(inner,
                     text=f"⚠ 未找到 {len(self.missing_images)} 张电池图片，请确认 resource 文件夹在："
                          f"{resource_dir()}",
                     bg=PANEL, fg=AMBER, font=self.f_small, anchor="w",
                     justify="left", wraplength=self.px(360)).pack(
                fill="x", pady=(self.px(6), 0))

        self._section(inner, "电池获取速率")
        self.slider = StepSlider(inner, RATE_VALUES, 0, self.on_rate_change, self.px,
                                 self.f_num, self.f_num_bold, page_bg=PANEL)
        self.slider.pack(fill="x", pady=(self.px(8), 0))
        self.rate_label = tk.Label(inner, text="", bg=PANEL, fg=ACCENT,
                                   font=self.f_label, anchor="w")
        self.rate_label.pack(fill="x", pady=(self.px(2), 0))

        self.error_label = tk.Label(inner, text="", bg=PANEL, fg=DANGER,
                                    font=self.f_small, anchor="w", justify="left",
                                    wraplength=self.px(360))
        self.error_label.pack(fill="x", pady=(self.px(6), 0))

        self.set_mode("normal")
        self.on_rate_change(RATE_VALUES[0])

    def _section(self, parent, text):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=(self.px(9), 0))
        tk.Frame(row, bg=ACCENT, width=self.px(4), height=self.px(15)).pack(
            side="left", padx=(0, self.px(10)))
        tk.Label(row, text=text, bg=PANEL, fg=TEXT,
                 font=self.f_section).pack(side="left")

    def _field(self, parent, var):
        box = RoundedBox(parent, self.px, radius=R_FIELD, fill=INPUT_BG,
                         outline=BORDER, page_bg=PANEL, inner_pad=1, autosize=True)
        box.pack(fill="x", pady=(self.px(10), self.px(2)))
        entry = tk.Entry(box.body, textvariable=var, bg=INPUT_BG, fg=TEXT,
                         relief="flat", bd=0, font=self.f_entry,
                         insertbackground=ACCENT, highlightthickness=0,
                         selectbackground=ACCENT_DIM, selectforeground=ON_ACCENT)
        entry.pack(fill="x", expand=True, padx=self.px(10), pady=self.px(8))
        entry.bind("<FocusIn>", lambda e: box.set_outline(ACCENT))
        entry.bind("<FocusOut>", lambda e: box.set_outline(BORDER))
        return entry

    # ---------------------------------------------------------- 右侧结果区
    def _make_scrollbar(self, parent, orient="vertical"):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        key = "Vertical" if orient == "vertical" else "Horizontal"
        name = "Theme.%s.TScrollbar" % key
        style.configure(name,
                        background=ACCENT_DIM, troughcolor=PANEL, bordercolor=PANEL,
                        darkcolor=ACCENT_DIM, lightcolor=ACCENT_DIM,
                        arrowcolor=ACCENT, arrowsize=self.px(12),
                        width=self.px(12), relief="flat", borderwidth=0)
        style.map(name,
                  background=[("active", ACCENT), ("pressed", ACCENT_HI)],
                  arrowcolor=[("active", ACCENT_HI)])
        return ttk.Scrollbar(parent, orient=orient, style=name)

    def _build_right(self, parent):
        inner = tk.Frame(parent, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=self.px(26), pady=self.px(24))

        head = tk.Frame(inner, bg=PANEL)
        head.pack(fill="x")
        tk.Frame(head, bg=ACCENT, width=self.px(4), height=self.px(15)).pack(
            side="left", padx=(0, self.px(10)))
        tk.Label(head, text="输出", bg=PANEL, fg=TEXT,
                 font=self.f_section).pack(side="left")

        self.output_seg = Segmented(
            inner, [("result", "计算结果"), ("build", "搭建演示")],
            self.output_mode, self.set_output_mode, self.px, self.f_btn)
        self.output_seg.pack(fill="x", pady=(self.px(12), 0))

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(self.px(12), 0))

        self.view_holder = tk.Frame(inner, bg=PANEL)
        self.view_holder.pack(fill="both", expand=True, pady=(self.px(14), 0))

        # ---------------- 视图一：计算结果 ----------------
        self.result_view = tk.Frame(self.view_holder, bg=PANEL)
        text_box = RoundedBox(self.result_view, self.px, radius=R_FIELD, fill=INPUT_BG,
                              outline=BORDER, page_bg=PANEL, inner_pad=1)
        text_box.pack(fill="both", expand=True)

        text_wrap = tk.Frame(text_box.body, bg=INPUT_BG)
        text_wrap.pack(fill="both", expand=True, padx=self.px(2), pady=self.px(2))

        scrollbar = self._make_scrollbar(text_wrap)
        scrollbar.pack(side="right", fill="y")

        self.text = tk.Text(text_wrap, bg=INPUT_BG, fg=TEXT, relief="flat", bd=0,
                            font=self.f_mono, wrap="word",
                            padx=self.px(18), pady=self.px(14),
                            insertbackground=ACCENT, selectbackground=ACCENT_DIM,
                            selectforeground=ON_ACCENT, state="disabled",
                            yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.text.yview)

        self.text.tag_configure("big", foreground=ACCENT, font=self.f_mono_big,
                                spacing1=self.px(10), spacing3=self.px(10))
        self.text.tag_configure("accent", foreground=ACCENT, font=self.f_mono_b,
                                spacing1=self.px(8), spacing3=self.px(8))
        self.text.tag_configure("body", foreground=TEXT, font=self.f_mono,
                                spacing1=self.px(5), spacing3=self.px(5),
                                lmargin1=self.px(2), lmargin2=self.px(18))
        self.text.tag_configure("muted", foreground=MUTED, font=self.f_mono,
                                spacing1=self.px(4), spacing3=self.px(4),
                                lmargin1=self.px(2), lmargin2=self.px(18))
        self.text.tag_configure("warn", foreground=AMBER, font=self.f_mono,
                                spacing1=self.px(6), spacing3=self.px(6))
        self.text.tag_configure("error", foreground=DANGER, font=self.f_mono_b,
                                spacing1=self.px(6), spacing3=self.px(6))
        self.text.tag_configure("section", foreground=ACCENT_DIM, font=self.f_mono_b,
                                spacing1=self.px(16), spacing3=self.px(8))
        self.text.tag_configure("placeholder", foreground=PLACEHOLDER, font=self.f_mono,
                                justify="center", spacing1=self.px(120))

        # ---------------- 视图二：搭建演示 ----------------
        self.build_view = tk.Frame(self.view_holder, bg=PANEL)
        build_canvas = tk.Canvas(self.build_view, bg=PANEL, highlightthickness=0, bd=0)
        build_sb = self._make_scrollbar(self.build_view)
        build_sb.pack(side="right", fill="y")
        build_canvas.pack(side="left", fill="both", expand=True)
        build_canvas.configure(yscrollcommand=build_sb.set)
        build_sb.configure(command=build_canvas.yview)

        self.build_inner = tk.Frame(build_canvas, bg=PANEL)
        self._build_win = build_canvas.create_window(0, 0, anchor="nw",
                                                     window=self.build_inner)
        self.build_inner.bind(
            "<Configure>",
            lambda e: build_canvas.configure(scrollregion=build_canvas.bbox("all")))
        build_canvas.bind(
            "<Configure>",
            lambda e: build_canvas.itemconfigure(self._build_win, width=e.width))

        # 鼠标滚轮 / 触控板上下滑动
        self._build_canvas = build_canvas

        def _on_wheel(event):
            if not self.build_view.winfo_ismapped():
                return
            delta = 0
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            elif event.delta:
                delta = -1 if event.delta > 0 else 1
            if delta:
                build_canvas.yview_scroll(delta, "units")

        for widget in (build_canvas, self.build_inner):
            widget.bind("<MouseWheel>", _on_wheel)
            widget.bind("<Button-4>", _on_wheel)
            widget.bind("<Button-5>", _on_wheel)
        self._bind_wheel_recursive = _on_wheel

        self.set_output_mode(self.output_mode)

    # ---------------------------------------------------------- 输出模式切换
    def set_output_mode(self, key):
        self.output_mode = "build" if key == "build" else "result"
        if hasattr(self, "output_seg"):
            self.output_seg.set_value(self.output_mode)
        if not hasattr(self, "result_view"):
            return
        self.result_view.pack_forget()
        self.build_view.pack_forget()
        if self.output_mode == "build":
            self.build_view.pack(fill="both", expand=True)
            self._render_build(self._last_info)
        else:
            self.result_view.pack(fill="both", expand=True)

    # ---------------------------------------------------------- 搭建演示渲染
    def _tile(self, name, size="big"):
        tile = getattr(self, "build_tiles", {}).get(name)
        return tile.get(size) if tile else None

    def _build_step(self, parent, tile_name, title, sub, size="big"):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=(self.px(2), 0))
        image = self._tile(tile_name, size)
        if image is not None:
            tk.Label(row, image=image, bg=PANEL, bd=0).pack(
                side="left", padx=(0, self.px(12)))
        else:
            tk.Frame(row, bg=PANEL, width=self.px(52)).pack(side="left",
                                                            padx=(0, self.px(12)))
        col = tk.Frame(row, bg=PANEL)
        col.pack(side="left", fill="x", expand=True)
        tk.Label(col, text=title, bg=PANEL, fg=TEXT, font=self.f_label, anchor="w",
                 justify="left", wraplength=self.px(330)).pack(fill="x")
        if sub:
            tk.Label(col, text=sub, bg=PANEL, fg=MUTED, font=self.f_small, anchor="w",
                     justify="left", wraplength=self.px(330)).pack(fill="x")

    def _build_arrow(self, parent, text="传送带"):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=self.px(1))
        tk.Label(row, text="↓", bg=PANEL, fg=ACCENT,
                 font=self.f_label).pack(side="left", padx=(self.px(46), self.px(6)))
        image = self._tile("build_belt.png", "small")
        if image is not None:
            tk.Label(row, image=image, bg=PANEL, bd=0).pack(side="left",
                                                            padx=(0, self.px(6)))
        tk.Label(row, text=text, bg=PANEL, fg=MUTED,
                 font=self.f_small).pack(side="left")

    def _build_head(self, parent, text, pady=(18, 6)):
        tk.Label(parent, text=text, bg=PANEL, fg=ACCENT_DIM, font=self.f_section,
                 anchor="w").pack(fill="x", pady=(self.px(pady[0]), self.px(pady[1])))

    def _bind_wheel_tree(self, widget):
        """给整个子树绑上滚轮，鼠标停在任意子控件上都能滚动"""
        handler = getattr(self, "_bind_wheel_recursive", None)
        if handler is None:
            return
        try:
            widget.bind("<MouseWheel>", handler)
            widget.bind("<Button-4>", handler)
            widget.bind("<Button-5>", handler)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_wheel_tree(child)

    def _render_build(self, info):
        parent = self.build_inner
        for child in parent.winfo_children():
            child.destroy()

        if not info:
            tk.Label(parent, text="先在左侧填写参数并计算，\n这里会给出对应的游戏内搭建方法。",
                     bg=PANEL, fg=PLACEHOLDER, font=self.f_mono, justify="left",
                     anchor="w", wraplength=self.px(400)).pack(fill="x",
                                                               pady=(self.px(30), 0))
            return

        rate = info["rate"]
        model = info["model"]
        interval = info["interval"]

        # ---- 摘要 ----
        if info["mode"] == "simple":
            parts = []
            if info["pow2"]:
                parts.append(f"{info['pow2']} 个二分")
            if info["pow3"]:
                parts.append(f"{info['pow3']} 个三分")
            summary = "串联 " + " + ".join(parts) if parts else "无需分流"
            factor_line = f"总速率 ×1/{info['result']}"
        else:
            summary = "串联 " + " + ".join(
                f"{c} 个 {p} 分" for p, c in info["factors"].items())
            factor_line = "总速率 ×1/" + str(math.prod(
                p ** c for p, c in info["factors"].items()))

        box = RoundedBox(parent, self.px, radius=R_FIELD, fill=INPUT_BG,
                         outline=BORDER, page_bg=PANEL, inner_pad=1, autosize=True)
        box.pack(fill="x", pady=(0, self.px(4)))
        head = tk.Frame(box.body, bg=INPUT_BG)
        head.pack(fill="x", padx=self.px(14), pady=self.px(10))
        tk.Label(head, text=summary, bg=INPUT_BG, fg=ACCENT, font=self.f_label,
                 anchor="w", justify="left", wraplength=self.px(380)).pack(fill="x")
        tk.Label(head, text=f"{factor_line}　·　目标间隔 {fmt_num(interval)} 秒",
                 bg=INPUT_BG, fg=MUTED, font=self.f_small, anchor="w",
                 justify="left", wraplength=self.px(380)).pack(fill="x")

        self._build_head(parent, "网格蓝图")
        bp = build_blueprint(info)
        if bp is None:
            tk.Label(parent, text="当前参数不需要分流，直接把取货口接进热能池即可。",
                     bg=PANEL, fg=MUTED, font=self.f_small, anchor="w",
                     justify="left", wraplength=self.px(390)).pack(fill="x")
        else:
            head = tk.Frame(parent, bg=PANEL)
            head.pack(fill="x", pady=(0, self.px(6)))
            tk.Label(head, text=f"{bp.cols} 列 × {bp.rows} 行 · 箭头就是电池流向",
                     bg=PANEL, fg=MUTED, font=self.f_small).pack(side="left")
            zoom = tk.Label(head, text="放大查看 ↗", bg=PANEL, fg=ACCENT,
                            font=self.f_small, cursor="hand2")
            zoom.pack(side="right")
            zoom.bind("<Button-1>", lambda e: self.open_blueprint_window())
            holder = tk.Frame(parent, bg=PANEL)
            holder.pack(fill="x")
            self._draw_blueprint(holder, bp)

            tk.Label(parent,
                     text=f"输入 {rate} 个/分钟（每 {fmt_num(model)} 秒 1 个）"
                          f"　·　热能池每 {fmt_num(info.get('actual_interval', interval))} 秒进 1 个",
                     bg=PANEL, fg=MUTED, font=self.f_small, anchor="w",
                     justify="left", wraplength=self.px(390)).pack(
                         fill="x", pady=(self.px(6), 0))

        self._bind_wheel_tree(self.build_inner)

    # ---------------------------------------------------------- 主题切换
    def switch_theme(self, name):
        if name == self.theme_name:
            return
        self.theme_name = name
        apply_theme(name)
        self._rebuild()

    def _rebuild(self):
        """切换主题后重建界面（保留输入与结果）"""
        battery_index = self.battery_select.index
        rate_index = self.slider.index
        mode = self.mode_var.get()

        for child in self.winfo_children():
            child.destroy()
        self.configure(bg=BG)

        self._build_header()
        self._build_body()

        self.battery_select.set_index(battery_index, notify=False)
        self.slider.set_index(rate_index)
        self.set_mode(mode)
        self.on_rate_change(RATE_VALUES[rate_index])

        if self._last_segments:
            self._render(self._last_segments)
        else:
            self.show_placeholder()

        apply_titlebar_color(self)

    # ---------------------------------------------------------- 逻辑
    def set_mode(self, key):
        self.mode_var.set(key)
        if hasattr(self, "mode_seg"):
            self.mode_seg.set_value(key)
        if key == "precise":
            self.mode_hint.configure(text="精确模式：对比例做质因数分解，给出可精确复现的配方。")
        else:
            self.mode_hint.configure(text="简单模式：用 2 分与 3 分电池的组合逼近理论比例。")

    def on_rate_change(self, rate):
        self.rate_label.configure(text=f"{rate} 个/分钟 · 每 {fmt_num(60.0 / rate)} 秒 1 个")

    def on_battery_change(self, item):
        if self._parse_total() is not None:
            self.on_calculate()

    def _render(self, segments):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for content, tag in segments:
            self.text.insert("end", content + "\n", (tag,))
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def show_placeholder(self):
        self._last_segments = None
        self._last_info = None
        self._render([("在左侧填写参数后，点击「开始计算」", "placeholder")])
        if getattr(self, "output_mode", "result") == "build" and hasattr(self, "build_inner"):
            self._render_build(None)

    def _fail(self, message):
        self._last_segments = None
        self._last_info = None
        self.error_label.configure(text=message)
        self._render([(message, "error")])
        if getattr(self, "output_mode", "result") == "build" and hasattr(self, "build_inner"):
            self._render_build(None)

    def _parse_total(self):
        raw = self.total_var.get().strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        if value <= 0:
            return None
        # 游戏内每台设备的耗电量都是 5 的整数倍，总耗电必然也是 5 的倍数；
        # 不是 5 的倍数说明填错了，向下取到最近的 5 的倍数再算
        if abs(value - round(value)) > 1e-9:
            return None
        value = int(round(value))
        if value % 5:
            value -= value % 5
            if value <= 0:
                return None
        return value

    def on_calculate(self):
        self.error_label.configure(text="")
        battery = self.battery_select.current

        if not self.total_var.get().strip():
            self._fail("请填写「系统总耗电」。")
            self.total_entry.focus_set()
            return

        total_power = self._parse_total()
        if total_power is None:
            self._fail("「系统总耗电」需要是大于 0 的整数，例如 1500。")
            self.total_entry.focus_set()
            return
        # 游戏内设备耗电都是 5 的倍数，总耗电也必然是 5 的倍数：自动对齐并回填
        typed = self.total_var.get().strip()
        if typed not in (str(total_power), str(total_power) + ".0"):
            self.total_var.set(str(total_power))

        battery_output = float(battery["power"])
        rate = RATE_VALUES[self.slider.index]
        precise = self.mode_var.get() == "precise"

        segments, summary, info = calculate(total_power, battery_output, rate, precise)
        segments.insert(0, (f"{battery['name']} · 每秒发电 {battery['power']} 单位", "muted"))
        self._last_segments = segments
        self._last_info = info
        self._render(segments)
        if getattr(self, "output_mode", "result") == "build":
            self._render_build(info)

    def on_clear(self):
        self.total_var.set("")
        self.battery_select.set_index(0, notify=False)
        self.slider.set_index(0)
        self.on_rate_change(RATE_VALUES[0])
        self.set_mode("normal")
        self.error_label.configure(text="")
        self.show_placeholder()
        self.total_entry.focus_set()

    # ---------------------------------------------------------- 关闭确认
    def on_close_request(self):
        already_minimized = (self.state() == "iconic")

        if self.close_action == "quit":
            self.destroy()
            return
        if self.close_action == "minimize":
            if already_minimized:
                self.destroy()
            else:
                self.iconify()
            return

        if self._close_dialog_open:
            self.destroy()
            return

        self._close_dialog_open = True
        try:
            if self.state() != "normal":
                self.deiconify()
            self.update_idletasks()
            self.lift()
            dialog = self._build_close_dialog()
            self.wait_window(dialog)
        finally:
            self._close_dialog_open = False

    def _build_close_dialog(self):
        px = self.px
        dlg = tk.Toplevel(self)
        dlg.title("关闭窗口")
        dlg.configure(bg=PANEL)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        tk.Frame(dlg, bg=ACCENT, height=px(4)).pack(fill="x")

        body = tk.Frame(dlg, bg=PANEL)
        body.pack(fill="both", expand=True, padx=px(28), pady=px(24))
        tk.Label(body, text="要退出应用吗？", bg=PANEL, fg=TEXT,
                 font=self.f_section).pack(anchor="w")
        tk.Label(body, text="可以退出程序，也可以最小化到任务栏继续后台运行。",
                 bg=PANEL, fg=MUTED, font=self.f_small).pack(
            anchor="w", pady=(px(10), px(16)))

        remember = tk.BooleanVar(value=False)
        tk.Checkbutton(body, text="本次运行不再提示（重启程序后恢复询问）",
                       variable=remember, bg=PANEL, fg=MUTED,
                       activebackground=PANEL, activeforeground=TEXT,
                       selectcolor=INPUT_BG, font=self.f_small,
                       bd=0, highlightthickness=0, anchor="w",
                       cursor="hand2", padx=0, pady=0).pack(fill="x", pady=(0, px(18)))

        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x")
        RoundedButton(row, "退出应用", lambda: self._quit_app(dlg, remember.get()),
                      px, self.f_btn, fill=ACCENT, fg=ON_ACCENT, hover=ACCENT_HI,
                      page_bg=PANEL, height=56, width=150).pack(side="right")
        RoundedButton(row, "最小化到任务栏",
                      lambda: self._hide_app(dlg, remember.get()),
                      px, self.f_btn, fill=PANEL, fg=ACCENT, hover=PANEL_HI,
                      page_bg=PANEL, height=56, width=200,
                      outline=ACCENT_DIM).pack(side="right", padx=(0, px(12)))
        RoundedButton(row, "取消", dlg.destroy, px, self.f_btn, fill=PANEL,
                      fg=MUTED, hover=PANEL_HI, page_bg=PANEL, height=56,
                      width=120, outline=BORDER).pack(side="right", padx=(0, px(12)))

        dlg.update_idletasks()
        width, height = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        x = self.winfo_rootx() + (self.winfo_width() - width) // 2
        y = self.winfo_rooty() + (self.winfo_height() - height) // 3
        dlg.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
        apply_titlebar_color(dlg)
        try:
            dlg.grab_set()
        except tk.TclError:
            pass
        dlg.lift()
        dlg.focus_force()
        return dlg

    def _remember_close_action(self, action, remember):
        """勾选了「本次运行不再提示」才记住，且只存在内存里，重启即失效"""
        if remember:
            self.close_action = action

    def _quit_app(self, dialog, remember=False):
        self._remember_close_action("quit", remember)
        dialog.destroy()
        self.destroy()

    def _hide_app(self, dialog, remember=False):
        self._remember_close_action("minimize", remember)
        dialog.destroy()
        self.iconify()


def main():
    enable_dpi_awareness()
    hide_console_window()
    install_crash_dialog()
    BatteryApp().mainloop()


if __name__ == "__main__":
    main()
