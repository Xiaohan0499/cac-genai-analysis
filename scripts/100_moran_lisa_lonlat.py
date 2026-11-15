#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
100_moran_lisa_lonlat.py — ln(1+备案记录数) LISA 结果经纬线示意图（非地图，中英双版，v1.1）

设计考量:
  - 为规避地图审查风险，底图不使用任何地图要素（无行政边界、无海岸线、
    无九段线），仅绘制经纬网格 + 城市质心散点
  - 标题仅保留「LISA集聚（KNN-5）」，副题、数据来源等说明文字一律
    移至图外脚注（v1.1 应投稿要求）
  - 显著点形状+颜色双编码（黑白打印仍可辨认）：HH=圆、LH=菱形、
    HL=三角形、LL=正方形（ln1p_merged_filings × KNN-5，α=0.05）
  - 点大小 ∝ ln(1+备案记录数)；不显著城市为灰色小圆点
  - 标注策略：京津冀与 LH 卫星城散布、逐城引线标注；
    长三角/珠三角点距仅数像素、逐城标注必然叠字，改为集聚带引出框
  - 一次运行同时产出中文版与英文版

输入（只读）:
  - data/moran_log_local_v1.0.csv   99 号脚本的局部结果（ln 口径）
  - geo/china_city_coords_v1.0.csv   城市质心经纬度（WGS84）

输出（幂等，字节确定）:
  - data/moran_log_lisa_lonlat_v1.1.svg      中文版
  - data/moran_log_lisa_lonlat_v1.1_en.svg   英文版

用法:
    python scripts/100_moran_lisa_lonlat.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

import paths

IN_LOCAL = paths.DATA / "moran_log_local_v1.0.csv"
OUT_ZH = paths.DATA / "moran_log_lisa_lonlat_v1.1.svg"
OUT_EN = paths.DATA / "moran_log_lisa_lonlat_v1.1_en.svg"

# 画布与投影（等经纬度直线投影，示意用）
VB_W, VB_H = 700, 640
X0, Y0, PW, PH = 78, 62, 540, 500
LON_MIN, LON_MAX = 72.0, 136.0
LAT_MIN, LAT_MAX = 15.0, 57.0

C_BG = "#FFFFFF"
C_PLOT = "#FCFCFA"
C_GRID = "#E3E1DA"
C_TEXT = "#26215C"
C_TEXT2 = "#8A877F"
C_NOSIG = "#C9C7BF"
C_HH = "#E24B4A"
CLUSTER_COLOR = {"HH": "#E24B4A", "LH": "#F0997B", "HL": "#EF9F27", "LL": "#378ADD"}

# 逐城引线标注（散布城市）：像素偏移 + 文字锚点
LABELS = {
    "北京市":   (-16, -16, "end"),
    "张家口市": (-14, 8, "end"),
    "承德市":   (12, -14, "start"),
    "唐山市":   (14, -6, "start"),
    "天津市":   (16, 6, "start"),
    "廊坊市":   (16, 20, "start"),
    "舟山市":   (12, 2, "start"),
    "绍兴市":   (-13, -6, "end"),
    "马鞍山市": (-14, 8, "end"),
    "宣城市":   (-14, 18, "end"),
}

# 英文城市名（逐城引线标注用）
EN_CITY = {
    "北京市": "Beijing", "张家口市": "Zhangjiakou", "承德市": "Chengde",
    "唐山市": "Tangshan", "天津市": "Tianjin", "廊坊市": "Langfang",
    "舟山市": "Zhoushan", "绍兴市": "Shaoxing", "马鞍山市": "Maanshan",
    "宣城市": "Xuancheng",
}

# 集聚带引出框：(引出锚点城市, 框左上角 x, y, [标题, 行2, 行3…])
BLOCKS_ZH = [
    ("苏州市", 522, 300, ["长三角集聚带", "HH×9：上海·苏州·无锡·常州", "镇江·南通·嘉兴·湖州·宁波"]),
    ("广州市", 436, 486, ["珠三角集聚带", "HH×4：广州·深圳·东莞·珠海", "LH×2：中山·惠州（零备案）"]),
]
BLOCKS_EN = [
    ("苏州市", 508, 300, ["Yangtze River Delta cluster", "HH×9: Shanghai, Suzhou, Wuxi,",
                         "Changzhou, Zhenjiang, Nantong,", "Jiaxing, Huzhou, Ningbo"]),
    ("广州市", 436, 486, ["Pearl River Delta cluster", "HH×4: Guangzhou, Shenzhen,",
                         "Dongguan, Zhuhai", "LH×2: Zhongshan, Huizhou (zero)"]),
]

# 语言配置：标题、字体、集聚带引出框与图例几何（说明文字一律移至图外脚注）
LANGS = {
    "zh": dict(
        out=OUT_ZH,
        font="'Microsoft YaHei', 'PingFang SC', sans-serif",
        title="LISA集聚（KNN-5）",
        blocks=BLOCKS_ZH,
        block_char_w=9.6,
        legend_dx=150, legend_w=160, legend_h=110,
        item=lambda k, n: {
            "HH": f"HH 高-高（{n} 市）",
            "LH": f"LH 低-高（{n} 市，均零备案）",
            "HL": f"HL 高-低（{n} 市）",
            "LL": f"LL 低-低（{n} 市）",
        }[k],
        nsig=lambda n: f"不显著（{n} 市）",
        city=lambda cn: cn[:-1],
        lon_ax="经度（°E）",
        lat_ax="纬度（°N）",
    ),
    "en": dict(
        out=OUT_EN,
        font="'Segoe UI', Arial, sans-serif",
        title="LISA Clusters (KNN-5)",
        blocks=BLOCKS_EN,
        block_char_w=5.6,
        legend_dx=180, legend_w=190, legend_h=110,
        item=lambda k, n: {
            "HH": f"HH High-High ({n} cities)",
            "LH": f"LH Low-High ({n}, all zero)",
            "HL": f"HL High-Low ({n} cities)",
            "LL": f"LL Low-Low ({n} cities)",
        }[k],
        nsig=lambda n: f"Not significant ({n} cities)",
        city=lambda cn: EN_CITY[cn],
        lon_ax="Longitude (°E)",
        lat_ax="Latitude (°N)",
    ),
}


def X(lon: float) -> float:
    return X0 + (lon - LON_MIN) * PW / (LON_MAX - LON_MIN)


def Y(lat: float) -> float:
    return Y0 + (LAT_MAX - lat) * PH / (LAT_MAX - LAT_MIN)


def marker(kind: str, cx: float, cy: float, r: float, fill: str) -> str:
    """集聚类型 → SVG 图形：HH=圆、LH=菱形、HL=三角形、LL=正方形（黑白可辨）。"""
    st = f'fill="{fill}" fill-opacity="0.85" stroke="#FFFFFF" stroke-width="0.8"'
    if kind == "HH":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" {st}/>'
    if kind == "LH":  # 菱形
        pts = f"{cx:.1f},{cy-r:.1f} {cx+r:.1f},{cy:.1f} {cx:.1f},{cy+r:.1f} {cx-r:.1f},{cy:.1f}"
        return f'<polygon points="{pts}" {st}/>'
    if kind == "HL":  # 等边三角形（顶点朝上）
        pts = (f"{cx:.1f},{cy-r:.1f} {cx+r*0.866:.1f},{cy+r*0.5:.1f} "
               f"{cx-r*0.866:.1f},{cy+r*0.5:.1f}")
        return f'<polygon points="{pts}" {st}/>'
    # LL：正方形
    return f'<rect x="{cx-r:.1f}" y="{cy-r:.1f}" width="{2*r:.1f}" height="{2*r:.1f}" {st}/>'


def build(cfg: dict, df: pd.DataFrame, counts: dict) -> list[str]:
    sig = df[df["cluster_p05"] != "不显著"].sort_values("value")
    L: list[str] = []
    A = L.append

    A(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB_W} {VB_H}" '
      f'font-family="{cfg["font"]}">')
    A(f'<rect width="{VB_W}" height="{VB_H}" fill="{C_BG}"/>')
    A(f'<text x="30" y="30" font-size="17" font-weight="bold" fill="{C_TEXT}">'
      f'{cfg["title"]}</text>')
    A(f'<rect x="{X0}" y="{Y0}" width="{PW}" height="{PH}" fill="{C_PLOT}" stroke="#D8D6CE"/>')

    # ---- 经纬网格 ----
    lon = LON_MIN
    while lon <= LON_MAX:
        if abs(lon - round(lon)) < 1e-9:
            major = round(lon) % 10 == 0
            A(f'<line x1="{X(lon):.1f}" y1="{Y0}" x2="{X(lon):.1f}" y2="{Y0+PH}" '
              f'stroke="{C_GRID}" stroke-width="{1.0 if major else 0.6}"/>')
            if major and lon > LON_MIN:
                A(f'<text x="{X(lon):.1f}" y="{Y0+PH+16}" font-size="10" fill="{C_TEXT2}" '
                  f'text-anchor="middle">{round(lon)}°E</text>')
        lon += 5
    lat = LAT_MIN
    while lat <= LAT_MAX:
        if abs(lat - round(lat)) < 1e-9:
            major = round(lat) % 10 == 0
            A(f'<line x1="{X0}" y1="{Y(lat):.1f}" x2="{X0+PW}" y2="{Y(lat):.1f}" '
              f'stroke="{C_GRID}" stroke-width="{1.0 if major else 0.6}"/>')
            if major and lat < LAT_MAX:
                A(f'<text x="{X0-6}" y="{Y(lat)+3.5:.1f}" font-size="10" fill="{C_TEXT2}" '
                  f'text-anchor="end">{round(lat)}°N</text>')
        lat += 5

    # ---- 不显著城市（灰点） ----
    for r in df[df["cluster_p05"] == "不显著"].itertuples():
        vln = r.value_ln if r.value_ln == r.value_ln else 0.0  # noqa: PLR0124 (NaN 防御)
        rad = 1.2 + vln * 0.45
        A(f'<circle cx="{X(r.centroid_lon_wgs84):.1f}" cy="{Y(r.centroid_lat_wgs84):.1f}" '
          f'r="{rad:.1f}" fill="{C_NOSIG}" fill-opacity="0.55"/>')

    # ---- 显著城市（形状+颜色双编码） ----
    for r in sig.itertuples():
        vln = r.value_ln if r.value_ln == r.value_ln else 0.0  # noqa: PLR0124
        rad = 3.0 + vln * 0.9
        A(marker(r.cluster_p05, X(r.centroid_lon_wgs84), Y(r.centroid_lat_wgs84),
                 rad, CLUSTER_COLOR[r.cluster_p05]))

    # ---- 逐城引线标注（散布城市） ----
    for r in sig.itertuples():
        if r.city_name not in LABELS:
            continue
        dx, dy, anchor = LABELS[r.city_name]
        px, py = X(r.centroid_lon_wgs84), Y(r.centroid_lat_wgs84)
        lx, ly = px + dx, py + dy
        col = CLUSTER_COLOR[r.cluster_p05]
        A(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{lx:.1f}" y2="{ly:.1f}" '
          f'stroke="{col}" stroke-width="0.7" stroke-opacity="0.6"/>')
        tx = lx + (3 if anchor == "start" else (-3 if anchor == "end" else 0))
        A(f'<text x="{tx:.1f}" y="{ly+3:.1f}" font-size="9.5" fill="{C_TEXT}" '
          f'text-anchor="{anchor}">{cfg["city"](r.city_name)}</text>')

    # ---- 集聚带引出框（长三角 / 珠三角） ----
    by_city = df.set_index("city_name")
    for anchor_city, bx, by, lines in cfg["blocks"]:
        ax = X(by_city.at[anchor_city, "centroid_lon_wgs84"])
        ay = Y(by_city.at[anchor_city, "centroid_lat_wgs84"])
        A(f'<path d="M{ax:.1f},{ay:.1f} Q{ax+10:.1f},{ay+10:.1f} {bx+6:.1f},{by+6:.1f}" '
          f'fill="none" stroke="{C_HH}" stroke-width="0.9" stroke-dasharray="3,2" '
          f'stroke-opacity="0.7"/>')
        bw = 8 + max(len(s) for s in lines) * cfg["block_char_w"]
        bh = 14 + len(lines) * 15
        A(f'<rect x="{bx}" y="{by}" width="{bw:.0f}" height="{bh}" rx="4" '
          f'fill="#FFFFFF" fill-opacity="0.92" stroke="{C_HH}" stroke-opacity="0.5"/>')
        for i, txt in enumerate(lines):
            if i == 0:
                A(f'<text x="{bx+8}" y="{by+15+i*15}" font-size="10.5" font-weight="bold" '
                  f'fill="{C_HH}">{txt}</text>')
            else:
                A(f'<text x="{bx+8}" y="{by+15+i*15}" font-size="9.5" fill="{C_TEXT}">{txt}</text>')

    # ---- 图例 ----
    lx, ly = X0 + PW - cfg["legend_dx"], Y0 + 12
    A(f'<rect x="{lx-10}" y="{ly-10}" width="{cfg["legend_w"]}" height="{cfg["legend_h"]}" '
      f'rx="4" fill="#FFFFFF" fill-opacity="0.9" stroke="#D8D6CE"/>')
    items = [(k, cfg["item"](k, counts.get(k, 0))) for k in ("HH", "LH", "HL", "LL")]
    for i, (k, txt) in enumerate(items):
        yy = ly + i * 20
        A(marker(k, lx, yy, 5.5, CLUSTER_COLOR[k]))
        A(f'<text x="{lx+10}" y="{yy+3.5}" font-size="10.5" fill="{C_TEXT}">{txt}</text>')
    yy = ly + 4 * 20
    A(f'<circle cx="{lx}" cy="{yy}" r="3" fill="{C_NOSIG}"/>')
    A(f'<text x="{lx+10}" y="{yy+3.5}" font-size="10.5" fill="{C_TEXT}">'
      f'{cfg["nsig"](counts.get("不显著", 0))}</text>')

    A(f'<text x="{X0+PW/2:.0f}" y="{VB_H-24}" font-size="10.5" fill="{C_TEXT2}" '
      f'text-anchor="middle">{cfg["lon_ax"]}</text>')
    A(f'<text x="22" y="{Y0+PH/2:.0f}" font-size="10.5" fill="{C_TEXT2}" '
      f'text-anchor="middle" transform="rotate(-90 22 {Y0+PH/2:.0f})">{cfg["lat_ax"]}</text>')
    A("</svg>")
    return L


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

    counts = sub["cluster_p05"].value_counts().to_dict()
    for lang, cfg in LANGS.items():
        svg = "\n".join(build(cfg, df, counts))
        cfg["out"].write_text(svg, encoding="utf-8")
        print(f"OK [{lang}] {cfg['out']}  ({cfg['out'].stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
