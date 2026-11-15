# Spatial Clustering of China's Generative AI Filings — Analysis Code

Reproduction code for the Moran's I spatial-autocorrelation analysis and the
submission figure (LISA clusters + cross-city model-invocation flows,
SAGE journal format) based on the **China Generative AI Filing Registry**.

**One command reproduces everything — analysis, figure, and 300-dpi TIFF:**

```bash
python scripts/102_reproduce_submission_figure.py
```

The pipeline runs in ~20 seconds and verifies itself at every stage: the
regression anchors below are asserted programmatically, so if anything drifts
(for example, an altered input file), the run stops with an explicit error.

---

## 1. Data requirement (not included in this repository)

This repository contains **code only**. All input data are read from the
dataset published on Zenodo and must be downloaded separately:

> Shi, Xiaohan (2026). *China Generative AI Filing Registry: City-Level Panel
> and App-Model Invocation Network, 2023–2026* (Version v2) [Data set].
> Zenodo. https://zenodo.org/records/24192455
> (DOI: 10.5281/zenodo.24192455, CC BY 4.0)

Download `cac_genai_full_v1.2.zip` (23.4 MB) from the record above.

Only four read-only input files are needed by this analysis:

| File (in the dataset archive) | Used by | Content |
|---|---|---|
| `data/cac_genai_product_entity_map_v1.2.csv` | 99 | Product–entity bridge (record_id ↔ entity_id) |
| `data/cac_genai_entity_enriched_v1.2.csv` | 99 | Table 2: entities → city adcode |
| `data/cac_genai_app_model_edges_v1.2.csv` | 101 | Table 3: 778 app→model invocation edges |
| `geo/china_city_coords_v1.0.csv` | 99, 101 | Prefecture centroids (lon/lat, WGS84) |

### Directory layout

`scripts/paths.py` resolves the project root as the parent of `scripts/` and
expects `data/` and `geo/` there. Either of the following layouts works:

- **Option A (recommended):** clone this repository, then extract the dataset
  archive and copy its `data/` and `geo/` folders into the repository root.
  They are covered by `.gitignore` and will never be committed.
- **Option B:** extract the dataset archive, then copy this repository's
  `scripts/` folder into the extraction root.

## 2. Environment

- Python 3.10+
- Stages A (analysis) and B (figure, SVG): `numpy`, `pandas` only — no PySAL
  dependency; all formulas are implemented from scratch and match PySAL `esda`.
- Stage C (300-dpi TIFF export): additionally `Pillow` and the
  [`agent-browser`](https://www.npmjs.com/package/agent-browser) CLI with its
  Chromium runtime (`npm install -g agent-browser && agent-browser install`).
  Set `AGENT_BROWSER_EXE` if the executable is not on your PATH.
  On systems without a browser runtime (e.g. some CI runners), use
  `--skip-tiff` — the SVG master is itself a valid vector submission format.

```bash
pip install -r requirements.txt
```

## 3. One-command reproduction

```bash
python scripts/102_reproduce_submission_figure.py
```

Stages and built-in checks (any failure aborts with exit code 1):

| Stage | Script | Output | Verified by 102 |
|---|---|---|---|
| A | `99_moran_log_knn5.py` | `data/moran_log_global_v1.0.csv`, `data/moran_log_local_v1.0.csv`, `data/qa_report_moran_log.txt` | Global I = +0.1737 (±5e-4), z = +5.26, p = 0.001; LISA: HH 18 / LH 7 / HL 0 / LL 0 / not significant 273 |
| B | `101_lisa_flow_map.py` | `data/moran_lisa_flow_v1.3.svg` (170-mm SAGE layout) | Single 5° lattice (no duplicated grid lines); all text within canvas, pairwise non-overlapping, ≥ 7 pt |
| C | `101b_flow_tiff.py` | `data/moran_lisa_flow_v1.3_sage_170mm_300dpi.tiff` | 2008 × 1568 px, 300 dpi, 170.0 mm physical width, LZW |

Useful flags: `--skip-moran` (reuse existing Stage-A results), `--skip-tiff`
(SVG only), `--qa-only` (validate existing outputs without re-computing).

The figure is deterministic: fixed permutation seed (42) ⇒ identical runs
produce byte-identical outputs.

## 4. Reference results

- **Variable:** number of filing records per city = model filings +
  application registrations pooled (1,836 records = 1,843 total − 7
  device-side filings), ln(1+y) transformed.
- **Weights:** KNN-5 on great-circle centroid distances, row-standardized.
  **Test:** 999 permutations (global, seed 42); conditional-permutation LISA,
  999 draws, α = 0.05.
- **Global Moran's I (ln-transformed):** I = +0.1737, z = +5.26, p = 0.001
  (significant at 1%).
- **Contrast (raw counts):** I = +0.0314, z = +1.42, p = 0.061
  (not significant) — the log transform is what stabilises the zero-inflated
  distribution.
- **Significant HH (18 cities):** Beijing, Shanghai, Guangzhou, Shenzhen,
  Tianjin, Suzhou, Wuxi, Changzhou, Nantong, Zhenjiang, Ningbo, Jiaxing,
  Huzhou, Tangshan, Chengde, Zhangjiakou, Zhuhai, Dongguan — forming three
  cluster belts (Beijing–Tianjin–Hebei, Yangtze River Delta, Pearl River
  Delta).
- **Significant LH (7 cities):** Langfang, Zhongshan, Huizhou, Zhoushan,
  Shaoxing, Ma'anshan, Xuancheng — all with zero filings (hub shadow effect).
- No significant LL or HL clusters (a property of the zero-inflated
  distribution).

## 5. Repository contents

| File | Purpose |
|---|---|
| `scripts/102_reproduce_submission_figure.py` | One-command orchestrator: Stage A → B → C with per-stage assertions |
| `scripts/99_moran_log_knn5.py` | Main analysis script (ln(1+y) × KNN-5) |
| `scripts/97_moran_analysis.py` | Function library reused by 99 via importlib (weights, permutations, Moran estimators) |
| `scripts/100_moran_lisa_lonlat.py` | Standalone LISA lon/lat-grid figure (Chinese + English SVG; not part of the 102 chain) |
| `scripts/101_lisa_flow_map.py` | Submission figure: LISA clusters + call-flow arcs, two panels (mainland / overseas), 170-mm SAGE layout |
| `scripts/101b_flow_tiff.py` | Rasterises the SVG to a 300-dpi LZW TIFF via headless Chromium + Pillow |
| `scripts/paths.py` | Central version and path conventions (expects `data/` and `geo/` beside `scripts/`) |
| `requirements.txt` | Python dependencies |
| `LICENSE` | MIT License (code) |
| `.gitignore` | Keeps data files out of the repository |

## 6. Notes

- **Figure compliance.** Both figure panels are pure longitude/latitude grids
  with city-centroid scatter points — they contain no administrative
  boundaries and no coastlines, and are therefore not maps.
- **Device-side filings.** The 7 device-side records are excluded from the
  spatial variable because they are registered in a separate regulatory
  section and their filing location (registrant HQ) is semantically decoupled
  from where the embedded model is actually served. A sensitivity check
  including them yields I = +0.1772 (z = +5.36, p = 0.001) with an identical
  set of significant cities.
- **Analysis vs. dataset code.** The full data-construction pipeline (112
  automated checks) ships inside the Zenodo archive; this repository only
  hosts the downstream spatial-analysis code.

## 7. License and citation

If you use this code, please cite both the dataset and this repository:

> Shi, Xiaohan (2026). *China Generative AI Filing Registry: City-Level Panel
> and App-Model Invocation Network, 2023–2026* (Version v2) [Data set].
> Zenodo. https://zenodo.org/records/24192455

- **Code** (this repository): MIT License — see [LICENSE](LICENSE).
- **Dataset** (Zenodo): CC BY 4.0.
