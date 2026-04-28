# V60 Pour-Over Physics Simulation

A physics-based numerical simulation of V60 pour-over coffee brewing, modelling fluid dynamics, bin-resolved extraction kinetics, and thermodynamics as one coupled ODE system.

## Project Scope

This repository now has a layered package structure with two complementary entry points:

- `README.md`: installation, package structure, reproducibility, and model boundary
- `index.html`: visual showcase of the current generated outputs and the main physics stories

The current model is a reduced-order bed-scale simulator. It is designed to compare flow, bypass, thermal regime, and extraction behavior across plausible pour-over conditions, while also checking the model against measured `V_in(t)`, `V_out(t)`, grinder PSD, and final cup temperature. The codebase is now explicitly split into fixed physical inputs, physically interpretable reduced-order closures, measured-data I/O, observation-layer transforms, and analysis/showcase entry points. It is not a fully particle-resolved diffusion-advection PDE solver, and its outputs should be read as engineering-model predictions rather than universal ground truth. Measured-case fitting is treated as a validation tool for physically defensible closures, not as a license to keep arbitrary parameters solely because they reduce loss.

Primary use cases:

- calibrate one real brew against measured `V_in(t)` / `V_out(t)` / PSD / cup temperature
- compare grind regimes under one consistent flow/extraction model
- inspect how temperature changes both hydraulic throughput and extraction chemistry
- diagnose whether a cup is limited by flow, accessibility, bypass, or retained liquid
- regenerate a consistent family of figures from the CLI

## Physics Model

The current main model uses one dynamic state family:

```
state = [h, V_out, V_poured, sat, {C_fast,i, M_fast,i, C_slow,i, M_slow,i}, T, T_dripper, chi_struct]
```

| Variable | Description |
|----------|-------------|
| `h` | Water level in the cone [m] |
| `V_out` | Cumulative output volume [m³] |
| `V_poured` | Cumulative poured volume [m³] |
| `sat` | Dynamic wetting / absorption saturation of the bed [-] |
| `{C_fast,i, C_slow,i}` | Bin-resolved bed pore concentration [g/L] |
| `{M_fast,i, M_slow,i}` | Bin-resolved remaining solid-phase solute [g] |
| `T` | Liquid temperature [K] |
| `T_dripper` | Dripper thermal node [K] |
| `chi_struct` | Post-bloom wet-bed structure state [-] |

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

The current calibrated reference in the repo is based on the April 12 measured brew:

- grinder: `Kinu 29`
- roast: `light`
- dose: `20 g`
- bed height: `5.3 cm`
- ambient: `23°C`
- dripper: ceramic V60, `123.5 g`
- server equivalent heat capacity: `42.4 mL water equivalent`
- measured PSD: raw Kinu 29 export is stored under `data/kinu_29_light/4:12/`; model-ready artifacts are `data/kinu_29_light/4:12/kinu29_psd_summary.csv` and `data/kinu_29_light/4:12/kinu29_psd_bins.csv`
- calibrated fit summary: `data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`

Current reference metrics:

- `D10 ≈ 529 μm`
- `axial_node_count = 2`
- `k_fit ≈ 1.24e-10 m²`
- `k_beta_fit ≈ 1.25e3 m⁻³`
- `tau_lag ≈ 0.5 s`
- `wetbed_struct_gain ≈ 0.176`
- `wetbed_struct_rate = 0.0607 (fixed)`
- `wetbed_impact_release_rate = 0.30 (fixed)`
- `kr(sat)` uses explicit unsaturated Darcy attenuation
- `pref_flow_coeff ≈ 2.64e-4 m²/s`
- `server cooling λ = 0` on the current measured fit
- `V_out RMSE ≈ 16.53 mL`
- `q_out RMSE ≈ 1.40 mL/s`
- `current benchmark gate = FAIL` under the existing thresholds

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
- `params.py` keeps reduced-order closures and model-control knobs that may be scanned or calibrated only within physically justified bounds.
- `core.py` remains the single coupled ODE engine.
- measured-data ingestion, observation-layer transforms, benchmark, identifiability, and showcase-state loading now live in dedicated modules instead of being folded into a few large files.

## Data Artifacts

The current Kinu 29 reference data has two layers:

- raw measurement export: `data/kinu_29_light/4:12/PSD_export_data.csv` and `data/kinu_29_light/4:12/PSD_export_data_stats.csv`
- model-ready artifacts: `data/kinu_29_light/4:12/kinu29_psd_summary.csv` and `data/kinu_29_light/4:12/kinu29_psd_bins.csv`

The raw CSV files are the source of truth for particle geometry. The `kinu29_psd_*` CSV files are generated artifacts used by the model and should be regenerated rather than edited by hand:

```bash
uv run python -m pour_over.psd \
  data/kinu_29_light/4:12/PSD_export_data.csv \
  --stats-csv data/kinu_29_light/4:12/PSD_export_data_stats.csv \
  --output data/kinu_29_light/4:12/kinu29_psd_summary.csv \
  --bin-output data/kinu_29_light/4:12/kinu29_psd_bins.csv
```

Large source media in `data/kinu_29_light/4:12/` such as photos and PDFs are treated as local measurement media and are ignored by `.gitignore`. The CSV export and model-ready CSV artifacts are the reproducible inputs for the simulator.

For measured-case temperature handling, `ambient_temp_C` should come from the brew record itself. If a thermal CSV omits that metadata, the loader now falls back to the `t=0` measured temperature (`server_temp_C` first, then `outflow_temp_C`) instead of silently assuming `23°C`.

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
    psd_bins_csv_path="data/kinu_29_light/4:12/kinu29_psd_bins.csv",
    D10_measured_m=529.3e-6,
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
- `data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- `v60_grind.png`
- `v60_thermal.png`

The measured-fit page also uses:

- `data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s.png`
- `data/kinu_29_light/4:12/kinu29_light_20g_flow_fit_psd_clog_impactrelief_wetbedchi_180s_summary.csv`
- `data/kinu_29_light/4:12/kinu29_light_20g_thermal_profile_comparison.png`

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
