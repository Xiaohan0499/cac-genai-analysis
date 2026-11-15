#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
99_moran_log_knn5.py — 变体分析：ln(1+备案记录数) × KNN-5 的 Moran 空间自相关

用户口径:
  - 变量: 城市 i 的备案记录条数 = 模型备案 + 应用登记（两类合并、不分层），
    即 1843 条全记录中排除 7 条端侧（device）记录后的 1836 条口径
  - 变换: 自然对数 ln(1+y)
  - 权重: KNN-5（质心大圆距离最近 5 市，行标准化；与 97 的 W2 完全一致）
  - 检验: 全局 999 次置换（种子 42，双侧 pseudo-p）；局部条件置换 999 次
  - 一致性校验: 全局 I ≡ (n/S0)·Σ local_i / (z'z)

输出（幂等，固定种子 ⇒ 逐字节一致）:
  - data/moran_log_global_v1.0.csv   全局结果（ln 口径 + 原始合并口径对照，均为 KNN-5）
  - data/moran_log_local_v1.0.csv    局部结果（两口径 × 298 市）
  - data/qa_report_moran_log.txt      体检 + 结果摘要

用法:
    python scripts/99_moran_log_knn5.py

依赖: numpy、pandas（复用 97_moran_analysis.py 的权重构建与置换检验函数）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import paths

# 复用 97 的函数（文件名以数字开头，无法常规 import，走 importlib）
_spec = importlib.util.spec_from_file_location(
    "m97", Path(__file__).resolve().parent / "97_moran_analysis.py"
)
m97 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m97)

OUT_GLOBAL = paths.DATA / "moran_log_global_v1.0.csv"
OUT_LOCAL = paths.DATA / "moran_log_local_v1.0.csv"
OUT_REPORT = paths.DATA / "qa_report_moran_log.txt"

VAR_LN = ("ln1p_merged_filings", "ln(1+备案记录数)（合并口径）")
VAR_RAW = ("merged_filings", "备案记录数（合并口径，未变换，对照）")
WEIGHT_NAME = ("knn5", "KNN-5")


def main() -> int:
    frame, feats = m97.load_lattice()
    n = len(frame)

    counts, info = m97.build_counts(frame)

    # ---- 用户口径：模型备案 + 应用登记（排除端侧 device） ----
    merged = (counts["model_filings"] + counts["app_registrations"]).astype(int)
    n_merged = int(merged.sum())
    checks: list[tuple[str, str, bool]] = []

    # C1 合并口径总量 = 模型 + 应用登记（与源表动态核对）
    ok1 = n_merged == info["n_model"] + info["n_app"]
    checks.append((
        "C1 合并口径总量",
        f"模型备案 {info['n_model']} + 应用登记 {info['n_app']} = {n_merged} 条"
        f"（全记录 {info['n_records']} − 端侧 {info['n_device']} = {info['n_records'] - info['n_device']}）",
        ok1 and n_merged == info["n_records"] - info["n_device"],
    ))
    # C2 非零/零值城市
    checks.append((
        "C2 城市覆盖",
        f"非零 {int((merged > 0).sum())} 市、零值 {int((merged == 0).sum())} 市（合计 {n}）",
        int((merged > 0).sum()) + int((merged == 0).sum()) == n,
    ))

    # ---- 权重 KNN-5（与 97 的 W2 逐字节一致） ----
    coords = pd.read_csv(paths.COORDS, encoding="utf-8-sig", dtype={"adcode": str})
    c = frame[["adcode"]].merge(
        coords[["adcode", "centroid_lon_wgs84", "centroid_lat_wgs84"]], on="adcode", how="left"
    )
    if c["centroid_lon_wgs84"].isna().any():
        raise SystemExit("!! 有边界单元缺质心坐标，中止")
    dist = m97.haversine_mat(
        c["centroid_lon_wgs84"].to_numpy(), c["centroid_lat_wgs84"].to_numpy()
    )
    adj = m97.build_knn(dist)
    W = m97.to_dense(adj, n)
    checks.append((
        "C3 KNN-5 完整性",
        f"每单元恰好 {m97.KNN_K} 个邻居（{sum(len(v) for v in adj.values())} 有向边）",
        all(len(v) == m97.KNN_K for v in adj.values()),
    ))

    # ---- 全局（ln 口径 + 原始口径对照） ----
    x_ln = np.log1p(merged.to_numpy(dtype=float))
    x_raw = merged.to_numpy(dtype=float)

    # C4 变换边界: 零值市 → 0；最大值 = ln(1+506)
    ok4 = bool(x_ln.min() == 0.0 and np.isclose(x_ln.max(), np.log1p(merged.max())))
    checks.append((
        "C4 对数变换边界",
        f"ln(1+y) ∈ [{x_ln.min():.4f}, {x_ln.max():.4f}]（零值市映射为 0，"
        f"{frame['city_name'].iat[int(merged.to_numpy().argmax())]} 最大 {int(merged.max())} 条）",
        ok4,
    ))

    rows_global = []
    sum_local_ref: dict[str, float] = {}
    for var, var_cn, x in ((VAR_LN[0], VAR_LN[1], x_ln), (VAR_RAW[0], VAR_RAW[1], x_raw)):
        r = m97.global_moran(x, W)
        sum_local_ref[var] = r["sum_local"]
        rows_global.append({
            "variable": var, "variable_cn": var_cn,
            "weights": WEIGHT_NAME[0], "weights_cn": WEIGHT_NAME[1],
            "n_units": n, "n_units_in_w": int((W.sum(axis=1) > 0).sum()),
            "moran_i": round(r["moran_i"], 6),
            "expected_i": round(r["expected_i"], 6),
            "mean_perm": round(r["mean_sim"], 6),
            "std_perm": round(r["std_sim"], 6),
            "z_sim": round(r["z_sim"], 3),
            "p_sim_two_sided": round(r["p_sim"], 4),
            "sig_0.05": "是" if r["p_sim"] <= 0.05 else "否",
            "sig_0.01": "是" if r["p_sim"] <= 0.01 else "否",
            "_raw": r,
        })
    gdf = pd.DataFrame(rows_global)

    # ---- 局部（两口径） ----
    rows_local = []
    cons_flags = []
    for var, var_cn, x in ((VAR_LN[0], VAR_LN[1], x_ln), (VAR_RAW[0], VAR_RAW[1], x_raw)):
        r = m97.local_moran(x, W)
        gr = gdf[gdf.variable == var]["_raw"].iloc[0]
        ok_consistency = np.isclose(
            gr["moran_i"], (n / gr["s0"]) * sum_local_ref[var] / gr["den"], rtol=1e-9
        )
        cons_flags.append((var, ok_consistency))
        for i in range(n):
            p = r["p_sim"][i]
            q = r["quadrant"][i]
            rows_local.append({
                "variable": var, "variable_cn": var_cn,
                "weights": WEIGHT_NAME[0],
                "adcode": frame["adcode"].iat[i],
                "city_name": frame["city_name"].iat[i],
                "province_name": frame["province_name"].iat[i],
                "value": int(merged.iat[i]),
                "value_ln": round(float(x_ln[i]), 4) if var == VAR_LN[0] else "",
                "z": round(float(r["z"][i]), 4),
                "lag_z": round(float(r["lag"][i]), 4),
                "local_i": round(float(r["local_i"][i]), 4),
                "z_sim": round(float(r["z_sim"][i]), 3) if np.isfinite(r["z_sim"][i]) else "",
                "p_sim": round(float(p), 4) if np.isfinite(p) else "",
                "quadrant": q,
                "cluster_p05": q if np.isfinite(p) and p <= 0.05 else "不显著",
                "cluster_p01": q if np.isfinite(p) and p <= 0.01 else "不显著",
                "n_neighbors": len(adj[i]),
            })
    ldf = pd.DataFrame(rows_local)

    # C5 全局-局部一致性
    ok5 = all(f for _, f in cons_flags)
    checks.append((
        "C5 全局-局部一致性",
        "两口径均满足 I ≡ (n/S0)·Σ local_i/(z'z)（rtol=1e-9）",
        ok5,
    ))
    # C6 取值域
    ok6 = bool((gdf["moran_i"].abs() <= 1.0).all())
    checks.append((
        "C6 全局 I 取值域",
        f"两口径 I ∈ [{gdf['moran_i'].min():.4f}, {gdf['moran_i'].max():.4f}]，均 |I| ≤ 1",
        ok6,
    ))

    # ---- 落盘 ----
    gdf.drop(columns=["_raw"]).to_csv(OUT_GLOBAL, index=False, encoding="utf-8-sig")
    ldf.to_csv(OUT_LOCAL, index=False, encoding="utf-8-sig")

    # ---- 体检报告 ----
    L: list[str] = []
    L.append("Moran 变体分析（ln(1+备案记录数) × KNN-5）— 体检报告")
    L.append("=" * 72)
    L.append("变量口径: 模型备案 + 应用登记两类合并计数（不分层，排除 7 条端侧记录）")
    L.append(f"变换: ln(1+y)；权重: KNN-5 行标准化；置换: {m97.N_PERM} 次，种子 {m97.SEED}")
    L.append("")
    n_pass = sum(1 for _, _, ok in checks if ok)
    for name, desc, ok in checks:
        L.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {desc}")
    L.append("")
    L.append(f"体检: {len(checks)} 项，{n_pass} 项 PASS"
             f"{'' if n_pass == len(checks) else '，存在 FAIL 项，请勿引用结果'}")
    L.append("")
    L.append("—— 全局 Moran's I ——")
    for _, r in gdf.iterrows():
        L.append(
            f"  {r['variable']:<22} I={r['moran_i']:+.4f} E[I]={r['expected_i']:+.6f} "
            f"z={r['z_sim']:+.2f} p={r['p_sim_two_sided']:.4f} "
            f"{'**显著(0.01)' if r['sig_0.01']=='是' else ('*显著(0.05)' if r['sig_0.05']=='是' else '不显著')}"
        )
    L.append("")
    for var, var_cn in ((VAR_LN[0], VAR_LN[1]), (VAR_RAW[0], VAR_RAW[1])):
        L.append(f"—— 局部显著集聚（α=0.05，{var_cn}）——")
        sub = ldf[ldf["variable"] == var]
        for q in ("HH", "LL", "HL", "LH"):
            sig = sub[sub["cluster_p05"] == q].sort_values("local_i", ascending=(q == "LL"))
            if len(sig) == 0:
                L.append(f"  {q}: 无")
                continue
            head = "、".join(
                f"{r.city_name}({r.province_name},{r.value},p={r.p_sim:.3f})"
                for r in sig.head(20).itertuples()
            )
            more = f" 等 {len(sig)} 市" if len(sig) > 20 else ""
            L.append(f"  {q}: {head}{more}")
        L.append("")
    L.append("复现: python scripts/99_moran_log_knn5.py（幂等，逐字节一致）")
    OUT_REPORT.write_text("\n".join(L), encoding="utf-8")

    print("\n".join(L))
    return 0 if n_pass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
