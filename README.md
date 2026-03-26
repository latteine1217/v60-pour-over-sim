# V60 Pour-Over Physics Simulation

A physics-based numerical simulation of V60 pour-over coffee brewing, modelling fluid dynamics, multi-component extraction kinetics, and thermodynamics as a coupled ODE system.

## Project Scope

This repository has two complementary entry points:

- `README.md`: installation, package structure, reproducibility, and model boundary
- `index.html`: visual showcase of the current generated outputs and the main physics stories

The current model is a reduced-order bed-scale simulator. It is designed to compare flow, bypass, thermal regime, and extraction behavior across plausible pour-over conditions. It is not a fully particle-resolved diffusion-advection PDE solver, and its outputs should be read as engineering-model predictions rather than universal ground truth.

Primary use cases:

- compare grind regimes under one consistent flow/extraction model
- inspect how temperature changes both hydraulic throughput and extraction chemistry
- diagnose whether a cup is limited by flow, accessibility, bypass, or retained liquid
- regenerate a consistent family of figures from the CLI

## Physics Model

The brew state is represented as a 9-dimensional ODE:

```
state = [h, V_out, V_poured, sat, C_fast, M_fast, C_slow, M_slow, T]
```

| Variable | Description |
|----------|-------------|
| `h` | Water level in the cone [m] |
| `V_out` | Cumulative output volume [m³] |
| `V_poured` | Cumulative poured volume [m³] |
| `sat` | Dynamic wetting / absorption saturation of the bed [-] |
| `C_fast/slow` | Bed pore concentration, fast/slow components [g/L] |
| `M_fast/slow` | Remaining solid-phase solute [g] |
| `T` | Water temperature [K] |

### Key Physical Corrections

| # | Correction | Description |
|---|-----------|-------------|
| [1] | Bed height transition | C∞ smooth crossover replacing hard switching |
| [2] | Bypass activation | Bypass stays near zero at low free-water head and opens gradually as wall-channel flow develops |
| [3] | Fine migration clogging | k_eff(V_out) = k₀ / (1 + β·V_out) |
| [4][13] | Bloom absorption | CO₂-corrected absorption ratio (0.5/1.64 mL/g for medium roast baseline) |
| [5] | Solid depletion | C_sat_eff(t) = κ(T)·M(t), prevents late-stage concentration spike |
| [6] | Thermodynamics | μ(T)·k_ext(T)·Newton cooling·initial thermal shock |
| [7] | Multi-component extraction | Fast (acids/sweetness, Ea=15 kJ/mol) + Slow (bitterness, Ea=45 kJ/mol) |
| [8] | Particle swelling | φ(sat) = φ₀ − Δφ·sat; Kozeny-Carman: k ∝ φ³/(1−φ)² |
| [9] | Capillary pressure cutoff | h < h_cap → Q→0 sigmoid (drip-filter mode) |
| [10] | Smooth saturation transition | Cubic Hermite smooth-step, C¹ continuous |
| [11] | Accessibility power law | C_eff = C_sat(T)·(M/M₀)^β, β=1.5 (shrinking-core model) |
| [12] | Brew time calibration | k: 2e-11→6e-11 m², h_cap: 5→3 mm |
| [14] | CO₂ back-pressure | h_gas(t) = h_gas_0·exp(−t/τ), kept small for the medium baseline and larger for fresher/light roasts |
| [15] | Flow-dependent transfer | Sherwood-like flow factor bridges diffusion-only and advective transfer |
| [16] | Dynamic wetting | capillary wetting state `sat(t)` with temperature-dependent Lucas-Washburn timescale |
| [17] | Particle geometry | fractal PSD, D10-based diagnostics, 200 μm shell accessibility, Einstein-Smoluchowski diffusion |

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
├── params.py       # RoastProfile, V60Params, PourProtocol
├── core.py         # simulate_brew ODE engine
├── viz.py          # Visualization functions
├── fitting.py      # Parameter fitting (scipy.optimize)
└── analysis.py     # Sensitivity analysis, grind optimization

v60_sim.py          # Backward-compatible thin wrapper
```

## Usage

```python
from pour_over import V60Params, RoastProfile, PourProtocol, simulate_brew

# Standard medium-grind brew
params   = V60Params()
protocol = PourProtocol.standard_v60()
results  = simulate_brew(params, protocol, t_end=300)

print(f"EY = {results['EY_pct'][-1]:.1f}%")
print(f"TDS = {results['TDS_gl'][-1]:.1f} g/L")
print(f"Brew time = {results['brew_time']:.0f} s")
print(f"Drain time = {results['drain_time']:.0f} s")
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

- `v60_simulation.png`
- `v60_tds.png`
- `v60_grind.png`
- `v60_thermal.png`

## SCA Golden Cup Targets

| Metric | Target |
|--------|--------|
| Extraction Yield (EY) | 18–22% |
| TDS | 11.5–14.5 g/L (1.15–1.35%) |

Current model output depends on recipe and roast profile.
The built-in `standard_v60()` recipe uses **20 g : 340 mL (1:17)**.
The default medium baseline is calibrated as a practical engineering reference, not as a universal fresh-bean profile.

## References

- Mateus et al. (2007) — Effective permeability of espresso coffee beds
- Cameron et al. (2020, *Matter*) — Particle size distribution and extraction uniformity
- Corrochano et al. (2015) — CT scanning of coffee bed porosity evolution
- Sanchez-Lopez et al. (2016) — Arrhenius parameters for coffee compound extraction
- SCA Brewing Control Chart — Golden Cup Standard
