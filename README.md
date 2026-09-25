# Why hive insulation has no general answer

A short synthesis of published thermal and field data on beehive insulation, with a small, fully documented illustrative model.

**Status:** technical note v1.0, not peer reviewed. No new field measurements. Model, not measurement.

- Paper: [`paper/technical_note.md`](paper/technical_note.md)
- Model and figures: [`model/model.py`](model/model.py)
- Climate data: [`data/climate_monthly.csv`](data/climate_monthly.csv) (station normals 1991-2020)

## Main points

1. The effect of the hive wall depends on quantities that change through the year and between colonies: bees relative to brood, how densely bees cover the brood, night temperature, sunlight, and the air exchange needed to dry nectar.
2. For 20 000 brood cells on an average March night in SE Styria, the wall decides between about 2 W and 14 W, depending on how densely the bees cover the brood.
3. On nectar-flow nights most of the heat demand is evaporation plus the warm air that carries the moisture out; neither depends on the wall. On warm days the direction can reverse (shade vs. sun).
4. Winter is where the only recent randomized trial points to a benefit: a re-analysis of its public data shows about 2–4 kg less mass loss over the winter with covers and fewer deaths, without statistical certainty and in an unusually cold winter. Winter savings are not modelled.
5. For build-up and yield, effects are mainly reported in weak or young colonies; no study free of major confounding shows higher yields of established colonies. Limits of every source are listed in Section 5.

## Reproduce

```bash
pip install -r requirements.txt
python model/model.py              # heat-balance figures and tables
python model/st_clair_reanalysis.py # re-analysis of the St. Clair et al. (2022) raw data
```

All parameters are listed in `PARAMS` in `model/model.py` with unit, source and evidence category (A measured, B derived, C assumption).

## Citation

See `CITATION.cff`. A DOI is issued through Zenodo on each GitHub release.

## License

Text, figures and own data: CC BY 4.0. Code: MIT. The St. Clair et al. (2022) raw data in `data/` are CC0 (https://doi.org/10.5061/dryad.80gb5mkss). See `LICENSE`.
