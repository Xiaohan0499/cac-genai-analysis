#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
paths.py — 版本号与产物路径的唯一来源。

升级版本只改这里一行，其余脚本全部自动跟随，避免"某些脚本还指着 v1.0"的漂移。
历史版本文件一律保留（DOI 需要可回溯），不覆盖不删除。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REFS = DATA / "refs"
RAW = ROOT / "raw"
GEO = ROOT / "geo"
REVIEW = ROOT / "review"

VERSION = "v1.2"

FILING = DATA / f"cac_genai_filing_{VERSION}.csv"
ENTITY = DATA / f"cac_genai_entity_enriched_{VERSION}.csv"
MAP = DATA / f"cac_genai_product_entity_map_{VERSION}.csv"

# 上一版（只读，用于差异比对与回退）
PREV_VERSION = "v1.1"
FILING_PREV = DATA / f"cac_genai_filing_{PREV_VERSION}.csv"
ENTITY_PREV = DATA / f"cac_genai_entity_enriched_{PREV_VERSION}.csv"
MAP_PREV = DATA / f"cac_genai_product_entity_map_{PREV_VERSION}.csv"

# 解析修复表：PDF 原文 → 规范名（逐条带证据，人工可复核）
ENTITY_REPAIR_TABLE = REFS / "pdf_entity_repair.csv"
# 人工审核补丁：审核意见以"补丁"形式沉淀，而不是覆盖整表
REVIEW_PATCH = REFS / "manual_review_patch.csv"

# ---- Step 4：应用→模型调用边表（表3）与应用审计表（表4）
EDGES = DATA / f"cac_genai_app_model_edges_{VERSION}.csv"
REVIEW_QUEUE = DATA / f"cac_genai_app_model_review_queue_{VERSION}.csv"
APP_AUDIT = DATA / f"cac_genai_app_audit_{VERSION}.csv"
RESEARCH_DIR = REFS / "table3_research"
MODEL_ALIAS = REFS / "model_brand_alias.csv"
OVERSEAS_GEO = REFS / "overseas_model_geo.csv"
# 人工复核补丁（表3 待核实队列的复核结论，2026-11）：以补丁形式并入，不覆盖整表
TABLE3_MANUAL = REFS / "table3_manual_review_v1.0.csv"
TABLE3_MANUAL_DATE = "2026-11-09"
# 人工复核删边补丁（v1.2 rev5）：原推测边删除、应用归入"确认无公开调用信息"
TABLE3_DELETION = REFS / "table3_edge_deletion_v1.0.csv"
TABLE3_DELETION_DATE = "2026-11-11"
COORDS = GEO / "china_city_coords_v1.0.csv"
