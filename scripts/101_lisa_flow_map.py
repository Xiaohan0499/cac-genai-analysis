#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
101_lisa_flow_map.py — LISA 集聚 + 跨城调用流（经纬网格 flow map）

v1.3 变更（用户指出：Mainland China 底图"两张底图叠在一起"）:
  - 根因：次要网格从 LON_MIN=72 / LAT_MIN=16 起按 5° 步进（72,77,82...；
    16,21,26...），主网格却锚在 10° 倍数（80,90,...；20,30,...）。两套格网
    锚点不同 ⇒ 同一面板出现 2°/3° 碎格、以及 20°/21° 这类相距 1° 的近重合
    双线，视觉上就是"两张底图叠加"。v1.1（无 main 线）与 v1.2（补 10° 线后）
    均受此影响，v1.2 因加了主网格而暴露。
  - 修复：次要线与主要线统一锚在 5° 全局格点 —— 次要 = 5° 倍数且非 10° 倍数，
    主要 = 10° 倍数。左面板得到规整的 5° 方格（每 10° 加粗并标度数）。
  - 右侧海外面板本就锚在 15°/30°（经）与 10°/20°（纬）全局格点，无需改动。

v1.2 相对 v1.1 的变更（保留）:
  1. 左面板补经纬度标注（v1.1 起点错位导致 major 线与度数标签从未绘制）
  2. SAGE 通用图像规范重排：
     - 画布 1040×812 units，对应 170 mm 宽 @300 dpi（2008×1568 px）
     - 城市标签 15.5 units = 7.2 pt（≥7 pt 下限；比例 2008px/1040units）
     - 全部图内文字 ≥15.5 units（≥7.2 pt）
     - 29 个在图标签在 7pt 下无法放进密集集聚区：改为图内仅保留 15 个
       空间分散的主城市标签，全部 HH/LH 集聚带成员移入底部三行
       集聚带图例（BTH/YRD/PRD，成员带度数），与 LISA 图例同排
     - 标记半径 / 弧线宽度 / 引线线宽 ×1.6 同步放大
  3. 产出两个文件：SVG 矢量母版 + 300 dpi TIFF（TIFF 由辅助脚本
     101b_flow_tiff.py 经无头浏览器光栅化生成，本脚本只产 SVG）

v1.1 相对 v1.0 的变更（保留）:
  - 全英文单版；海外调用流跨面板 OD 弧线（15 对 46 边全额绘制）；
    城市名后缀总度数（自环计 1）

设计不变项:
  - 底图均为纯经纬网格（无行政边界、无海岸线，非地图，规避审查风险）
  - 左右两 panel 比例尺不同（图内注明）
  - LISA 形状+颜色双编码（HH=圆、LH=菱形、HL=三角、LL=方块，黑白可辨）
  - 左面板国内弧线仅绘 ≥5 条边的 OD 对（16 对）；线宽 ∝ 边数（对数）

口径与数据（只读输入）:
  - data/cac_genai_app_model_edges_v1.2.csv  表3：778 条调用边（含两端城市坐标）
  - data/moran_log_local_v1.0.csv            99 号脚本的 LISA 局部结果（ln 口径）
  - geo/china_city_coords_v1.0.csv            城市质心经纬度（WGS84）

输出（幂等，字节确定）:
  - data/moran_lisa_flow_v1.3.svg  SAGE 170mm 版式母版（矢量）

用法:
    python scripts/101_lisa_flow_map.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

import paths

IN_LOCAL = paths.DATA / "moran_log_local_v1.0.csv"
IN_EDGES = paths.EDGES
OUT = paths.DATA / "moran_lisa_flow_v1.3.svg"

# ---- 画布与两面板几何（等经纬度直线示意投影；两面板比例尺不同） ----
# SAGE 版式：170 mm 宽 @300 dpi = 2008 px ⇒ 2008/1040 = 1.931 px/unit，
# 文字 pt = units × 1.931/4.1667 = units × 0.4634 ⇒ 15.5 units = 7.18 pt ≥ 7 pt
VB_W, VB_H = 1040, 812
X0, Y0, PW, PH = 48, 96, 470, 456          # 左：中国大陆（48..518, 96..552）
LON_MIN, LON_MAX = 72.0, 136.0
LAT_MIN, LAT_MAX = 16.0, 57.0
XR, YR, PWR, PHR = 598, 96, 430, 430        # 右：海外（598..1028, 96..526）
OLON_MIN, OLON_MAX = -130.0, 155.0
OLAT_MIN, OLAT_MAX = -40.0, 57.0

FS_TITLE, FS_SUB = 26, 16          # 主标题 12.0pt / 面板副题 7.4pt
FS_CITY = 15.5                     # 城市标签 7.18pt（≥7pt 下限）
FS_SMALL = 15.5                    # 其余图内文字统一 7.18pt
FS_BOLD = 15.5                     # 底部图例行

C_BG = "#FFFFFF"
C_PLOT = "#FCFCFA"
C_GRID = "#E3E1DA"
C_TEXT = "#26215C"
C_TEXT2 = "#8A877F"
C_NOSIG = "#C9C7BF"
C_HH = "#E24B4A"
C_ARC = "#5C4B8A"      # 调用流弧线（紫靛）
C_DEST = "#4A3D73"     # 海外模型城节点
CLUSTER_COLOR = {"HH": "#E24B4A", "LH": "#F0997B", "HL": "#EF9F27", "LL": "#378ADD"}
FONT = "'Segoe UI', Arial, sans-serif"

MIN_EDGES = 5  # 左面板国内 OD 弧线阈值

# 旧金山湾区四城合并为一个节点（左图比例尺下彼此亚像素重叠）
BAY_AREA = {"San Francisco", "Mountain View", "Palo Alto", "Menlo Park"}
BAY_EN = "SF Bay Area"
BAY_LON, BAY_LAT = -122.4194, 37.7749  # 以旧金山为节点锚点

# 跨面板弧线按目的地的拱起系数（分离同源平行弧线）
BOW_DEST = {"SF Bay Area": 0.10, "Seattle": 0.32, "New York": 0.18,
            "Cologne": 0.26, "Freiburg": 0.40, "Sydney": 0.16}


def X(lon: float) -> float:
    return X0 + (lon - LON_MIN) * PW / (LON_MAX - LON_MIN)


def Y(lat: float) -> float:
    return Y0 + (LAT_MAX - lat) * PH / (LAT_MAX - LAT_MIN)


def OX(lon: float) -> float:
    return XR + (lon - OLON_MIN) * PWR / (OLON_MAX - OLON_MIN)


def OY(lat: float) -> float:
    return YR + (OLAT_MAX - lat) * PHR / (OLAT_MAX - OLAT_MIN)


def flow_width(n: int) -> float:
    """OD 弧线线宽 ∝ 边数（对数刻度）；×1.6 适配 170mm 版式。"""
    return 1.4 + 3.8 * math.log10(n + 1)


# ---- 图内标注城市（空间分散的 15 个主城市；集聚带其余成员移至底部图例） ----
# 偏移 (dx, dy, anchor)：相对城市质心；字号 FS_CITY
LABELS = {
    "北京市":   (-22, -24, "end"),
    "天津市":   (-22, 10, "end"),
    "哈尔滨市": (18, -8, "start"),
    "大连市":   (18, -16, "start"),
    "烟台市":   (18, 6, "start"),
    "南京市":   (-22, -6, "end"),
    "上海市":   (16, -6, "start"),
    "杭州市":   (14, 18, "start"),
    "广州市":   (-16, 6, "end"),
    "深圳市":   (14, 8, "start"),
    "成都市":   (-16, -10, "end"),
    "重庆市":   (-16, 18, "end"),
    "昆明市":   (-16, 10, "end"),
    "长沙市":   (10, 20, "start"),
    "湛江市":   (10, 10, "start"),
}

EN_CITY = {
    "北京市": "Beijing", "天津市": "Tianjin", "哈尔滨市": "Harbin",
    "大连市": "Dalian", "烟台市": "Yantai", "南京市": "Nanjing",
    "上海市": "Shanghai", "杭州市": "Hangzhou", "广州市": "Guangzhou",
    "深圳市": "Shenzhen", "成都市": "Chengdu", "重庆市": "Chongqing",
    "昆明市": "Kunming", "长沙市": "Changsha", "湛江市": "Zhanjiang",
}

# ---- 三大集聚带成员（底部图例行；HH/LH 全部显著城市应恰好覆盖） ----
CLUSTERS = [
    ("Beijing-Tianjin-Hebei cluster",
     [("HH", ["Beijing", "Tianjin", "Tangshan", "Zhangjiakou", "Chengde"]),
      ("LH", ["Langfang"])]),
    ("Yangtze River Delta cluster",
     [("HH", ["Shanghai", "Suzhou", "Wuxi", "Changzhou", "Zhenjiang",
              "Nantong", "Jiaxing", "Huzhou", "Ningbo"]),
      ("LH", ["Zhoushan", "Shaoxing", "Maanshan", "Xuancheng"])]),
    ("Pearl River Delta cluster",
     [("HH", ["Guangzhou", "Shenzhen", "Zhuhai", "Dongguan"]),
      ("LH", ["Zhongshan", "Huizhou"])]),
]


def marker(kind: str, cx: float, cy: float, r: float, fill: str) -> str:
    """集聚类型 → SVG 图形：HH=圆、LH=菱形、HL=三角、LL=正方形（黑白可辨）。"""
    st = f'fill="{fill}" fill-opacity="0.85" stroke="#FFFFFF" stroke-width="1.3"'
    if kind == "HH":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" {st}/>'
    if kind == "LH":
        pts = f"{cx:.1f},{cy-r:.1f} {cx+r:.1f},{cy:.1f} {cx:.1f},{cy+r:.1f} {cx-r:.1f},{cy:.1f}"
        return f'<polygon points="{pts}" {st}/>'
    if kind == "HL":
        pts = (f"{cx:.1f},{cy-r:.1f} {cx+r*0.866:.1f},{cy+r*0.5:.1f} "
               f"{cx-r*0.866:.1f},{cy+r*0.5:.1f}")
        return f'<polygon points="{pts}" {st}/>'
    return f'<rect x="{cx-r:.1f}" y="{cy-r:.1f}" width="{2*r:.1f}" height="{2*r:.1f}" {st}/>'


def arc_path(x1: float, y1: float, x2: float, y2: float,
             r1: float, r2: float,
             bx0: float, bx1: float, by0: float, by1: float,
             bow: float = 0.22, cap: float = 80.0) -> str | None:
    """二次贝塞尔 OD 弧线：向行进方向左侧拱起；两端按节点半径后退。"""
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return None
    px, py = dy / d, -dx / d  # 行进方向左侧法向（屏幕系）
    off = min(d * bow, cap)
    cx_ = min(max((x1 + x2) / 2 + px * off, bx0 + 8), bx1 - 8)
    cy_ = min(max((y1 + y2) / 2 + py * off, by0 + 8), by1 - 8)
    n0 = math.hypot(cx_ - x1, cy_ - y1)
    n1 = math.hypot(x2 - cx_, y2 - cy_)
    if n0 < 1e-6 or n1 < 1e-6:
        return None
    sx = x1 + (cx_ - x1) / n0 * (r1 + 5)
    sy = y1 + (cy_ - y1) / n0 * (r1 + 5)
    ex = x2 - (x2 - cx_) / n1 * (r2 + 5)
    ey = y2 - (y2 - cy_) / n1 * (r2 + 5)
    return (f"M{sx:.1f},{sy:.1f} Q{cx_:.1f},{cy_:.1f} {ex:.1f},{ey:.1f}")


def grid_left(A) -> None:
    """左面板经纬网格 + 度数标注（经度标签在面板上方，纬度在左侧外边）。

    单一格网原则（v1.3）：次要线与主要线必须共用同一套全局锚点，否则两套
    格网交错会出现 2°/3° 碎格与相距 1° 的近重合双线（即"两张底图叠加"）。
    次要线 = 5° 倍数且非 10° 倍数；主要线 = 10° 倍数（加粗 + 度数标签）。
    v1.1/v1.2 的次要线从 LON_MIN=72 / LAT_MIN=16 起算，与 10° 主网格错位。
    """
    A(f'<rect x="{X0}" y="{Y0}" width="{PW}" height="{PH}" '
      f'fill="{C_PLOT}" stroke="#D8D6CE" stroke-width="1.5"/>')
    # 次要线：全局 5° 格点（排除 10° 倍数，由主网格绘制）
    lon = math.ceil(LON_MIN / 5.0) * 5
    while lon <= LON_MAX:
        if lon % 10 != 0:
            A(f'<line x1="{X(lon):.1f}" y1="{Y0}" x2="{X(lon):.1f}" y2="{Y0+PH}" '
              f'stroke="{C_GRID}" stroke-width="0.9"/>')
        lon += 5
    # 主要线 + 经度标签：10° 倍数且严格在面板内
    lon = math.ceil(LON_MIN / 10.0) * 10
    while lon < LON_MAX:
        A(f'<line x1="{X(lon):.1f}" y1="{Y0}" x2="{X(lon):.1f}" y2="{Y0+PH}" '
          f'stroke="{C_GRID}" stroke-width="1.6"/>')
        A(f'<text x="{X(lon):.1f}" y="{Y0-8}" font-size="{FS_SMALL}" fill="{C_TEXT2}" '
          f'text-anchor="middle">{lon:g}°E</text>')
        lon += 10
    lat = math.ceil(LAT_MIN / 5.0) * 5
    while lat <= LAT_MAX:
        if lat % 10 != 0:
            A(f'<line x1="{X0}" y1="{Y(lat):.1f}" x2="{X0+PW}" y2="{Y(lat):.1f}" '
              f'stroke="{C_GRID}" stroke-width="0.9"/>')
        lat += 5
    lat = math.ceil(LAT_MIN / 10.0) * 10
    while lat < LAT_MAX:
        A(f'<line x1="{X0}" y1="{Y(lat):.1f}" x2="{X0+PW}" y2="{Y(lat):.1f}" '
          f'stroke="{C_GRID}" stroke-width="1.6"/>')
        A(f'<text x="{X0-8}" y="{Y(lat)+4.5:.1f}" font-size="{FS_SMALL}" fill="{C_TEXT2}" '
          f'text-anchor="end">{lat:g}°N</text>')
        lat += 10


def grid_right(A) -> None:
    """右面板（海外）经纬网格：线距更稀（比例尺不同，图内注明）。"""
    A(f'<rect x="{XR}" y="{YR}" width="{PWR}" height="{PHR}" '
      f'fill="{C_PLOT}" stroke="#D8D6CE" stroke-width="1.5"/>')
    lon = OLON_MIN
    while lon <= OLON_MAX:
        if abs(lon - round(lon)) < 1e-9:
            major = round(lon) % 30 == 0
            if major:
                w, lbl = 1.6, round(lon) % 60 == 0
            else:
                w, lbl = 0.9, False
            if round(lon) % 15 == 0:
                A(f'<line x1="{OX(lon):.1f}" y1="{YR}" x2="{OX(lon):.1f}" y2="{YR+PHR}" '
                  f'stroke="{C_GRID}" stroke-width="{w}"/>')
                if lbl and OLON_MIN < lon < OLON_MAX:
                    tag = "0°" if lon == 0 else ("°W" if lon < 0 else "°E")
                    A(f'<text x="{OX(lon):.1f}" y="{YR-8}" font-size="{FS_SMALL}" '
                      f'fill="{C_TEXT2}" text-anchor="middle">'
                      f'{"0°" if lon == 0 else str(abs(round(lon))) + tag}</text>')
        lon += 5
    lat = OLAT_MIN
    while lat <= OLAT_MAX:
        if abs(lat - round(lat)) < 1e-9 and round(lat) % 10 == 0:
            major = round(lat) % 20 == 0
            A(f'<line x1="{XR}" y1="{OY(lat):.1f}" x2="{XR+PWR}" y2="{OY(lat):.1f}" '
              f'stroke="{C_GRID}" stroke-width="{1.6 if major else 0.9}"/>')
            if major and OLAT_MIN < lat < OLAT_MAX:
                if lat > 0:
                    tag = f"{round(lat)}°N"
                elif lat < 0:
                    tag = f"{abs(round(lat))}°S"
                else:
                    tag = "0°"
                A(f'<text x="{XR-8}" y="{OY(lat)+4.5:.1f}" font-size="{FS_SMALL}" '
                  f'fill="{C_TEXT2}" text-anchor="end">{tag}</text>')
        lat += 5


def build(df: pd.DataFrame, counts: dict,
          dom_od: pd.DataFrame, ov_od: pd.DataFrame,
          lisa: dict, ov_total: dict, deg: dict,
          dest_coord: dict) -> list[str]:
    """df = 298 市 LISA 局部结果 + 质心；dom_od/ov_od = OD 弧线表；deg = 城市总度数。"""
    L: list[str] = []
    A = L.append

    def fmt(en: str) -> str:
        return f"{en} ({deg.get(en, 0)})"

    # ---- 集聚带图例行与数据一致性断言 ----
    n_hh_rows = sum(len(cs) for _, ms in CLUSTERS for k, cs in ms if k == "HH")
    n_lh_rows = sum(len(cs) for _, ms in CLUSTERS for k, cs in ms if k == "LH")
    assert n_hh_rows == counts.get("HH", 0), \
        f"集聚带图例 HH 成员 {n_hh_rows} ≠ 显著 HH {counts.get('HH', 0)}"
    assert n_lh_rows == counts.get("LH", 0), \
        f"集聚带图例 LH 成员 {n_lh_rows} ≠ 显著 LH {counts.get('LH', 0)}"

    A(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" '
      f'font-family="{FONT}">')
    A(f'<rect width="{VB_W}" height="{VB_H}" fill="{C_BG}"/>')
    # 箭头 marker（×1.6 适配新字号）
    A('<defs><marker id="arr" markerWidth="13" markerHeight="13" refX="10.4" refY="4.2" '
      f'orient="auto" markerUnits="userSpaceOnUse">'
      f'<path d="M0,0 L11.2,4.2 L0,8.4 Z" fill="{C_ARC}"/></marker></defs>')
    A(f'<text x="{X0}" y="40" font-size="{FS_TITLE}" font-weight="bold" fill="{C_TEXT}">'
      f'LISA Clusters and Cross-city Call Flows (KNN-5)</text>')
    A(f'<text x="{X0}" y="68" font-size="{FS_SUB}" font-weight="bold" fill="{C_TEXT2}">'
      f'Mainland China</text>')
    A(f'<text x="{XR}" y="68" font-size="{FS_SUB}" font-weight="bold" fill="{C_TEXT2}">'
      f'Overseas (different scale from left panel)</text>')

    # ================= 两个面板的网格（先画，弧线压在其上） =================
    grid_left(A)
    grid_right(A)

    # 左面板不显著城市（灰点）
    for r in df[df["cluster_p05"] == "不显著"].itertuples():
        vln = r.value_ln if r.value_ln == r.value_ln else 0.0  # noqa: PLR0124 (NaN 防御)
        A(f'<circle cx="{X(r.centroid_lon_wgs84):.1f}" cy="{Y(r.centroid_lat_wgs84):.1f}" '
          f'r="{1.9 + vln * 0.72:.1f}" fill="{C_NOSIG}" fill-opacity="0.55"/>')

    # 调用流端点（含国内与跨面板海外流的起点城市）加描边圆环，增强可见性
    endpoint_adcodes = set(dom_od["app_adcode"]) | set(dom_od["model_adcode"]) \
        | set(ov_od["app_adcode"])
    for ac in sorted(endpoint_adcodes):
        if lisa[ac]["sig"]:
            continue
        A(f'<circle cx="{lisa[ac]["x"]:.1f}" cy="{lisa[ac]["y"]:.1f}" '
          f'r="{lisa[ac]["r"] + 5:.1f}" fill="none" stroke="{C_TEXT2}" '
          f'stroke-width="1.4" stroke-opacity="0.85"/>')

    # ---- 国内 OD 弧线（粗者先画，细线在上；仅 ≥5 条边的 OD 对） ----
    for r in dom_od.sort_values("n", ascending=False).itertuples():
        ra = lisa[r.app_adcode]["r"]
        rb = lisa[r.model_adcode]["r"]
        d = arc_path(lisa[r.app_adcode]["x"], lisa[r.app_adcode]["y"],
                     lisa[r.model_adcode]["x"], lisa[r.model_adcode]["y"],
                     ra, rb, X0, X0 + PW, Y0, Y0 + PH)
        if d is None:
            continue
        A(f'<path d="{d}" fill="none" stroke="{C_ARC}" stroke-opacity="0.55" '
          f'stroke-width="{flow_width(r.n):.2f}" stroke-linecap="round" '
          f'marker-end="url(#arr)"/>')

    # ---- 跨面板海外 OD 弧线（全部 OD 对：左面板应用城 → 右面板海外模型城） ----
    for r in ov_od.sort_values("n", ascending=False).itertuples():
        src = lisa[r.app_adcode]
        dx_, dy_ = OX(dest_coord[r.dest_key][0]), OY(dest_coord[r.dest_key][1])
        r2 = 4.8 + 0.9 * math.sqrt(ov_total[r.dest_key])
        d = arc_path(src["x"], src["y"], dx_, dy_, src["r"], r2,
                     X0, XR + PWR, Y0, Y0 + PH,
                     bow=BOW_DEST.get(r.dest_key, 0.22), cap=80.0)
        if d is None:
            continue
        A(f'<path d="{d}" fill="none" stroke="{C_ARC}" stroke-opacity="0.42" '
          f'stroke-width="{flow_width(r.n):.2f}" stroke-linecap="round" '
          f'marker-end="url(#arr)"/>')

    # ---- 左面板显著城市（形状+颜色双编码） ----
    sig = df[df["cluster_p05"] != "不显著"].sort_values("value")
    for r in sig.itertuples():
        vln = r.value_ln if r.value_ln == r.value_ln else 0.0  # noqa: PLR0124
        A(marker(r.cluster_p05, X(r.centroid_lon_wgs84), Y(r.centroid_lat_wgs84),
                 4.8 + vln * 1.45, CLUSTER_COLOR[r.cluster_p05]))

    # ---- 右面板海外模型城节点（方块，大小∝总流入边数；压在弧线之上） ----
    for key, tot in sorted(ov_total.items()):
        x_, y_ = OX(dest_coord[key][0]), OY(dest_coord[key][1])
        rr = 4.8 + 0.9 * math.sqrt(tot)
        A(f'<rect x="{x_-rr:.1f}" y="{y_-rr:.1f}" width="{2*rr:.1f}" height="{2*rr:.1f}" '
          f'fill="{C_DEST}" fill-opacity="0.9" stroke="#FFFFFF" stroke-width="1.3"/>')

    # ---- 左面板主城市标注（城市名 + 总度数；集聚带其余成员见底部图例） ----
    for r in df.itertuples():
        if r.city_name not in LABELS:
            continue
        dx, dy, anchor = LABELS[r.city_name]
        px, py = X(r.centroid_lon_wgs84), Y(r.centroid_lat_wgs84)
        lx, ly = px + dx, py + dy
        A(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{lx:.1f}" y2="{ly:.1f}" '
          f'stroke="{C_TEXT2}" stroke-width="1.1" stroke-opacity="0.6"/>')
        tx = lx + (5 if anchor == "start" else (-5 if anchor == "end" else 0))
        A(f'<text x="{tx:.1f}" y="{ly+4.5:.1f}" font-size="{FS_CITY}" fill="{C_TEXT}" '
          f'text-anchor="{anchor}">{fmt(EN_CITY[r.city_name])}</text>')

    # ---- 右面板海外模型城标注（名称 + 总度数 = 流入边数） ----
    OV_LABELS = {
        BAY_EN:     (22, 8, "start"),
        "Seattle":  (20, -8, "start"),
        "New York": (0, -18, "middle"),
        "Cologne":  (20, -10, "start"),
        "Freiburg": (20, 10, "start"),
        "Sydney":   (-16, 8, "end"),
    }
    for key, (dx_, dy_, anchor) in OV_LABELS.items():
        x_, y_ = OX(dest_coord[key][0]), OY(dest_coord[key][1])
        tx = x_ + dx_ + (5 if anchor == "start" else (-5 if anchor == "end" else 0))
        A(f'<text x="{tx:.1f}" y="{y_+dy_+4.5:.1f}" font-size="{FS_CITY}" fill="{C_TEXT}" '
          f'text-anchor="{anchor}">{key} ({ov_total[key]})</text>')

    # ---- 调用流说明（右面板内下方空白区；6 行 ≤34 字符，避开弧线主通道） ----
    notes = [
        "Call flows (app city \u2192 model city),",
        "width \u221d edge count. Left: OD pairs",
        "with \u22655 edges (16); right: all 15",
        "overseas pairs (46 edges). Labels:",
        "total degree = incident call edges",
        "(self-loop counted once).",
    ]
    for i, txt in enumerate(notes):
        A(f'<text x="{XR+16}" y="{414 + i * 21}" font-size="{FS_SMALL}" '
          f'fill="{C_TEXT2}">{txt}</text>')
    # ================= 底部图例条带（y 582..790；全部 ≥7pt） =================
    # 行 A：LISA 图例（横排一行）
    row_y = 582
    xa = X0
    items = [("HH", f"HH High-High ({counts.get('HH', 0)})"),
             ("LH", f"LH Low-High ({counts.get('LH', 0)}, all zero)"),
             ("HL", f"HL High-Low ({counts.get('HL', 0)})"),
             ("LL", f"LL Low-Low ({counts.get('LL', 0)})")]
    for k, txt in items:
        A(marker(k, xa, row_y - 4.5, 7, CLUSTER_COLOR[k]))
        w_txt = len(txt) * 8.4
        A(f'<text x="{xa+16}" y="{row_y}" font-size="{FS_SMALL}" fill="{C_TEXT}">{txt}</text>')
        xa += 16 + w_txt + 22
    A(f'<circle cx="{xa}" cy="{row_y-4.5}" r="5" fill="{C_NOSIG}"/>')
    A(f'<text x="{xa+14}" y="{row_y}" font-size="{FS_SMALL}" fill="{C_TEXT}">'
      f'Not significant ({counts.get("不显著", 0)})</text>')

    # 行 B：弧线宽度标尺（横排一行）
    row_y = 614
    A(f'<text x="{X0}" y="{row_y}" font-size="{FS_SMALL}" fill="{C_TEXT}">'
      f'Arc width \u221d edges per OD pair:</text>')
    xb = X0 + 268
    for n in (5, 20, 50):
        A(f'<line x1="{xb}" y1="{row_y-4}" x2="{xb+72}" y2="{row_y-4}" '
          f'stroke="{C_ARC}" stroke-opacity="0.55" stroke-width="{flow_width(n):.2f}" '
          f'stroke-linecap="round"/>')
        lbl = f"{n} edges"
        A(f'<text x="{xb+84}" y="{row_y}" font-size="{FS_SMALL}" fill="{C_TEXT}">{lbl}</text>')
        xb += 84 + len(lbl) * 8.4 + 24

    # 行 C..E：三大集聚带成员（HH/LH 显著城市全名单，带度数）
    # 按字符宽度贪心换行：一行 ≤112 字符（≈941 px），超出在逗号边界断行
    row_y = 646
    for title, members in CLUSTERS:
        A(f'<text x="{X0}" y="{row_y}" font-size="{FS_BOLD}" font-weight="bold" '
          f'fill="{C_HH}">{title}</text>')
        row_y += 22
        segs = [f"{k}\u00d7{len(cs)}: " + ", ".join(fmt(c) for c in cs)
                for k, cs in members]
        # 流式换行：段内按 ", " 边界拆分、段间以 " · " 相接，一行 ≤112 字符
        units: list[str] = []
        for si, seg in enumerate(segs):
            parts = seg.split(", ")
            for pi, p in enumerate(parts):
                sep = ""
                if pi == 0:
                    if si > 0:
                        sep = " \u00b7 "
                else:
                    sep = ", "
                units.append(sep + p)
        lines: list[str] = []
        for u in units:
            if not lines or len(lines[-1]) + len(u) > 112:
                lines.append(u)
            else:
                lines[-1] += u
        for txt in lines:
            txt = txt.lstrip(", ")
            A(f'<text x="{X0}" y="{row_y}" font-size="{FS_SMALL}" fill="{C_TEXT}">'
              f'{txt}</text>')
            row_y += 22
        row_y += 8

    A("</svg>")
    return L


def qa_grid_lattice(svg: str) -> None:
    """回归自检：左面板网格必须是单一 5° 格网（无重线、无错位碎格）。

    v1.3 的 bug 根因是两套锚点不同的格网叠加，此处从产出 SVG 反解每条线的
    经纬度，断言：①无重复坐标；②全部落在 5° 倍数上；③相邻间距恒为 5°。
    右面板同理断言经线 15° / 纬线 10° 的规整性。
    """
    import re

    def lon_of(x: float) -> float:
        return LON_MIN + (x - X0) * (LON_MAX - LON_MIN) / PW

    def lat_of(y: float) -> float:
        return LAT_MAX - (y - Y0) * (LAT_MAX - LAT_MIN) / PH

    vx = [float(m.group(1)) for m in re.finditer(
        r'<line x1="([\d.]+)" y1="96" x2="[\d.]+" y2="552"', svg)]
    hy = [float(m.group(1)) for m in re.finditer(
        r'<line x1="48" y1="([\d.]+)" x2="518" y2="[\d.]+"', svg)]
    assert vx and hy, "左面板网格线缺失"
    assert len(set(round(v, 1) for v in vx)) == len(vx), "左面板存在重复经线（格网叠加）"
    assert len(set(round(v, 1) for v in hy)) == len(hy), "左面板存在重复纬线（格网叠加）"

    lons = sorted(lon_of(x) for x in vx)
    lats = sorted(lat_of(y) for y in hy)
    for v in lons:
        assert abs(v / 5 - round(v / 5)) < 0.02, f"经线 {v:.2f}° 不在 5° 格点上"
    for v in lats:
        assert abs(v / 5 - round(v / 5)) < 0.02, f"纬线 {v:.2f}° 不在 5° 格点上"
    for a, b in zip(lons, lons[1:]):
        assert abs((b - a) - 5) < 0.05, f"经线间距 {b-a:.2f}° ≠ 5°（格网错位）"
    for a, b in zip(lats, lats[1:]):
        assert abs((b - a) - 5) < 0.05, f"纬线间距 {b-a:.2f}° ≠ 5°（格网错位）"

    ox = [float(m.group(1)) for m in re.finditer(
        r'<line x1="([\d.]+)" y1="96" x2="[\d.]+" y2="526"', svg)]
    olons = sorted(OLON_MIN + (x - XR) * (OLON_MAX - OLON_MIN) / PWR for x in ox)
    for v in olons:
        assert abs(v / 15 - round(v / 15)) < 0.05, f"右面板经线 {v:.1f}° 不在 15° 格点上"
    for a, b in zip(olons, olons[1:]):
        assert abs((b - a) - 15) < 0.1, f"右面板经线间距 {b-a:.1f}° ≠ 15°"

    print(f"QA 格网: 左面板 {len(lons)} 条经线 / {len(lats)} 条纬线，"
          f"单一 5° 格网无重线（v1.3 回归项 PASS）；右面板 {len(olons)} 条经线 15° 格网 PASS")


def main() -> int:
    ld = pd.read_csv(IN_LOCAL, encoding="utf-8-sig", dtype={"adcode": str})
    sub = ld[ld["variable"] == "ln1p_merged_filings"].copy()
    coords = pd.read_csv(paths.COORDS, encoding="utf-8-sig", dtype={"adcode": str})
    df = sub.merge(
        coords[["adcode", "centroid_lon_wgs84", "centroid_lat_wgs84"]],
        on="adcode", how="left", validate="one_to_one",
    )
    if df["centroid_lon_wgs84"].isna().any():
        raise SystemExit("!! 有城市缺质心坐标，中止")
    df["adcode"] = df["adcode"].astype(str)

    # ---- 表3：拆分自环 / 国内跨城 / 海外 ----
    e = pd.read_csv(IN_EDGES, encoding="utf-8-sig", dtype=str)
    for c in ("app_city_lon_wgs84", "app_city_lat_wgs84",
              "model_city_lon_wgs84", "model_city_lat_wgs84"):
        e[c] = pd.to_numeric(e[c], errors="coerce")
    e["app_adcode"] = e["app_adcode"].astype(str)
    same = e["app_city_cn"] == e["model_city_cn"]
    is_ov = e["edge_basis"].str.contains("overseas")
    dom_cross = e[~same & ~is_ov]
    ov = e[~same & is_ov]

    # QA：口径断言（v1.2 rev5）
    assert len(e) == 778, f"表3 应为 778 条边，实为 {len(e)}"
    assert int(same.sum()) == 414, f"自环应 414，实为 {int(same.sum())}"
    assert len(dom_cross) == 318, f"国内跨城应 318，实为 {len(dom_cross)}"
    assert len(ov) == 46, f"海外跨城应 46，实为 {len(ov)}"
    assert ov["model_city_lon_wgs84"].notna().all(), "海外模型城坐标缺失"

    # ---- 城市总度数：关联调用边数（应用端或模型端；自环计 1 次） ----
    deg = (e["app_city_en"].value_counts()
           .add(e["model_city_en"].value_counts(), fill_value=0))
    sl = e.loc[same, "app_city_en"].value_counts()
    deg = (deg - sl.reindex(deg.index).fillna(0)).astype(int)
    # 湾区合并节点度数 = 四城流入边数之和
    bay_deg = int(sum(int(deg.get(c, 0)) for c in BAY_AREA))
    deg_merged = dict(deg)
    deg_merged[BAY_EN] = bay_deg

    # ---- 国内 OD 聚合（≥5 条边） ----
    dom_od = (dom_cross.groupby(["app_adcode", "model_adcode"])
              .agg(n=("edge_id", "size"))
              .reset_index())
    dom_od = dom_od[dom_od["n"] >= MIN_EDGES].sort_values("n", ascending=False)
    assert len(dom_od) == 16, f"国内 ≥5 边 OD 对应 16，实为 {len(dom_od)}"

    # ---- 海外 OD 聚合（湾区四城合并；全部 OD 对） ----
    ov = ov.copy()
    ov["dest_key"] = ov["model_city_en"].map(
        lambda s: BAY_EN if s in BAY_AREA else s)
    ov["dest_lon"] = ov["model_city_lon_wgs84"]
    ov["dest_lat"] = ov["model_city_lat_wgs84"]
    bay = ov[ov["dest_key"] == BAY_EN]
    if len(bay):
        ov.loc[ov["dest_key"] == BAY_EN, ["dest_lon", "dest_lat"]] = (BAY_LON, BAY_LAT)
    ov_od = (ov.groupby(["app_adcode", "dest_key", "dest_lon", "dest_lat"])
             .agg(n=("edge_id", "size"))
             .reset_index())
    ov_total = ov.groupby("dest_key")["edge_id"].size().to_dict()
    # 同一目的地的多条弧线按起点 adcode 顺序递增微调拱起系数，避免完全重合
    ov_od = ov_od.sort_values(["dest_key", "app_adcode"]).reset_index(drop=True)
    ov_od["bow"] = ov_od.groupby("dest_key").cumcount().map(
        lambda i: 0.025 * i).add(ov_od["dest_key"].map(
        lambda k: BOW_DEST.get(k, 0.22)))
    assert len(ov_od) == 15, f"海外合并后 OD 对应 15，实为 {len(ov_od)}"
    assert int(ov_od["n"].sum()) == 46, "海外 OD 边数合计应 46"
    assert int(dom_od["n"].sum()) == 204, "国内 ≥5 边 OD 边数合计应 204"
    assert ov_total[BAY_EN] == 40, f"湾区流入应 40，实为 {ov_total[BAY_EN]}"
    assert deg_merged[BAY_EN] == 40, "湾区合并度数应 40"

    dest_coord: dict[str, tuple[float, float]] = {}
    for key in ov_total:
        row = ov[ov["dest_key"] == key].iloc[0]
        dest_coord[key] = (float(row["dest_lon"]), float(row["dest_lat"]))

    # ---- 逐市渲染信息 ----
    lisa: dict[str, dict] = {}
    for r in df.itertuples():
        vln = r.value_ln if r.value_ln == r.value_ln else 0.0  # noqa: PLR0124
        sig = r.cluster_p05 != "不显著"
        lisa[r.adcode] = dict(
            sig=sig, cluster=r.cluster_p05, vln=vln,
            r=(4.8 + vln * 1.45) if sig else (1.9 + vln * 0.72),
            x=X(r.centroid_lon_wgs84), y=Y(r.centroid_lat_wgs84),
        )

    counts = sub["cluster_p05"].value_counts().to_dict()

    # QA：打印度数极值与杭州归类，供报告核对
    top = sorted(deg_merged.items(), key=lambda kv: -kv[1])[:5]
    print("QA 度数 Top5:", ", ".join(f"{k} ({v})" for k, v in top))
    hz = df[df["city_name"] == "杭州市"]
    if len(hz):
        h = hz.iloc[0]
        print(f"QA 杭州: value={h['value']:.0f} cluster_p05={h['cluster_p05']} "
              f"quadrant={h['quadrant']} p={h['p_sim']}")
    print(f"QA 跨面板海外 OD: {len(ov_od)} 对 / {int(ov_od['n'].sum())} 条边; "
          f"起点城市 {ov_od['app_adcode'].nunique()} 个")

    svg = "\n".join(build(df, counts, dom_od, ov_od, lisa, ov_total,
                          deg_merged, dest_coord))
    qa_grid_lattice(svg)
    OUT.write_text(svg, encoding="utf-8")
    print(f"OK {OUT}  ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
