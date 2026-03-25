# V60 Pour-Over Physics Simulation

A physics-based numerical simulation of V60 pour-over coffee brewing, modelling fluid dynamics, multi-component extraction kinetics, and thermodynamics as a coupled ODE system.

## Physics Model

The brew state is represented as an 8-dimensional ODE:

```
state = [h, V_out, V_poured, C_fast, M_fast, C_slow, M_slow, T]
```

| Variable | Description |
|----------|-------------|
| `h` | Water level in the cone [m] |
| `V_out` | Cumulative output volume [m³] |
| `V_poured` | Cumulative poured volume [m³] |
| `C_fast/slow` | Bed pore concentration, fast/slow components [g/L] |
| `M_fast/slow` | Remaining solid-phase solute [g] |
| `T` | Water temperature [K] |

### Key Physical Corrections

| # | Correction | Description |
|---|-----------|-------------|
| [1] | Bed height transition | C∞ smooth crossover replacing hard switching |
| [2] | Bypass dissipation | Q_bp ∝ h² (h < h_bed), eliminates h→0 bypass paradox |
| [3] | Fine migration clogging | k_eff(V_out) = k₀ / (1 + β·V_out) |
| [4][13] | Bloom absorption | CO₂-corrected absorption ratio (0.5/1.3 mL/g vs old 1.0/2.0) |
| [5] | Solid depletion | C_sat_eff(t) = κ(T)·M(t), prevents late-stage concentration spike |
| [6] | Thermodynamics | μ(T)·k_ext(T)·Newton cooling·initial thermal shock |
| [7] | Multi-component extraction | Fast (acids/sweetness, Ea=15 kJ/mol) + Slow (bitterness, Ea=45 kJ/mol) |
| [8] | Particle swelling | φ(sat) = φ₀ − Δφ·sat; Kozeny-Carman: k ∝ φ³/(1−φ)² |
| [9] | Capillary pressure cutoff | h < h_cap → Q→0 sigmoid (drip-filter mode) |
| [10] | Smooth saturation transition | Cubic Hermite smooth-step, C¹ continuous |
| [11] | Accessibility power law | C_eff = C_sat(T)·(M/M₀)^β, β=1.5 (shrinking-core model) |
| [12] | Brew time calibration | k: 2e-11→6e-11 m², h_cap: 5→3 mm |
| [14] | CO₂ back-pressure | h_gas(t) = h_gas_0·exp(−t/τ), explains "fresh bean gas-trapping" |

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
| `max_EY` | 22% | 28% | 30% |
| `Ea_slow` | 50 kJ/mol | 45 kJ/mol | 38 kJ/mol |
| `fast_fraction` | 0.45 | 0.35 | 0.25 |
| `absorb_full_ratio` | 1.2 mL/g | 1.3 mL/g | 1.7 mL/g |
| `co2_pressure_m` | 9 mm | 7 mm | 4 mm |

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

## SCA Golden Cup Targets

| Metric | Target |
|--------|--------|
| Extraction Yield (EY) | 18–22% |
| TDS | 11.5–14.5 g/L (1.15–1.35%) |

Current model output (medium roast, medium grind, 93°C): **EY ≈ 18.8%, TDS ≈ 13.4 g/L** ✓

## References

- Mateus et al. (2007) — Effective permeability of espresso coffee beds
- Cameron et al. (2020, *Matter*) — Particle size distribution and extraction uniformity
- Corrochano et al. (2015) — CT scanning of coffee bed porosity evolution
- Sanchez-Lopez et al. (2016) — Arrhenius parameters for coffee compound extraction
- SCA Brewing Control Chart — Golden Cup Standard
