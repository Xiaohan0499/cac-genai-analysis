#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
102_reproduce_submission_figure.py — 一键复现投稿图：Moran 分析 → LISA/调用流图 → 300 dpi TIFF

一条命令跑完从原始数据到 SAGE 投稿级 Figure 的完整链路：

  阶段 A  Moran 分析        99_moran_log_knn5.py
          输入  data/cac_genai_product_entity_map_v1.2.csv（桥表）
                data/cac_genai_entity_enriched_v1.2.csv（表2）
                geo/china_city_coords_v1.0.csv（质心）
          输出  data/moran_log_global_v1.0.csv   全局 Moran（ln 口径 + 原始对照）
                data/moran_log_local_v1.0.csv    局部 LISA（298 市 × 2 口径）
                data/qa_report_moran_log.txt     6 项体检 + 摘要

  阶段 B  作图（矢量）      101_lisa_flow_map.py
          输入  上述局部结果 + data/cac_genai_app_model_edges_v1.2.csv（表3）
          输出  data/moran_lisa_flow_v1.3.svg   SAGE 170 mm 宽版式母版

  阶段 C  出版位图          101b_flow_tiff.py
          输出  data/moran_lisa_flow_v1.3_sage_170mm_300dpi.tiff
                2008×1568 px，300 dpi，LZW，物理 170.0 mm × 132.8 mm

每阶段结束自动校验（任一失败即退出码 1）：
  A  I = +0.1737 ± 0.0005、z = +5.26 ± 0.05、p ≤ 0.001；HH 18 / LH 7 / LL 0 / HL 0 / 不显著 273
  B  左面板单一 5° 格网（无重线、无 2°/3° 碎格 —— v1.3 双底图 bug 回归项）；
     全部文字在画布内、两两不重叠、字号 ≥ 15.5 units（= 7.18 pt）
  C  TIFF 2008×1568、dpi=300、宽 170.0 mm

用法:
    python scripts/102_reproduce_submission_figure.py             # 全链路（A→B→C）
    python scripts/102_reproduce_submission_figure.py --skip-moran # 复用已有 Moran 结果，只重出图
    python scripts/102_reproduce_submission_figure.py --skip-tiff  # 只出 SVG，不转 TIFF
    python scripts/102_reproduce_submission_figure.py --qa-only    # 只体检现有产物

依赖: numpy、pandas（A/B）；Pillow + agent-browser（C，见 101b_flow_tiff.py）
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import paths  # noqa: E402

SVG = paths.DATA / "moran_lisa_flow_v1.3.svg"
TIFF = paths.DATA / "moran_lisa_flow_v1.3_sage_170mm_300dpi.tiff"
GLOBAL_CSV = paths.DATA / "moran_log_global_v1.0.csv"
LOCAL_CSV = paths.DATA / "moran_log_local_v1.0.csv"

# ---- 已定稿数值（数据 v1.2 rev5 口径；任何漂移都说明输入变了，必须人工确认） ----
EXPECT = dict(i=0.173698, z=5.258, p=0.001, n=298,
              hh=18, lh=7, hl=0, ll=0, nosig=273,
              i_raw=0.031370, p_raw=0.061)
TOL_I, TOL_Z = 5e-4, 5e-2

PX_W, PX_H, DPI, MM_TARGET = 2008, 1568, 300, 170.0
MIN_FS = 15.4  # SVG units；15.5 units × 0.4634 = 7.18 pt ≥ SAGE 7 pt 下限


def load_mod(alias: str, filename: str):
    """按文件路径加载以数字开头的脚本模块（无法常规 import）。"""
    spec = importlib.util.spec_from_file_location(alias, SCRIPT_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def banner(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


# ---------------------------------------------------------------- 阶段 A
def stage_moran() -> None:
    banner("阶段 A / Moran 分析（99_moran_log_knn5.py）")
    m99 = load_mod("m99", "99_moran_log_knn5.py")
    rc = m99.main()
    if rc not in (0, None):
        raise SystemExit(f"!! 99 号脚本返回 {rc}")


def qa_moran() -> None:
    import pandas as pd

    g = pd.read_csv(GLOBAL_CSV, encoding="utf-8-sig")
    ln = g[(g["variable"] == "ln1p_merged_filings") & (g["weights"] == "knn5")].iloc[0]
    raw = g[(g["variable"] == "merged_filings") & (g["weights"] == "knn5")].iloc[0]

    assert int(ln["n_units"]) == EXPECT["n"], f"单元数 {ln['n_units']} ≠ {EXPECT['n']}"
    assert abs(ln["moran_i"] - EXPECT["i"]) < TOL_I, \
        f"全局 I={ln['moran_i']:.6f} 偏离定稿值 {EXPECT['i']}（输入数据变了？）"
    assert abs(ln["z_sim"] - EXPECT["z"]) < TOL_Z, f"z={ln['z_sim']:.3f} 偏离 {EXPECT['z']}"
    assert ln["p_sim_two_sided"] <= EXPECT["p"] + 1e-12, f"p={ln['p_sim_two_sided']} 应为 0.001"
    assert abs(raw["moran_i"] - EXPECT["i_raw"]) < TOL_I, "原始计数对照 I 偏离"
    assert abs(raw["p_sim_two_sided"] - EXPECT["p_raw"]) < 5e-3, "原始计数对照 p 偏离"

    loc = pd.read_csv(LOCAL_CSV, encoding="utf-8-sig")
    sub = loc[loc["variable"] == "ln1p_merged_filings"]
    assert len(sub) == EXPECT["n"], f"局部结果 {len(sub)} 行 ≠ {EXPECT['n']}"
    cnt = sub["cluster_p05"].value_counts().to_dict()
    for k, exp in (("HH", EXPECT["hh"]), ("LH", EXPECT["lh"]),
                   ("HL", EXPECT["hl"]), ("LL", EXPECT["ll"]),
                   ("不显著", EXPECT["nosig"])):
        got = int(cnt.get(k, 0))
        assert got == exp, f"{k} 市数 {got} ≠ {exp}"

    print(f"QA-A 全局 I={ln['moran_i']:.4f} z={ln['z_sim']:.2f} p={ln['p_sim_two_sided']:.3f}"
          f"；LISA HH {EXPECT['hh']} / LH {EXPECT['lh']} / 不显著 {EXPECT['nosig']} —— 与定稿一致 PASS")


# ---------------------------------------------------------------- 阶段 B
def stage_figure() -> None:
    banner("阶段 B / 作图（101_lisa_flow_map.py → SVG 母版）")
    m101 = load_mod("m101", "101_lisa_flow_map.py")
    rc = m101.main()
    if rc not in (0, None):
        raise SystemExit(f"!! 101 号脚本返回 {rc}")


def qa_svg() -> None:
    """文本越界/重叠/字号 + 左面板格网规整性（v1.3 双底图 bug 回归项）。"""
    assert SVG.exists(), f"缺少 {SVG}"
    svg = SVG.read_text(encoding="utf-8")

    texts = []
    for m in re.finditer(r'<text ([^>]+)>([^<]+)</text>', svg):
        at, t = m.group(1), m.group(2)

        def attr(k, at=at):
            mm = re.search(k + r'="([^"]+)"', at)
            return mm.group(1) if mm else None

        texts.append((float(attr("x")), float(attr("y")), float(attr("font-size")),
                      attr("text-anchor") or "start", t))

    # 字号：全部 ≥ 7 pt 等效（SAGE 要求）
    tiny = [(t, fs) for _, _, fs, _, t in texts if fs < MIN_FS]
    assert not tiny, f"存在小于 7 pt 的文字: {tiny[:3]}"

    # 越界：粗估字宽（8.4 units / 字 @15.5pt）
    W = 8.4

    def box(x, y, fs, a, t):
        w = W * len(t) * (fs / 15.5)
        x0 = x - w if a == "end" else (x - w / 2 if a == "middle" else x)
        return [x0, y - fs * 0.78, x0 + w, y + fs * 0.22]

    oob = [(t, round(box(x, y, fs, a, t)[0]), round(box(x, y, fs, a, t)[2]))
           for x, y, fs, a, t in texts
           if box(x, y, fs, a, t)[0] < -0.5 or box(x, y, fs, a, t)[2] > 1040.5
           or box(x, y, fs, a, t)[3] > 812.5]
    assert not oob, f"文字越界: {oob[:3]}"

    bs = [box(x, y, fs, a, t) for x, y, fs, a, t in texts]
    dup = []
    for i, b1 in enumerate(bs):
        for j in range(i + 1, len(bs)):
            b2 = bs[j]
            if b1[0] < b2[2] and b2[0] < b1[2] and b1[1] < b2[3] and b2[1] < b1[3]:
                dup.append((texts[i][4][:24], texts[j][4][:24]))
    assert not dup, f"文字重叠: {dup[:3]}"

    # 格网回归：复用 101 的断言函数（两套格网叠加会在此失败）
    m101 = load_mod("m101_qa", "101_lisa_flow_map.py")
    m101.qa_grid_lattice(svg)

    deg = sorted({t for _, _, _, _, t in texts if "°" in t})
    assert len(deg) >= 10, f"度数标签仅 {len(deg)} 个，疑似缺失"
    print(f"QA-B 文字 {len(texts)} 个：零越界、零重叠，最小字号 "
          f"{min(t[2] for t in texts):.1f} units（= "
          f"{min(t[2] for t in texts) * 0.4634:.2f} pt）；度数标签 {len(deg)} 个 PASS")


# ---------------------------------------------------------------- 阶段 C
def stage_tiff() -> None:
    banner("阶段 C / 出版位图（101b_flow_tiff.py → 300 dpi TIFF）")
    m101b = load_mod("m101b", "101b_flow_tiff.py")
    m101b.main()


def qa_tiff() -> None:
    from PIL import Image

    assert TIFF.exists(), f"缺少 {TIFF}"
    im = Image.open(TIFF)
    assert im.size == (PX_W, PX_H), f"TIFF 尺寸 {im.size} ≠ {(PX_W, PX_H)}"
    dpi = im.info.get("dpi", (0, 0))
    assert abs(dpi[0] - DPI) < 1 and abs(dpi[1] - DPI) < 1, f"dpi={dpi} ≠ 300"
    mm = im.size[0] / DPI * 25.4
    assert abs(mm - MM_TARGET) < 0.3, f"物理宽度 {mm:.1f} mm ≠ 170 mm"
    print(f"QA-C TIFF {im.size[0]}×{im.size[1]} px，{float(dpi[0]):.0f} dpi，{mm:.1f} mm 宽，"
          f"{im.info.get('compression')} —— 符合 SAGE PASS")


# ---------------------------------------------------------------- main
def main() -> int:
    # 子进程（agent-browser）直接写 stdout，须关掉块缓冲以保证日志顺序
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(
        description="一键复现投稿图：Moran 分析 → LISA/调用流图 → 300 dpi TIFF")
    ap.add_argument("--skip-moran", action="store_true", help="复用已有 Moran 结果，跳过阶段 A")
    ap.add_argument("--skip-tiff", action="store_true", help="只出 SVG，跳过阶段 C")
    ap.add_argument("--qa-only", action="store_true", help="不重算，只体检现有产物")
    args = ap.parse_args()

    t0 = time.time()

    if not args.qa_only:
        if args.skip_moran:
            print("· 跳过阶段 A（复用现有 Moran 结果）")
            qa_moran()
        else:
            stage_moran()
            qa_moran()

        stage_figure()
        qa_svg()

        if args.skip_tiff:
            print("· 跳过阶段 C（按 --skip-tiff）")
        else:
            stage_tiff()
            qa_tiff()
    else:
        qa_moran()
        if SVG.exists():
            qa_svg()
        if TIFF.exists():
            qa_tiff()

    banner(f"完成，用时 {time.time() - t0:.1f}s")
    for p in (GLOBAL_CSV, LOCAL_CSV, SVG, TIFF):
        if p.exists():
            print(f"  {p.name:52s} {p.stat().st_size:9,d} B  sha256 {sha256(p)[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
