#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
101b_flow_tiff.py — 将 101 号脚本产出的 SVG 光栅化为 SAGE 投稿用 300 dpi TIFF

流程（Windows 上 cairosvg 不可用 —— 缺 libcairo-2.dll，故走无头浏览器路线）:
  1. 读取 data/moran_lisa_flow_v1.3.svg，包一层零边距 HTML（svg 定宽 2008px）
  2. agent-browser（无头 Chromium）: open → set viewport 2008x1568 → wait →
     screenshot → close
     ⚠ 顺序坑: 必须先 open 再 set viewport —— 导航会重置视口，
     先设视口后导航会拿到默认视口的截图（1258x566）
     ⚠ Git Bash 坑: agent-browser 的 bash 包装脚本在 PATH 降级环境下
     （dirname/sed 缺失）不可用，直接调用原生 exe
  3. PIL: PNG → TIFF，dpi=(300,300)，LZW 无损压缩
  4. 校验尺寸与物理毫米宽度（170 mm @300 dpi ⇒ 2008 px）

用法:
    python scripts/101b_flow_tiff.py
可选环境变量:
    AGENT_BROWSER_EXE  agent-browser 原生可执行文件路径
                       （默认指向本机 WorkBuddy 内置安装位置）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

from PIL import Image  # noqa: E402

SVG = paths.DATA / "moran_lisa_flow_v1.3.svg"
TIFF = paths.DATA / "moran_lisa_flow_v1.3_sage_170mm_300dpi.tiff"

# SAGE 版式: 170 mm 宽 @ 300 dpi = 2008 px; viewBox 1040x812 ⇒ 高 1568 px
PX_W, PX_H = 2008, 1568
DPI = 300

DEFAULT_EXE = (
    r"C:\Users\Hannah\.workbuddy\binaries\node\versions\22.22.2-3"
    r"\node_modules\agent-browser\bin\agent-browser-win32-x64.exe"
)


def find_agent_browser() -> str:
    exe = os.environ.get("AGENT_BROWSER_EXE", DEFAULT_EXE)
    if Path(exe).exists():
        return exe
    on_path = shutil.which("agent-browser")
    if on_path:
        return on_path
    raise SystemExit(
        "找不到 agent-browser 可执行文件。\n"
        "请安装 agent-browser（npm install -g agent-browser），或设环境变量\n"
        "AGENT_BROWSER_EXE 指向原生 exe（agent-browser-win32-x64.exe）。"
    )


HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;background:#ffffff;width:{w}px;height:{h}px;overflow:hidden}}
  svg{{display:block;width:{w}px;height:{h}px}}
</style></head>
<body>
{svg}
</body></html>
"""


def main() -> None:
    if not SVG.exists():
        raise SystemExit(f"缺少输入 {SVG}，请先运行 python scripts/101_lisa_flow_map.py")

    ab = find_agent_browser()

    # 1. 写临时 HTML（UTF-8，内联 SVG，无外部资源 ⇒ file:// 可直接加载）
    svg_text = SVG.read_text(encoding="utf-8")
    html_path = Path(tempfile.gettempdir()) / "moran_lisa_flow_v1_3_render.html"
    html_path.write_text(HTML.format(w=PX_W, h=PX_H, svg=svg_text), encoding="utf-8")

    png_path = Path(tempfile.gettempdir()) / "moran_lisa_flow_v1_3_2008px.png"

    # 2. 无头浏览器截图 —— 顺序不可颠倒：open 必须在 set viewport 之前
    # ⚠ 坑: 不要用 capture_output=True —— agent-browser 的常驻 daemon 会继承
    #   stdout 管道，subprocess.run 等不到 EOF 而挂起，须让其直接继承终端
    cmds = [
        [ab, "open", html_path.as_uri()],
        [ab, "set", "viewport", str(PX_W), str(PX_H)],
        [ab, "wait", "800"],
        [ab, "screenshot", str(png_path)],
        [ab, "close"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, timeout=120)
        if r.returncode != 0:
            raise SystemExit(f"agent-browser 步骤失败: {' '.join(cmd[1:])}")
        print(f"  [ok] {' '.join(cmd[1:])}")

    # 3. PNG → 300 dpi LZW TIFF
    img = Image.open(png_path)
    if img.size != (PX_W, PX_H):
        raise SystemExit(f"截图尺寸异常 {img.size}，期望 {(PX_W, PX_H)}（视口被重置？）")
    img.save(TIFF, format="TIFF", dpi=(DPI, DPI), compression="tiff_lzw")

    # 4. 回读校验
    chk = Image.open(TIFF)
    mm_w = chk.size[0] / DPI * 25.4
    print(f"TIFF: {chk.size} dpi={chk.info.get('dpi')} "
          f"compression={chk.info.get('compression')}")
    print(f"物理尺寸: {mm_w:.1f} mm 宽（SAGE 要求 170 mm）")
    print(f"输出: {TIFF}（{TIFF.stat().st_size/1024:.0f} KB）")

    # 清理临时文件
    for p in (html_path, png_path):
        try:
            p.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
