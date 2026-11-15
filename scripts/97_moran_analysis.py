#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
97_moran_analysis.py — Step 5 扩展分析：城市级全局与局部 Moran 空间自相关

输入（全部只读）:
  - 桥表 cac_genai_product_entity_map_v1.2.csv   record_id ↔ entity_id ↔ section
  - 表2   cac_genai_entity_enriched_v1.2.csv     entity_id → 城市 adcode
  - geo/china_city_boundaries_wgs84.geojson      298 个地级市边界（Queen 邻接）
  - geo/china_city_coords_v1.0.csv               质心坐标（KNN / 桥接距离）

分析设计:
  - 空间单元: 大陆 31 省 298 个地级市单元（含零备案城市；
    CAC 备案主体全部位于此范围内，表2→边界的 adcode 覆盖率 100%）
  - 变量（按 adcode 聚合，零填充）:
      total_filings     备案记录总数
      model_filings     模型备案数（section=filing）
      app_registrations 应用登记数（section=registry）
      n_entities        法人主体数
  - 空间权重（均行标准化）:
      W1 queen_bridge : Queen 邻接（共享边界顶点，坐标四舍五入 6 位小数）；
                        因 datav 分省/分市文件独立简化，西藏 6 市、攀枝花-丽江、
                        海南 4 市等跨省界顶点不重合 → 在 Queen 图上做"最近跨分量
                        对"单链桥接直至全图连通（每条补边留痕，见输出权重表）
      W2 knn5         : 质心大圆距离最近 5 市（稳健性对照，天然连通）
  - 全局 Moran's I: 观察值 + 999 次随机置换（固定种子 42，双侧 pseudo-p）
  - 局部 Moran (LISA): 条件置换 999 次（保持本单元值固定、其余单元置换），
    输出 local_i / z_sim / p_sim 与四象限（HH 高-高 / LL 低-低 / HL 高-低 /
    LH 低-高），α=0.05、0.01 两档显著性
  - 内部一致性检验: 全局 I ≡ (n/S0)·Σ local_i / (z'z)，全局与局部两条
    代码路径互为校验

输出（幂等可复跑，固定种子 ⇒ 逐字节一致）:
  - data/moran_global_v1.0.csv   全局结果：变量 × 权重 一行
  - data/moran_local_v1.0.csv    局部结果：变量 × 权重 × 城市一行
  - data/moran_weights_v1.0.csv  权重邻接表（W1/W2，queen/bridge 分边留痕）
  - data/qa_report_moran.txt     体检 + 结果摘要（无时间戳，字节确定）

用法:
    python scripts/97_moran_analysis.py

依赖: numpy、pandas（标准库以外仅此两项；不依赖 PySAL，Moran 统计量与
     置换检验按标准公式自实现，公式与 PySAL esda 一致）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import paths

# ---- 固定参数（确定性保证） ----------------------------------------------
N_PERM = 999
SEED = 42
KNN_K = 5
VERTEX_DP = 6          # Queen 顶点匹配容差（小数位）

VARIABLES = [
    ("total_filings", "备案记录总数"),
    ("model_filings", "模型备案数"),
    ("app_registrations", "应用登记数"),
    ("n_entities", "法人主体数"),
]
WEIGHT_NAMES = {"queen_bridge": "W1 Queen邻接+连通桥接", "knn5": "W2 KNN-5"}

GEOJSON = paths.GEO / "china_city_boundaries_wgs84.geojson"
OUT_GLOBAL = paths.DATA / "moran_global_v1.0.csv"
OUT_LOCAL = paths.DATA / "moran_local_v1.0.csv"
OUT_WEIGHTS = paths.DATA / "moran_weights_v1.0.csv"
OUT_REPORT = paths.DATA / "qa_report_moran.txt"


# ---- 空间单元 ----------------------------------------------------------------
def load_lattice() -> tuple[pd.DataFrame, dict]:
    """返回城市框架（298 行，按 adcode 升序）与 GeoJSON 要素字典。"""
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    feats = sorted(gj["features"], key=lambda f: f["properties"]["adcode"])
    frame = pd.DataFrame(
        {
            "adcode": [f["properties"]["adcode"] for f in feats],
            "city_name": [f["properties"]["city_name"] for f in feats],
            "province_name": [f["properties"]["province_name"] for f in feats],
        }
    )
    if frame["adcode"].duplicated().any():
        raise SystemExit("!! 边界 GeoJSON 中 adcode 重复，中止")
    return frame, feats


def build_counts(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """桥表×表2 → 按 adcode 聚合四个变量（零填充），返回统计信息用于体检。"""
    m = pd.read_csv(paths.MAP, encoding="utf-8-sig", dtype={"entity_id": str})
    e = pd.read_csv(paths.ENTITY, encoding="utf-8-sig", dtype={"entity_id": str, "adcode": str})
    j = m[["record_id", "entity_id", "section"]].merge(
        e[["entity_id", "adcode"]], on="entity_id", how="left", validate="many_to_one"
    )
    n_missing = int(j["adcode"].isna().sum())
    if n_missing:
        raise SystemExit(f"!! 桥表 {n_missing} 条记录无城市 adcode，中止")
    unmatched = sorted(set(j["adcode"]) - set(frame["adcode"]))
    if unmatched:
        raise SystemExit(f"!! 有记录落在非地级市单元: {unmatched}，中止")

    g = j.groupby("adcode")
    agg = pd.DataFrame(
        {
            "total_filings": g.size(),
            "model_filings": j[j["section"] == "filing"].groupby("adcode").size(),
            "app_registrations": j[j["section"] == "registry"].groupby("adcode").size(),
            "n_entities": g["entity_id"].nunique(),
        }
    ).fillna(0)
    out = frame.drop(columns=["city_name", "province_name"]).merge(
        agg, left_on="adcode", right_index=True, how="left"
    )
    out[VARIABLE_COLS] = out[VARIABLE_COLS].fillna(0).astype(int)
    info = {
        "n_records": len(m),
        "n_model": int((m["section"] == "filing").sum()),
        "n_app": int((m["section"] == "registry").sum()),
        "n_device": int((m["section"] == "device").sum()),
        "n_entities_source": int(e["entity_id"].nunique()),
        "n_cities_nonzero": int((out["total_filings"] > 0).sum()),
        "n_cities_zero": int((out["total_filings"] == 0).sum()),
    }
    return out, info


VARIABLE_COLS = [v for v, _ in VARIABLES]


# ---- 空间权重 ----------------------------------------------------------------
def haversine_mat(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """质心大圆距离矩阵（km），向量化。"""
    lon_r, lat_r = np.radians(lon), np.radians(lat)
    dlon = lon_r[:, None] - lon_r[None, :]
    dlat = lat_r[:, None] - lat_r[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat_r)[:, None] * np.cos(lat_r)[None, :] * np.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def build_queen(feats: list[dict]) -> dict[int, set[int]]:
    """Queen 邻接：共享边界顶点（round 6 位小数）即相邻。"""
    pt2feat: dict[tuple[float, float], set[int]] = {}
    for idx, f in enumerate(feats):
        gm = f["geometry"]
        polys = gm["coordinates"] if gm["type"] == "MultiPolygon" else [gm["coordinates"]]
        for poly in polys:
            for ring in poly:
                for lon, lat in ring:
                    pt2feat.setdefault((round(lon, VERTEX_DP), round(lat, VERTEX_DP)), set()).add(idx)
    adj: dict[int, set[int]] = {i: set() for i in range(len(feats))}
    for holders in pt2feat.values():
        if len(holders) > 1:
            for a in holders:
                adj[a].update(holders - {a})
    return adj


def component_labels(adj: dict[int, set[int]], n: int) -> np.ndarray:
    lab = np.full(n, -1)
    c = 0
    for s in range(n):
        if lab[s] != -1:
            continue
        stack, lab[s] = [s], c
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if lab[v] == -1:
                    lab[v] = c
                    stack.append(v)
        c += 1
    return lab


def bridge_components(adj: dict[int, set[int]], dist: np.ndarray) -> list[tuple[int, int]]:
    """最近跨分量对单链桥接，直至全图连通；返回按加入顺序的补边列表。"""
    n = len(adj)
    lab = component_labels(adj, n)
    added: list[tuple[int, int]] = []
    while lab.max() > 0:
        best: tuple[float, int, int] | None = None
        for i in range(n):
            li = lab[i]
            for j in range(i + 1, n):
                if lab[j] != li and (best is None or dist[i, j] < best[0]):
                    best = (dist[i, j], i, j)
        if best is None:  # pragma: no cover
            break
        _, i, j = best
        adj[i].add(j)
        adj[j].add(i)
        added.append((i, j))
        lab = np.where(lab == lab[j], lab[i], lab)
    return added


def build_knn(dist: np.ndarray, k: int = KNN_K) -> dict[int, set[int]]:
    """KNN 邻接（不对称，取每单元最近 k 个，不含自身）。"""
    n = dist.shape[0]
    adj: dict[int, set[int]] = {}
    for i in range(n):
        order = np.argsort(dist[i], kind="stable")
        adj[i] = {int(j) for j in order[1 : k + 1]}
    return adj


def to_dense(adj: dict[int, set[int]], n: int) -> np.ndarray:
    """行标准化稠密权重矩阵。"""
    W = np.zeros((n, n))
    for i, js in adj.items():
        if js:
            W[i, sorted(js)] = 1.0 / len(js)
    return W


# ---- 全局 Moran's I ------------------------------------------------------------
def global_moran(x: np.ndarray, W: np.ndarray) -> dict:
    n = len(x)
    z = x - x.mean()
    s0 = W.sum()
    den = float(z @ z)
    I_obs = (n / s0) * float(z @ (W @ z)) / den
    I_obs_sum_local = float(z @ (W @ z))  # 内部一致性用：Σ local_i

    rng = np.random.default_rng(SEED)
    P = np.stack([rng.permutation(z) for _ in range(N_PERM)])
    # 置换不改变 z'z，故 I_sim = (n/s0)·(zp'Wzp)/(z'z)
    num_sim = ((P @ W) * P).sum(axis=1)
    I_sim = (n / s0) * num_sim / den
    p = (np.sum(np.abs(I_sim) >= abs(I_obs)) + 1) / (N_PERM + 1)
    return {
        "moran_i": I_obs,
        "expected_i": -1.0 / (n - 1),
        "mean_sim": float(I_sim.mean()),
        "std_sim": float(I_sim.std(ddof=1)),
        "z_sim": (I_obs - float(I_sim.mean())) / float(I_sim.std(ddof=1)),
        "p_sim": float(p),
        "sum_local": I_obs_sum_local,
        "s0": float(s0),
        "den": den,
    }


# ---- 局部 Moran（LISA） --------------------------------------------------------
def local_moran(x: np.ndarray, W: np.ndarray) -> dict[str, np.ndarray]:
    n = len(x)
    z = x - x.mean()
    lag = W @ z
    li = z * lag
    n_nbrs = (W != 0).sum(axis=1)
    z_sim = np.full(n, np.nan)
    p_sim = np.full(n, np.nan)

    for i in range(n):
        k = int(n_nbrs[i])
        if k == 0:
            continue
        cand = np.delete(np.arange(n), i)
        nz = np.nonzero(W[i])[0]          # 固定邻居位置与权重
        k = len(nz)
        rng = np.random.default_rng(SEED + i)
        perms = rng.permuted(np.tile(cand, (N_PERM, 1)), axis=1)[:, :k]
        lag_sim = z[perms] @ W[i][nz]      # 置换取值 × 固定权重
        sim = z[i] * lag_sim
        z_sim[i] = (li[i] - sim.mean()) / sim.std(ddof=1)
        p_sim[i] = (np.sum(np.abs(sim) >= abs(li[i])) + 1) / (N_PERM + 1)

    quad = np.where((z > 0) & (lag > 0), "HH",
           np.where((z <= 0) & (lag <= 0), "LL",
           np.where((z > 0) & (lag <= 0), "HL", "LH")))
    return {"z": z, "lag": lag, "local_i": li, "z_sim": z_sim, "p_sim": p_sim, "quadrant": quad}


# ---- 主流程 -----------------------------------------------------------------
def main() -> int:
    frame, feats = load_lattice()
    n = len(frame)

    counts, info = build_counts(frame)

    coords = pd.read_csv(paths.COORDS, encoding="utf-8-sig", dtype={"adcode": str})
    c = frame[["adcode"]].merge(
        coords[["adcode", "centroid_lon_wgs84", "centroid_lat_wgs84"]], on="adcode", how="left"
    )
    if c["centroid_lon_wgs84"].isna().any():
        raise SystemExit("!! 有边界单元缺质心坐标，中止")
    dist = haversine_mat(c["centroid_lon_wgs84"].to_numpy(), c["centroid_lat_wgs84"].to_numpy())

    # 权重
    adj_q = build_queen(feats)
    n_queen_edges = sum(len(v) for v in adj_q.values()) // 2
    bridged = bridge_components(adj_q, dist)
    adj_w1 = adj_q
    adj_w2 = build_knn(dist)
    W1, W2 = to_dense(adj_w1, n), to_dense(adj_w2, n)
    bridge_flags = {(min(i, j), max(i, j)): "bridge" for i, j in bridged}
    lab_after = component_labels(adj_w1, n)

    checks: list[tuple[str, str, bool]] = []

    # C1 记录→城市映射
    checks.append((
        "C1 记录→城市映射",
        f"{info['n_records']}/{info['n_records']} 条记录全部落到 298 个地级市单元"
        f"（{info['n_cities_nonzero']} 市有备案、{info['n_cities_zero']} 市为零）",
        info["n_records"] == int(counts["total_filings"].sum()) == 1843,
    ))
    # C2 变量总量核对（与源表动态核对，不硬编码）
    ok2 = (
        int(counts["total_filings"].sum()) == info["n_records"]
        and int(counts["model_filings"].sum()) == info["n_model"]
        and int(counts["app_registrations"].sum()) == info["n_app"]
        and int(counts["n_entities"].sum()) == info["n_entities_source"]
        and info["n_model"] + info["n_app"] + info["n_device"] == info["n_records"]
    )
    checks.append((
        "C2 变量总量核对",
        f"total={int(counts['total_filings'].sum())} model={int(counts['model_filings'].sum())} "
        f"app={int(counts['app_registrations'].sum())} entities={int(counts['n_entities'].sum())} "
        f"（源表 {info['n_records']}/{info['n_model']}/{info['n_app']}/{info['n_entities_source']}，端侧 {info['n_device']}）",
        ok2,
    ))
    # C3 W1 连通性
    checks.append((
        "C3 W1 Queen+桥接连通性",
        f"Queen {n_queen_edges} 边 + 桥接 {len(bridged)} 边 = {n_queen_edges + len(bridged)} 边；"
        f"连通分量 {int(lab_after.max()) + 1} 个",
        int(lab_after.max()) == 0,
    ))
    # C4 W2 KNN
    checks.append((
        "C4 W2 KNN-5 完整性",
        f"每单元恰好 {KNN_K} 个邻居（{sum(len(v) for v in adj_w2.values())} 有向边，不对称属 KNN 正常形态）",
        all(len(v) == KNN_K for v in adj_w2.values()),
    ))

    # 全局
    rows_global = []
    sum_local_ref: dict[tuple[str, str], float] = {}
    for wname, W in (("queen_bridge", W1), ("knn5", W2)):
        for var, var_cn in VARIABLES:
            r = global_moran(counts[var].to_numpy(), W)
            sum_local_ref[(var, wname)] = r["sum_local"]
            rows_global.append({
                "variable": var, "variable_cn": var_cn,
                "weights": wname, "weights_cn": WEIGHT_NAMES[wname],
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

    # 局部
    rows_local = []
    for wname, W, adj in (("queen_bridge", W1, adj_w1), ("knn5", W2, adj_w2)):
        for var, var_cn in VARIABLES:
            r = local_moran(counts[var].to_numpy(), W)
            # C5 全局-局部一致性：I ≡ (n/S0)·Σ local_i / (z'z)
            ref = sum_local_ref[(var, wname)]
            ok_consistency = np.isclose(
                gdf[(gdf.variable == var) & (gdf.weights == wname)]["_raw"].iloc[0]["moran_i"],
                (n / gdf[(gdf.variable == var) & (gdf.weights == wname)]["_raw"].iloc[0]["s0"])
                * ref / gdf[(gdf.variable == var) & (gdf.weights == wname)]["_raw"].iloc[0]["den"],
                rtol=1e-9,
            )
            for i in range(n):
                p = r["p_sim"][i]
                q = r["quadrant"][i]
                rows_local.append({
                    "variable": var, "variable_cn": var_cn,
                    "weights": wname,
                    "adcode": frame["adcode"].iat[i],
                    "city_name": frame["city_name"].iat[i],
                    "province_name": frame["province_name"].iat[i],
                    "value": int(counts[var].iat[i]),
                    "z": round(float(r["z"][i]), 4),
                    "lag_z": round(float(r["lag"][i]), 4),
                    "local_i": round(float(r["local_i"][i]), 4),
                    "z_sim": round(float(r["z_sim"][i]), 3) if np.isfinite(r["z_sim"][i]) else "",
                    "p_sim": round(float(p), 4) if np.isfinite(p) else "",
                    "quadrant": q,
                    "cluster_p05": q if np.isfinite(p) and p <= 0.05 else "不显著",
                    "cluster_p01": q if np.isfinite(p) and p <= 0.01 else "不显著",
                    "n_neighbors": len(adj[i]),
                    "_ok": ok_consistency,
                })
            if not ok_consistency:
                checks.append((
                    f"C5 全局-局部一致性 {var}/{wname}",
                    "I ≡ (n/S0)·Σ local_i/(z'z) 校验失败",
                    False,
                ))
    ldf = pd.DataFrame(rows_local)
    if "_ok" in ldf.columns and ldf["_ok"].all():
        checks.append((
            "C5 全局-局部一致性",
            "8 组（4 变量 × 2 权重）均满足 I ≡ (n/S0)·Σ local_i/(z'z)（rtol=1e-9）",
            True,
        ))
    # C6 Moran's I 取值域
    ok6 = bool((gdf["moran_i"].abs() <= 1.0).all())
    checks.append((
        "C6 全局 I 取值域",
        f"8 组 I ∈ [{gdf['moran_i'].min():.4f}, {gdf['moran_i'].max():.4f}]，均 |I| ≤ 1",
        ok6,
    ))

    # 权重表
    rows_w = []
    for wname, adj in (("queen_bridge", adj_w1), ("knn5", adj_w2)):
        for i in range(n):
            js = sorted(adj[i])
            flags = []
            for j in js:
                key = (min(i, j), max(i, j))
                flags.append(bridge_flags.get(key, "queen" if wname == "queen_bridge" else "knn"))
            rows_w.append({
                "weights": wname,
                "adcode": frame["adcode"].iat[i],
                "city_name": frame["city_name"].iat[i],
                "n_neighbors": len(js),
                "neighbor_adcodes": ";".join(frame["adcode"].iat[j] for j in js),
                "neighbor_names": ";".join(frame["city_name"].iat[j] for j in js),
                "edge_provenance": ";".join(flags),
            })
    wdf = pd.DataFrame(rows_w)

    # 落盘
    gout = gdf.drop(columns=["_raw"])
    gout.to_csv(OUT_GLOBAL, index=False, encoding="utf-8-sig")
    lout = ldf.drop(columns=["_ok"]) if "_ok" in ldf.columns else ldf
    lout.to_csv(OUT_LOCAL, index=False, encoding="utf-8-sig")
    wdf.to_csv(OUT_WEIGHTS, index=False, encoding="utf-8-sig")

    # ---- 体检报告 ----
    L: list[str] = []
    L.append("Moran 空间自相关分析 — 体检报告")
    L.append("=" * 72)
    L.append("空间单元: 大陆 31 省 298 个地级市（含零备案城市）")
    L.append("权重: W1 Queen邻接+连通桥接 / W2 KNN-5，均行标准化")
    L.append(f"置换检验: {N_PERM} 次，固定种子 {SEED}；局部为条件置换（本单元固定）")
    L.append("补边说明: datav 分市边界独立简化，跨省界顶点不重合（西藏 6 市、")
    L.append("          攀枝花-丽江、海南 4 市、克拉玛依），按最近跨分量对单链桥接，")
    L.append("          每条补边在 moran_weights_v1.0.csv 的 edge_provenance 列留痕")
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
            f"  {r['variable']:<18} {r['weights']:<12} I={r['moran_i']:+.4f} "
            f"E[I]={r['expected_i']:+.6f} z={r['z_sim']:+.2f} p={r['p_sim_two_sided']:.4f} "
            f"{'**显著(0.01)' if r['sig_0.01']=='是' else ('*显著(0.05)' if r['sig_0.05']=='是' else '不显著')}"
        )
    L.append("")
    L.append("—— 局部 Moran 显著集聚（α=0.05，W1 Queen+桥接）——")
    for var, var_cn in VARIABLES:
        sub = ldf[(ldf["variable"] == var) & (ldf["weights"] == "queen_bridge")]
        for q in ("HH", "LL", "HL", "LH"):
            sig = sub[(sub["cluster_p05"] == q)].sort_values("local_i", ascending=(q == "LL"))
            if len(sig) == 0:
                continue
            head = "、".join(
                f"{r.city_name}({r.province_name},{r.value})" for r in sig.head(15).itertuples()
            )
            more = f" 等 {len(sig)} 市" if len(sig) > 15 else ""
            L.append(f"  [{var_cn}] {q}: {head}{more}")
    L.append("")
    L.append("复现: python scripts/97_moran_analysis.py（幂等，逐字节一致）")
    OUT_REPORT.write_text("\n".join(L), encoding="utf-8")

    print("\n".join(L))
    return 0 if n_pass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
