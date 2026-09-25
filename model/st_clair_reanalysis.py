"""
Re-analysis of the public raw data of St. Clair, Beach & Dolezal (2022),
"Honey bee hive covers reduce food consumption and colony mortality during
overwintering", PLOS ONE 17(4): e0266219.

Data: St. Clair A, Beach N, Dolezal A (2022) [Dataset], Dryad,
https://doi.org/10.5061/dryad.80gb5mkss (mirror: https://zenodo.org/records/6413033),
licensed CC0 1.0. A copy is included as data/st_clair_2022_overwintering_raw.xlsx.

The script uses simple, assumption-light comparisons (group means, exact and
rank tests). The authors used mixed and survival models with an apiary effect;
the differences in p-values below reflect that choice of method.

Run:  python model/st_clair_reanalysis.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "data" / "st_clair_2022_overwintering_raw.xlsx"


def main():
    d = pd.read_excel(F, sheet_name="Overwinterng Data")
    d["Date"] = pd.to_datetime(d["Date"])
    feed = "Proportion mid-winter feed consumed with dead colonies filetered"
    for c in ["Raw Mass (kg)", "Survival", "Rate of growth (Mx)", feed]:
        d[c] = pd.to_numeric(d[c], errors="coerce")        # '.' = missing

    mass = d.pivot_table(index=["Treatment", "Colony ID"], columns="Date", values="Raw Mass (kg)")
    surv = d.pivot_table(index=["Treatment", "Colony ID"], columns="Date", values="Survival")
    yard = d.groupby(["Treatment", "Colony ID"])["Yard"].first()
    n = surv.groupby("Treatment").size()
    dead = surv.iloc[:, -1].groupby("Treatment").sum().astype(int)
    out = []

    # 1 group sizes and mortality
    out.append(f"Colonies: covered (Wrapped) {n['Wrapped']}, uncovered (Unwrapped) {n['Unwrapped']}")
    out.append(f"Dead by 12 Apr 2021: covered {dead['Wrapped']}/{n['Wrapped']} "
               f"({100*dead['Wrapped']/n['Wrapped']:.1f} %), uncovered {dead['Unwrapped']}/{n['Unwrapped']} "
               f"({100*dead['Unwrapped']/n['Unwrapped']:.1f} %)")
    p = stats.fisher_exact([[dead["Unwrapped"], n["Unwrapped"] - dead["Unwrapped"]],
                            [dead["Wrapped"], n["Wrapped"] - dead["Wrapped"]]]).pvalue
    out.append(f"  Fisher exact test, two-sided: p = {p:.3f}")
    pb = stats.boschloo_exact([[dead["Unwrapped"], n["Unwrapped"] - dead["Unwrapped"]],
                               [dead["Wrapped"], n["Wrapped"] - dead["Wrapped"]]]).pvalue
    out.append(f"  Boschloo exact test, two-sided: p = {pb:.3f}")

    T = lambda y, m, d_: pd.Timestamp(y, m, d_)
    alive = surv[T(2021, 3, 30)] == 0

    def compare(a, b, label, alive_mask):
        dl = -(mass[b] - mass[a])[alive_mask].dropna()
        u, w = dl.xs("Unwrapped"), dl.xs("Wrapped")
        diff = u.mean() - w.mean(); se = np.sqrt(u.var() / len(u) + w.var() / len(w))
        out.append(f"Mass loss {label}: uncovered {u.mean():.1f} kg (n={len(u)}), covered {w.mean():.1f} kg (n={len(w)}); "
                   f"difference {diff:.1f} kg, approx. 95 % CI {diff-1.96*se:.1f} to {diff+1.96*se:.1f}; "
                   f"Mann-Whitney p = {stats.mannwhitneyu(u, w).pvalue:.2f}")
        return dl

    # 2 mass loss of surviving colonies in windows of constant hive configuration
    #    20 Jan is the last weighing before hives were opened for feeding on 2 Feb.
    compare(T(2020, 11, 9), T(2021, 1, 20), "9 Nov - 20 Jan (before feeding)", alive)
    compare(T(2021, 1, 20), T(2021, 2, 22), "20 Jan - 22 Feb (feeding, cold wave)", alive)
    compare(T(2021, 2, 22), T(2021, 3, 30), "22 Feb - 30 Mar", alive)
    tot = compare(T(2020, 11, 9), T(2021, 3, 30), "9 Nov - 30 Mar (whole winter)", alive)
    compare(T(2020, 11, 9), T(2021, 4, 12), "9 Nov - 12 Apr", surv[T(2021, 4, 12)] == 0)
    by_yard = tot.to_frame("loss").join(yard).groupby(["Yard", "Treatment"])["loss"].mean().unstack()
    out.append(f"  whole winter: covered colonies lost less in {(by_yard['Wrapped'] < by_yard['Unwrapped']).sum()} "
               f"of {len(by_yard)} apiaries")

    # 3 data quality indicators
    jump = (mass[T(2021, 2, 2)] - mass[T(2021, 1, 20)]).dropna()
    out.append(f"Colonies more than 2 kg heavier on 2 Feb than on 20 Jan (weighed after feeding): {(jump > 2).sum()} of {len(jump)}")
    cols = list(mass.columns); gains = n_int = 0
    for a, b in zip(cols[:-1], cols[1:]):
        if b > T(2021, 1, 20):          # winter intervals only, before feeding
            continue
        dd = (mass[b] - mass[a]).dropna(); gains += (dd > 2).sum(); n_int += len(dd)
    out.append(f"Winter weighing intervals (Nov - Jan) showing a gain > 2 kg: {gains} of {n_int}")
    v = pd.read_excel(F, sheet_name="Tipping scale Side Experiment").apply(pd.to_numeric, errors="coerce")
    v = v.dropna(subset=["Tilted total", "Classic scale weight"]); dv = v["Classic scale weight"] - v["Tilted total"]
    out.append(f"Authors' validation, reference scale minus tilt method: {dv.mean():.1f} +/- {dv.std():.1f} kg (n={len(dv)})")

    # slopes of mass over time, surviving colonies to 30 Mar, with and without a step for feeding
    rows = []
    for (tr, cid), r in mass[alive].iterrows():
        r = r.dropna(); r = r[r.index <= T(2021, 3, 30)]
        if len(r) < 5:
            continue
        x = (r.index - T(2020, 11, 9)).days.values / 14.0
        step = (r.index >= T(2021, 2, 2)).astype(float)
        b_step = np.linalg.lstsq(np.column_stack([np.ones_like(x), x, step]), r.values, rcond=None)[0][1]
        r2 = r[r.index != T(2021, 2, 2)]; x2 = (r2.index - T(2020, 11, 9)).days.values / 14.0
        st2 = (r2.index > T(2021, 2, 2)).astype(float)
        b_step2 = np.linalg.lstsq(np.column_stack([np.ones_like(x2), x2, st2]), r2.values, rcond=None)[0][1]
        rows.append((tr, np.polyfit(x, r.values, 1)[0], b_step, b_step2))
    R = pd.DataFrame(rows, columns=["tr", "no_step", "step", "step_excl_2feb"])
    for c, lab in (("no_step", "no feeding step"), ("step", "with feeding step"),
                   ("step_excl_2feb", "with feeding step, 2 Feb weighing excluded")):
        u, w = R[R.tr == "Unwrapped"][c], R[R.tr == "Wrapped"][c]
        out.append(f"Slope of mass, kg per 14 days, {lab}: uncovered {u.mean():.2f}, covered {w.mean():.2f}, "
                   f"Welch p = {stats.ttest_ind(u, w, equal_var=False).pvalue:.2f}")

    # 4 sugar cake consumed (proportion), surviving colonies
    fc = d.groupby(["Treatment", "Colony ID"])[feed].first().dropna()
    u, w = fc.xs("Unwrapped"), fc.xs("Wrapped")
    out.append(f"Proportion of mid-winter sugar cake consumed: uncovered {u.mean():.2f}, covered {w.mean():.2f}, "
               f"Mann-Whitney p = {stats.mannwhitneyu(u, w).pvalue:.2f}")

    # 5 the authors' slope metric, as given in the data file
    mx = d.groupby(["Treatment", "Colony ID"])["Rate of growth (Mx)"].first()
    u, w = mx.xs("Unwrapped"), mx.xs("Wrapped")
    out.append(f"Authors' mass-change slope (column 'Rate of growth'): uncovered {u.mean():.2f}, covered {w.mean():.2f}, "
               f"Welch p = {stats.ttest_ind(u, w, equal_var=False).pvalue:.3f}")

    # 6 steady-state model for the trial period, for three cluster sizes
    #    uncovered wooden hive: series(2.6 W/K, 0.2 W/K); core 30 degC; outside assumed
    #    -7 degC for the whole period, about as cold as the trial's coldest month
    #    (February 2021: about -5 to -7 degC at nearby stations, NWS). The measured
    #    figure is a net loss that excludes the feed added in February, so the
    #    comparison is conservative.
    days = (T(2021, 3, 30) - T(2020, 11, 9)).days
    unc = tot.xs("Unwrapped").mean()          # net loss of uncovered colonies, whole winter
    # cluster size converted to inner conductance at 0.2 W/K per kg of bees
    # (lower end of Southwick 1985, Fig. 4)
    for Li, lab in ((0.2, "about 1 kg"), (0.3, "about 1.5 kg"), (0.4, "about 2 kg")):
        L = 1 / (1 / 2.6 + 1 / Li)
        kg_sugar = L * (30 - (-7)) * days * 86400 / 16.2e6
        out.append(f"Model bound, uncovered wooden hive, cluster {lab} (inner {Li} W/K), 9 Nov - 30 Mar at -7 degC: "
                   f"{kg_sugar:.1f} kg sugar, about {kg_sugar/0.8:.1f} kg of stores at 80 % sugar "
                   f"= {100*kg_sugar/0.8/unc:.0f} % of the {unc:.1f} kg net loss of surviving uncovered colonies "
                   f"(n={len(tot.xs('Unwrapped'))}, excluding feed added)")

    text = "\n".join(out)
    print(text)
    (ROOT / "data" / "results_st_clair_reanalysis.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
