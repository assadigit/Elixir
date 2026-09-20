# Source Chapter: Grid-Scale Battery Storage Economics (academic, fictionalized)

## Study Design and Data Sources

We assembled a dataset of 142 grid-scale battery installations
commissioned between 2015 and 2023 across four regional markets [1].
Installation records were cross-validated against interconnection queue
filings and operator disclosure reports (Smith et al., 2021). Each
installation was characterized by rated power, energy capacity, cell
chemistry, and annual degradation measurements collected over a minimum
of three operating years [2]. The final panel covers 31,400
megawatt-hours of cumulative installed capacity, representing 87% of
global deployments in the study window.

Table 1: Annual capacity retention by cell chemistry.

| Chemistry | Year 1 | Year 3 | Year 5 | Year 8 |
|-----------|--------|--------|--------|--------|
| LFP       | 98.1%  | 95.4%  | 92.0%  | 87.2%  |
| NMC       | 97.3%  | 93.1%  | 88.4%  | 81.5%  |
| LTO       | 99.2%  | 98.0%  | 96.7%  | 94.6%  |

Lithium iron phosphate cells retained 87.2% of nameplate capacity after
eight years, outperforming nickel manganese cobalt cells by 5.7
percentage points over the same horizon [3]. Lithium titanate cells
degraded slowest but carried a 2.4 times capital cost premium,
consistent with earlier laboratory estimates (Chen and Okafor, 2022).

## Levelized Cost Modeling

We computed levelized costs of storage using a discounted cash flow
model with a 7% real discount rate and 20-year project life [4]. The
model internalizes augmentation purchases that restore capacity as
cells degrade, which earlier studies treated as an exogenous
sensitivity [5].

Table 2: Levelized cost of storage by market, 2023 USD per megawatt-hour.

| Market | Mean | Median | 10th pct | 90th pct |
|--------|------|--------|----------|----------|
| MISO   | 132  | 128    | 96       | 171      |
| ERCOT  | 118  | 114    | 89       | 152      |
| GB     | 141  | 137    | 104      | 183      |
| NEM    | 127  | 123    | 95       | 164      |

Levelized costs fell 38% between 2018 and 2023, driven principally by
cell price declines rather than balance-of-plant savings [6]. The
interquartile spread narrowed by 21% over the same period, indicating
maturing supply chains and standardization of enclosure designs.

## Revenue Stacking and Sensitivity Analysis

Installations earning revenues from three or more stacked streams
achieved payback in 6.2 years on average, compared with 9.8 years for
single-stream merchant assets [7]. Frequency regulation alone never
recouped capital costs in any market we studied. Energy arbitrage
contributed the largest revenue share in markets with high renewable
penetration, reaching 54% of total revenue in the NEM cohort [8].

A one-at-a-time sensitivity analysis shows the payback period is most
elastic to cycle frequency: increasing daily cycles from one to two
shortened payback by 1.9 years, whereas a 20% capital cost reduction
shortened it by only 1.1 years [9]. Degradation assumptions ranked
third in elasticity, confirming that augmentation scheduling deserves
the modeling attention it has recently received (Ibrahim et al., 2023).

## Limitations

Our panel over-represents large utility-scale assets and excludes
behind-the-meter systems, so the reported levelized costs should be
read as an upper bound for distributed storage. Revenue data for the
final study year remain provisional in two of the four markets, and
contracted hedges were not observable, which may understate revenue
stability [10].
