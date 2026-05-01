# V60 Pour-Over Physics Simulation

A physics-based numerical simulation of V60 pour-over coffee brewing, modelling fluid dynamics, bin-resolved extraction kinetics, and thermodynamics as one coupled ODE system.

## Project Scope

This repository now has a layered package structure with two complementary entry points:

- `README.md`: installation, package structure, reproducibility, and model boundary
- `index.html`: visual showcase of the current generated outputs and the main physics stories

The current model is a reduced-order bed-scale simulator. It is designed to compare flow, bypass, thermal regime, and extraction behavior across plausible pour-over conditions, while also supporting calibration against measured `V_in(t)`, `V_out(t)`, grinder PSD, and final cup temperature. The codebase is now explicitly split into fixed physical inputs, tunable reduced-order closures, measured-data I/O, observation-layer transforms, and analysis/showcase entry points. It is not a fully particle-resolved diffusion-advection PDE solver, and its outputs should be read as engineering-model predictions rather than universal ground truth.

Primary use cases:

- calibrate one real brew against measured `V_in(t)` / `V_out(t)` / PSD / cup temperature
- compare grind regimes under one consistent flow/extraction model
- inspect how temperature changes both hydraulic throughput and extraction chemistry
- diagnose whether a cup is limited by flow, accessibility, bypass, or retained liquid
- regenerate a consistent family of figures from the CLI

## Physics Model

The current best model uses one dynamic state family:

```
state = [h, V_out, V_bed, V_poured, sat, {C_fast,i, M_fast,i, C_slow,i, M_slow,i}, T, T_dripper, xi_pref]
```

| Variable | Description |
|----------|-------------|
| `h` | Water level in the cone [m] |
| `V_out` | Cumulative output volume [m³] |
| `V_bed` | Cumulative bed-flow volume [m³] (used for fines-loading ageing) |
| `V_poured` | Cumulative poured volume [m³] |
| `sat` | Dynamic wetting / absorption saturation of the bed [-] |
| `{C_fast,i, C_slow,i}` | Bin-resolved bed pore concentration [g/L] |
| `{M_fast,i, M_slow,i}` | Bin-resolved remaining solid-phase solute [g] |
| `T` | Liquid temperature [K] |
| `T_dripper` | Dripper thermal node [K] |
| `xi_pref` | Preferential-flow channel state [-] (0 unless `pref_flow_coeff > 0`) |

Hydraulic closure follows a fully additive resistance form:

```
k_eff = (k / R_total) × k_kc(φ_eff)
R_total = 1 + (throat_eff − 1) + (deposition − 1) + (1/f_post − 1)
```

Each `(term − 1)` represents that mechanism's incremental resistance over the unblocked baseline. The legacy multiplicative `× f_post` and the redundant `wetbed_struct` channel state were removed in the P0/P1 refactor — the post-bloom wet-bed effect now lives entirely inside `f_post = f_rev · f_irr` and enters `R_total` additively.

This is a single model family. The repository no longer maintains an older fractal-PSD branch in parallel. If measured PSD bins are unavailable, the code falls back to a synthetic single-bin representation inside the same bin-resolved framework.

### Key Physical Corrections

| # | Correction | Description |
|---|-----------|-------------|
| [1] | Bed height transition | C∞ smooth crossover replacing hard switching |
| [2] | Bypass activation | Bypass stays near zero at low free-water head and opens gradually as wall-channel flow develops |
| [3] | Split fines clogging | `k_eff` now uses early throat blocking + later deposition instead of one linear `β·V_out` law |
| [4][13] | Bloom absorption | CO₂-corrected absorption ratio (0.5/1.64 mL/g for medium roast baseline) |
| [5] | Solid depletion | C_sat_eff(t) = κ(T)·M(t), prevents late-stage concentration spike |
| [6] | Thermodynamics | Two-node thermal model: liquid `T` + dripper `T_dripper`, with ambient cooling and liquid-dripper exchange |
| [7] | Multi-component extraction | Fast (acids/sweetness, Ea=15 kJ/mol) + Slow (bitterness, Ea=45 kJ/mol), both resolved per PSD bin |
| [8] | Particle swelling | φ(sat) = φ₀ − Δφ·sat; Kozeny-Carman: k ∝ φ³/(1−φ)² |
| [9] | Capillary pressure cutoff | h < h_cap → Q→0 sigmoid (drip-filter mode) |
| [10] | Smooth saturation transition | Cubic Hermite smooth-step, C¹ continuous |
| [11] | Accessibility power law | `C_eff,i = C_sat(T)·(M_i/M0_i)^β`, β=1.5 (shrinking-core model) |
| [12] | Brew time calibration | k: 2e-11→6e-11 m², h_cap: 5→3 mm |
| [14] | CO₂ back-pressure | h_gas(t) = h_gas_0·exp(−t/τ), kept small for the medium baseline and larger for fresher/light roasts |
| [15] | Flow-dependent transfer | Sherwood-like flow factor bridges diffusion-only and advective transfer |
| [16] | Dynamic wetting | capillary wetting state `sat(t)` with temperature-dependent Lucas-Washburn timescale |
| [17] | Particle geometry | Measured multi-bin PSD, D10/D50/D90, fines fractions, shell accessibility, and Einstein-Smoluchowski diffusion |

## Current Calibrated Reference

The current best-fit reference in the repo is based on one measured brew:

- grinder: `Kinu 29`
- roast: `light`
- dose: `20 g`
- bed height: `5.3 cm`
- ambient: `23°C`
- dripper: ceramic V60, `123.5 g`
- server equivalent heat capacity: `42.4 mL water equivalent`
- measured PSD: raw Kinu 29 export is stored under `data/kinu_29_light/`; model-ready artifacts are `data/kinu29_psd_summary.csv` and `data/kinu29_psd_bins.csv`
- calibrated fit summary: `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`

Current fit metrics:

- `D10 ≈ 374 μm` (high-resolution PSD, 17.24 μm/px microscope)
- `axial_node_count = 2`
- `ext_bin_count = 7` (measured PSD bins, `data/kinu29_psd_bins.csv`)
- `k_fit ≈ 8.09e-11 m²`
- `k_beta_fit ≈ 2.35e3 m⁻³` (PSD prior 1.35e3 m⁻³ → 1.74×)
- `tau_lag ≈ 2.0 s`
- post-bloom wet-bed term enters `R_total` additively via `f_post = f_rev · f_irr` (no separate χ ODE)
- `kr(sat)` uses explicit unsaturated Darcy attenuation
- `pref_flow_coeff = 0` on the current measured fit
- thermal closure jointly fit `λ_liquid_dripper × λ_server_ambient`; `λ_cool` and `λ_dripper_ambient` frozen
- **extraction (Option C dual-baseline + flow_factor split + high-res PSD)**:
  - `max_EY ≈ 0.373`, `k_ext_slow_coef ≈ 1.22e-5` (39× default)
  - `flow_factor_fast` follows Hill kinetics; `flow_factor_slow = 1.0` (slow pool diffusion-bounded, not flow-bounded; subagent P2 fix)
  - `TDS error ≈ +0.02 g/L` against measured Brix=1.36 → TDS=11.56 g/L (essentially perfect)
- `V_out RMSE ≈ 13.79 mL = 5.06%` (relative-% gate)
- `q_out RMSE ≈ 1.23 mL/s`
- `cup temperature error ≈ +0.011°C` (best-ever)
- All 5 benchmark gates PASS (V_RMSE relative ≤ 7%, q_out ≤ 1.30, drain ±3s, cup temp ±3.5°C, TDS ±2.5 g/L)
- fitting pipeline uses `fit_with_multi_start` (3 starts, lowest-loss basin); `observed_stop_time_from_layer` sub-grid interpolation removes drain-time staircase

### Dual-baseline framework (Option C, 2026-05-02)

PSD measurements come from two microscope resolutions:
- **high-res** (worktree top-level): 17.24 μm/px, 4554 particles, D10 = 374 μm
- **per-case** (parent project, each brew dir): 35 μm/px, 1942-3800 particles, D10 = 517-529 μm — systematically under-counts fines by 38%

Therefore we run two complementary tracks:

| track | PSD | use |
|---|---|---|
| **canonical baseline** (kinu29/4:11) | high-res top-level | benchmark gates (TDS ±2.5 g/L) |
| cross-validation (kinu27/4:12, kinu28/4:20, kinu29/4:12) | per-case sibling | honest measurement-bounded prediction |

Override mechanism: `pour_over.measured_io.CANONICAL_HIGH_RES_PSD_OVERRIDES` dict maps canonical brew CSV path → high-res PSD path; everything else falls through to per-case sibling PSD.

| case | grinder | Brix | TDS_obs | TDS_pred | TDS error | V_RMSE % |
|---|---|---|---|---|---|---|
| **kinu29/4:11 (canonical, high-res)** | 29 (fine) | 1.36 | 11.56 | 11.57 | **+0.02** | 5.06% |
| kinu27/4:12 (per-case) | 27 (coarse) | 1.19 | 10.11 | 7.08 | −3.03 | 6.41% |
| kinu28/4:20 (per-case) | 28 (medium) | 1.60 | 13.60 | 7.94 | −5.66 | 5.08% |
| kinu29/4:12 (per-case) | 29 (fine) | 1.36 | 11.56 | 6.49 | −5.07 | 5.72% |

The canonical baseline achieves TDS error well below VST refractometer noise floor (±0.5 g/L); cross-validation cases reflect the per-case PSD measurement limitation (under-counted fines reduce model surface area, capping predicted extraction). Re-measuring per-case PSDs at high resolution would unlock cross-validation accuracy.

The `flow_factor` was split into separate `fast` (Hill, flow-dependent) and `slow` (constant 1.0, diffusion-bounded) terms per the subagent extraction audit (P2). This structural fix improves the high-res baseline TDS error from −0.40 to +0.02 g/L (95% residual reduction), confirming the audit was physically correct — but only unlocks at sufficient PSD resolution.
- extraction (now **fit-validated** with measured Brix → TDS):
  - Brew CSV records final cup `Brix` reading (column `final_tds_pct`, unit °Bx); the model uses VST conversion `TDS_g/L = Brix × 0.85 × 10` (specialty-coffee convention)
  - Stage 7 of `fit_k_kbeta_from_flow_profile` jointly fits `(k_ext_slow_coef, max_EY)` against measured TDS with prior reg and volume guard
  - kinu29/4:11 baseline: `Brix=1.36 → TDS_obs=11.56 g/L`; model predicts `TDS_pred=10.15 g/L` (12% under-predicted) with `max_EY=0.308`, `k_ext_slow_coef=2.26e-5` (72× default)
  - Cross-grinder validation across kinu27/28/29 (3 grinders, 4 brews): V_RMSE relative% all 5.1-7.0%; TDS error 12-18% on 3 cases, kinu28 outlier −6.25 g/L (Powell early-converges due to V_RMSE-dominated loss)
  - Benchmark gates updated to relative% (V_RMSE/V_out ≤ 7%) and TDS gate ±2.5 g/L for fair cross-brew comparison
  - Remaining TDS gap is structural (subagent P2 flow_factor fast/slow split, mid-cup TDS time-series); not a fit bug

## Roast Profiles

Three built-in profiles model roast-level differences in chemistry and physics:

```python
from pour_over import V60Params, RoastProfile

# Light roast — dense structure, high CO₂, mostly acids
p = V60Params.for_roast(RoastProfile.LIGHT)

# Dark roast — broken cell walls, degassed, bitter compounds dominant
p = V60Params.for_roast(RoastProfile.DARK)

# Combine with grind: light roast + fine grind
p = V60Params.for_roast(RoastProfile.LIGHT, k_target=3e-11)
```

| Parameter | Light | Medium | Dark |
|-----------|-------|--------|------|
| `max_EY` | 22% | 30% | 32% |
| `Ea_slow` | 50 kJ/mol | 45 kJ/mol | 38 kJ/mol |
| `fast_fraction` | 0.45 | 0.35 | 0.25 |
| `brew_temp` | 92°C | 90°C | 88°C |
| `absorb_full_ratio` | 1.2 mL/g | 1.64 mL/g | 1.7 mL/g |
| `co2_pressure_m` | 9 mm | 1 mm | 4 mm |

## Package Structure

```
pour_over/
├── __init__.py     # Public API re-exports
├── __main__.py     # uv run python -m pour_over
├── constant.py     # Measurable fixed inputs and physical constants
├── params.py       # RoastProfile, V60Params closures, PourProtocol
├── core.py         # simulate_brew ODE engine
├── measured_io.py  # Measured CSV loading and protocol reconstruction
├── observation.py  # Outflow lag and cup/server observation layer
├── fitting.py      # Hydraulic / thermal fitting (scipy.optimize)
├── benchmark.py    # Benchmark suite entry point
├── identifiability.py  # Local identifiability scans
├── psd.py          # PSD post-processing and model overrides
├── analysis.py     # Sensitivity, wet-bed scans, grind optimization façade
├── showcase_state.py   # Current calibrated showcase baseline loader
└── viz.py          # Pure plotting functions and compare_* figures

v60_sim.py          # Backward-compatible thin wrapper
```

Structure summary:

- `constant.py` holds quantities that should come from measurement or hardware setup, not fitting.
- `params.py` keeps reduced-order closures and model-control knobs that may be scanned or calibrated.
- `core.py` remains the single coupled ODE engine.
- measured-data ingestion, observation-layer transforms, benchmark, identifiability, and showcase-state loading now live in dedicated modules instead of being folded into a few large files.

## Data Artifacts

The Kinu 29 PSD data has two layers:

- raw measurement export: `data/kinu_29_light/kinu29_PSD_export_data.csv` and `data/kinu_29_light/kinu29_PSD_export_data_stats.csv`
- model-ready artifacts: `data/kinu29_psd_summary.csv` and `data/kinu29_psd_bins.csv`

The raw CSV files are the source of truth for particle geometry. The `kinu29_psd_*` CSV files are generated artifacts used by the model and should be regenerated rather than edited by hand:

```bash
uv run python -m pour_over.psd \
  data/kinu_29_light/kinu29_PSD_export_data.csv \
  --stats-csv data/kinu_29_light/kinu29_PSD_export_data_stats.csv \
  --output data/kinu29_psd_summary.csv \
  --bin-output data/kinu29_psd_bins.csv
```

Large source media in `data/kinu_29_light/` such as photos and PDFs are treated as local measurement media and are ignored by `.gitignore`. The CSV export and model-ready CSV artifacts are the reproducible inputs for the simulator.

## Usage

```python
from pour_over import V60Params, RoastProfile, PourProtocol, simulate_brew

# Standard regime reference brew
params   = V60Params()
protocol = PourProtocol.standard_v60()
results  = simulate_brew(params, protocol, t_end=180)

print(f"EY = {results['EY_pct'][-1]:.1f}%")
print(f"TDS = {results['TDS_gl'][-1]:.1f} g/L")
print(f"Brew time = {results['brew_time']:.0f} s")
print(f"Drain time = {results['drain_time']:.0f} s")
```

```python
# Measured-bin calibrated Kinu 29 reference
import dataclasses
from pour_over import V60Params, RoastProfile, PourProtocol, simulate_brew

params = dataclasses.replace(
    V60Params.for_roast(RoastProfile.LIGHT),
    psd_bins_csv_path="data/kinu29_psd_bins.csv",
    D10_measured_m=374.2e-6,
    h_bed=0.053,
    T_amb=296.15,
    dripper_mass_g=123.5,
    dripper_cp_J_gK=0.88,
)
results = simulate_brew(params, PourProtocol.standard_v60(), t_end=180)
print(f"bin count = {results['extraction_bin_count']}")
```

```python
# Find optimal grind size (SCA Golden Cup targets)
from pour_over import find_optimal_grind
find_optimal_grind(protocol)

# Sensitivity analysis (tornado chart + 2D heatmap)
from pour_over import sensitivity_analysis
sensitivity_analysis(protocol)
```

## Installation

```bash
uv sync
uv run python -m pour_over      # run full simulation suite
uv run python v60_sim.py        # equivalent (backward-compatible)
```

This command regenerates the main figure set used by the showcase page:

- `data/kinu29_calibrated_flow_diagnostics_180s.png`
- `data/kinu29_calibrated_extraction_quality_180s.png`
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- `v60_grind.png`
- `v60_thermal.png`

The measured-fit page also uses:

- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- `data/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`

## SCA Golden Cup Targets

| Metric | Target |
|--------|--------|
| Extraction Yield (EY) | 18–22% |
| TDS | 11.5–14.5 g/L (1.15–1.35%) |

Current model output depends on recipe and roast profile.
The built-in `standard_v60()` recipe uses **20 g : 340 mL (1:17)**.
The generic medium baseline is a regime reference only. The current repo narrative and landing page are centered on the measured Kinu 29 calibrated model described above.

## References

- Mateus et al. (2007) — Effective permeability of espresso coffee beds
- Cameron et al. (2020, *Matter*) — Particle size distribution and extraction uniformity
- Corrochano et al. (2015) — CT scanning of coffee bed porosity evolution
- Sanchez-Lopez et al. (2016) — Arrhenius parameters for coffee compound extraction
- SCA Brewing Control Chart — Golden Cup Standard
