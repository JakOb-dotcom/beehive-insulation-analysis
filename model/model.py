"""
Why hive insulation has no general answer -- illustrative heat-balance model (v1.0)
===========================================================================

Heat demand is expressed in watts. Colony heat output per bee depends on
season and activity (0.5-2 mW, see PARAMS), so bee numbers are shown only as
a secondary scale: bees = watts / heat per bee.

Winter savings are not modelled: depending on cluster size (at 0.2 W/K per kg
of bees), the model gives a little under half to about 85 % of the winter loss
measured in surviving uncovered colonies in the trial re-analysed in
model/st_clair_reanalysis.py, i.e. it is uncertain by about a factor of two.

side_calculations() reproduces the further figures quoted in the text.

Every parameter is listed in PARAMS with unit, source and evidence category:
  A = measured / published value, used as reported
  B = derived by the author from published values (derivation in comments)
  C = assumption for illustration
Run:  python model/model.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parents[1]

PARAMS = {
    # hive wall, lumped conductance hive air -> outside, one brood box, measured
    # sealed and in still air (Mitchell 2016, Table 2)
    "L_wall_wood": (2.6, "W/K", "Mitchell 2016: cedar National 2.56-2.59 W/K", "A"),
    "L_wall_eps":  (1.0, "W/K", "Mitchell 2016: EPS 0.91-1.31 W/K (Langstroth EPS 1.30); "
                               "1.0 overstates the EPS advantage", "A"),
    # inner path brood -> hive air, per 10 000 brood cells, in series with wall.
    # Mitchell 2024 CFD brood area 6 combs x 214 x 100 mm; read as both faces =
    # 0.257 m2 ~ 10 000 cells at ~400 cells/dm2 (one-face reading halves values).
    #  dense cover: R_max ~1.4 K m2/W -> system 0.18 W/K -> minus wall -> 0.20 W/K
    #               (Southwick 1985 cluster: 0.12-0.26 W/K, independent check)
    #  no cover:    R_min ~0.4 K m2/W (nest without bees) -> 0.85 W/K
    # Scaled linearly with brood area (assumption C).
    "Li_dense_per10k": (0.20, "W/K", "Mitchell 2024 R_max; Southwick 1985", "B"),
    "Li_none_per10k":  (0.85, "W/K", "Mitchell 2024 R_min (no bees)", "B"),
    "T_brood": (35.0, "degC", "Stabentheiner et al. 2010: 33-36 degC", "A"),
    # heat output per bee (secondary scale only), season dependent:
    #  Southwick 1985: broodless cluster 2 degC -> 0.51 mW
    #  Southwick 1982 (via Mitchell 2016): 5 W/kg clustered 10 degC, 20 W/kg
    #    unclustered 20 degC -> ~0.5-2 mW at ~10 000 bees/kg
    #  Seeley 1995 summer budget: ~1 mW incl. flight
    "p_winter": ((0.5e-3, 1.0e-3), "W/bee", "Southwick 1985; Southwick 1982", "A/B"),
    "p_season": ((1.0e-3, 2.0e-3), "W/bee", "Southwick 1982; Seeley 1995", "A/B"),
    # nectar drying (Mitchell 2019 example: 5.3 mg/s honey from 30 % nectar)
    "P_dry":   (21.4, "W", "Mitchell 2019", "A/B"),
    "m_water": (8.83e-6, "kg/s", "763 g water/day at that rate", "B"),
    # minimum ventilation to carry that water out (openings only add to it)
    "T_exhaust":  (30.0, "degC", "assumed exhaust state", "C"),
    "RH_exhaust": (0.70, "-", "central case", "C"),
    "exhaust_range": (((28.0, 30.0, 33.0), (0.6, 0.7, 0.8)), "degC, -", "sensitivity range for exhaust state", "C"),
    "rho_cp": (1.2 * 1005, "J/m3K", "air", "A"),
    "h_out": (15.0, "W/m2K", "light wind; lower in calm air", "C"),
    "alpha": ({"dark": 0.85, "light glaze": 0.45, "white": 0.25}, "-", "typical", "C"),
}
P = {k: v[0] for k, v in PARAMS.items()}
I_PEAK = {"Whitehorse": 750.0, "Bad Gleichenberg": 850.0, "Sevilla": 950.0}  # C
SITE_LABEL = {"Whitehorse": "Whitehorse (cold)", "Bad Gleichenberg": "SE Styria (temperate)",
              "Sevilla": "Sevilla (hot)"}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
DAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
FLOW_MONTH = {"Whitehorse": 7, "Bad Gleichenberg": 7, "Sevilla": 4}  # C, peak-flow example


def series(*L):
    return 1.0 / sum(1.0 / x for x in L)


def L_inner(cells, cover):
    per = P["Li_dense_per10k"] if cover == "dense" else P["Li_none_per10k"]
    return per * cells / 1e4


def demand(t_out, L_wall, cells, cover):
    """heat needed to hold brood of `cells` cells at 35 degC (W)"""
    return series(L_wall, L_inner(cells, cover)) * np.maximum(P["T_brood"] - t_out, 0)


def p_sat(t):
    return 611.2 * np.exp(17.62 * t / (243.12 + t))


def x_abs(t, rh):
    return rh * p_sat(t) / (461.5 * (t + 273.15))


def x_outdoor(r):
    if pd.notna(r.dewpoint_c):
        return p_sat(r.dewpoint_c) / (461.5 * (r.tmean_c + 273.15))
    return x_abs(r.tmean_c, r.rh_pct / 100)


def q_vent(t_night, x_out, T_ex=None, RH_ex=None):
    T_ex = P["T_exhaust"] if T_ex is None else T_ex
    RH_ex = P["RH_exhaust"] if RH_ex is None else RH_ex
    vdot = P["m_water"] / (x_abs(T_ex, RH_ex) - x_out)
    return P["rho_cp"] * vdot * max(T_ex - t_night, 0), vdot


def q_vent_range(t_night, x_out):
    Ts, RHs = P["exhaust_range"]
    vals = [q_vent(t_night, x_out, T, RH) for T in Ts for RH in RHs]
    return min(v[0] for v in vals), max(v[0] for v in vals), min(v[1] for v in vals), max(v[1] for v in vals)



def n_per_group(effect, cv=0.25, z_a=1.959964, z_b=0.841621):
    return int(np.ceil(2 * (z_a + z_b) ** 2 * (cv / effect) ** 2))


def side_calculations(clim):
    """Figures quoted in the text that are not shown in the figures or tables."""
    Lw, Le = P["L_wall_wood"], P["L_wall_eps"]
    out = []
    # 3.2 EPS value 1.31 instead of 1.0, March night SE Styria, 20 000 cells, no cover
    t = clim[(clim.site == "Bad Gleichenberg") & (clim.month == 3)].tmin_c.item()
    d10 = demand(t, Lw, 20_000, "none") - demand(t, Le, 20_000, "none")
    d131 = demand(t, Lw, 20_000, "none") - demand(t, 1.31, 20_000, "none")
    out.append(f"3.2  wall-decided heat, March, 20k cells, no cover: EPS 1.0 -> {d10:.1f} W, EPS 1.31 -> {d131:.1f} W "
               f"({100*(d131/d10-1):.0f} %)")
    # 3.2 thermal resistance of 25 mm spruce vs 19 mm cedar (lambda 0.13 and 0.10 W/mK)
    out.append(f"3.2  R 25 mm spruce = {0.025/0.13:.2f} m2K/W, R 19 mm cedar = {0.019/0.10:.2f} m2K/W")
    # 3.6 wall share on flow nights with densely covered brood
    shares = []
    for site, mo in FLOW_MONTH.items():
        r = clim[(clim.site == site) & (clim.month == mo)].iloc[0]
        qv, _ = q_vent(r.tmin_c, x_outdoor(r))
        for c in (10_000, 20_000, 40_000):
            w, e = demand(r.tmin_c, Lw, c, "dense"), demand(r.tmin_c, Le, c, "dense")
            shares.append(100 * (w - e) / (w + P["P_dry"] + qv))
    out.append(f"3.6  wall share of flow-night demand, dense cover, 10k-40k cells, three sites: "
               f"{min(shares):.1f}-{max(shares):.1f} %")
    # 3.7 shade: extra heat shed by wood vs EPS at 25-28 degC, 20k-40k cells, no cover
    vals = [demand(T, Lw, c, "none") - demand(T, Le, c, "none") for T in (25, 28) for c in (20_000, 40_000)]
    out.append(f"3.7  shade, 25-28 degC, 20k-40k cells: wood sheds {min(vals):.1f}-{max(vals):.1f} W more than EPS")
    # 3.7 solar uptake through a dark wooden roof (assumptions stated in the text)
    out.append(f"3.7  dark wooden roof in full sun: 0.22 m2 x 2.8 W/m2K x 40 K = {0.22*2.8*40:.0f} W")
    # 5   entrance advection with Mitchell's corrected values (10 cm2, 0.94 m/s, 1.2 kJ m-3 K-1)
    adv = 1200 * 0.94 * 10e-4
    out.append(f"5    entrance advection: full entrance area {adv:.2f} W/K, half area {adv/2:.2f} W/K")
    # 5   one-face reading of Mitchell (2024) brood area
    A1 = 6 * 0.214 * 0.100
    inner = lambda R: 1 / (1 / (A1 / R) - 1 / Lw)
    out.append(f"5    one-face brood area {A1:.3f} m2: inner conductance dense {inner(1.4):.2f} W/K, "
               f"no bees {inner(0.4):.2f} W/K")
    # 9   sample size from Erdogan (2019) standard errors, n = 10 per group
    cvs = [sem * np.sqrt(10) / mean for mean, sem in ((17.08, 0.61), (20.17, 0.92), (23.04, 1.17))]
    ns = [n_per_group(0.10, cv=c) for c in (min(cvs), max(cvs))]
    out.append(f"9    CV of honey yield (Erdogan 2019) {100*min(cvs):.0f}-{100*max(cvs):.0f} %; colonies per group for a "
               f"10 % difference (two-sided alpha 0.05, power 0.8): {ns[0]}-{ns[1]}")
    return out


def main():
    clim = pd.read_csv(ROOT / "data" / "climate_monthly.csv")
    Lw, Le = P["L_wall_wood"], P["L_wall_eps"]
    sizes = (10_000, 20_000, 40_000)

    # --- table: demand per site/month/brood size/cover ----------------------
    rows = []
    for _, r in clim.iterrows():
        for c in sizes:
            for cov in ("dense", "none"):
                rows.append({"site": r.site, "month": int(r.month), "tmin": r.tmin_c,
                             "cells": c, "cover": cov,
                             "demand_wood_W": demand(r.tmin_c, Lw, c, cov),
                             "demand_eps_W": demand(r.tmin_c, Le, c, cov)})
    tab = pd.DataFrame(rows)
    tab.round(1).to_csv(ROOT / "data" / "results_brood_demand.csv", index=False)

    # --- flow-night budget ----------------------------------------------------
    flow = []
    for site, m in FLOW_MONTH.items():
        r = clim[(clim.site == site) & (clim.month == m)].iloc[0]
        qv, vdot = q_vent(r.tmin_c, x_outdoor(r))
        qlo, qhi, vlo, vhi = q_vent_range(r.tmin_c, x_outdoor(r))
        for c in (20_000, 40_000):
            dw = demand(r.tmin_c, Lw, c, "none"); de = demand(r.tmin_c, Le, c, "none")
            tw = dw + P["P_dry"] + qv; te = de + P["P_dry"] + qv
            flow.append({"site": site, "month": MONTHS[m - 1], "tmin": r.tmin_c, "cells": c,
                         "cond_wood": dw, "cond_eps": de, "evap": P["P_dry"], "vent": qv,
                         "vent_Ls": vdot * 1e3, "vent_min_W": qlo, "vent_max_W": qhi,
                         "vent_min_Ls": vlo * 1e3, "vent_max_Ls": vhi * 1e3,
                         "total_wood": tw, "total_eps": te,
                         "wall_share_of_total_%": 100 * (tw - te) / tw})
    flow = pd.DataFrame(flow)
    flow.round(2).to_csv(ROOT / "data" / "results_flow_night.csv", index=False)


    # --- console ----------------------------------------------------------------
    pd.set_option("display.width", 200)
    print("Example: SE Styria, March night (Tmin %.1f degC), demand W wood / EPS:" %
          clim[(clim.site == "Bad Gleichenberg") & (clim.month == 3)].tmin_c.item())
    for c in sizes:
        s = tab[(tab.site == "Bad Gleichenberg") & (tab.month == 3) & (tab.cells == c)]
        for _, x in s.iterrows():
            print(f"  {c/1e3:3.0f}k cells, {x.cover:5s} cover: {x.demand_wood_W:5.1f} / {x.demand_eps_W:5.1f} "
                  f"(diff {x.demand_wood_W - x.demand_eps_W:4.1f} W)")
    print("\nFlow-night budget (no-cover bound = largest wall share):")
    print(flow.round(1).to_string(index=False))
    print("\nWall share of resistance: tight cluster wood %.0f %%, EPS %.0f %%" %
          (100 * (1 / Lw) / (1 / Lw + 1 / P["Li_dense_per10k"]), 100 * (1 / Le) / (1 / Le + 1 / P["Li_dense_per10k"])))

    side = side_calculations(clim)
    print("\nSide calculations quoted in the text:")
    print("\n".join(side))
    (ROOT / "data" / "results_side_calculations.txt").write_text("\n".join(side) + "\n")

    # --- Fig 1: heat demand vs night temperature --------------------------------
    T = np.linspace(-6, 24, 200)
    cols = {10_000: "#F2A541", 20_000: "#D1495B", 40_000: "#5B2A86"}
    fig = plt.figure(figsize=(14.5, 7.6))
    gs = GridSpec(2, 2, height_ratios=[4.2, 1.0], hspace=0.08, wspace=0.18, figure=fig)
    for j, (cov, title) in enumerate((("none", "Bees not covering the brood\n(largest wall share, best case for insulation)"),
                                      ("dense", "Brood densely covered by bees\n(laboratory basis, may understate real losses)"))):
        ax = fig.add_subplot(gs[0, j])
        for c in sizes:
            w, e = demand(T, Lw, c, cov), demand(T, Le, c, cov)
            ax.fill_between(T, e, w, color=cols[c], alpha=.18)
            ax.plot(T, w, "-", color=cols[c], lw=2.2, label=f"{c//1000}k brood cells, wooden hive")
            ax.plot(T, e, "--", color=cols[c], lw=2.2, label=f"{c//1000}k brood cells, EPS hive")
        ax.set_xlim(-6, 24); ax.set_ylim(0, 70); ax.grid(alpha=.25)
        ax.set_title(title, fontsize=10.5); ax.set_xticklabels([])
        if j == 0:
            ax.set_ylabel("heat needed to hold brood at 35 °C (W)")
            ax.legend(fontsize=7.8, loc="upper right", ncol=1)
        sec = ax.secondary_yaxis("right", functions=(lambda w: w, lambda w: w))
        sec.set_ylabel("≈ thousand bees at 1 mW per bee (double at 0.5 mW)", fontsize=8.5)
        # rug of monthly night minima
        axr = fig.add_subplot(gs[1, j])
        for k, (site, g) in enumerate(clim.groupby("site", sort=False)):
            axr.scatter(g.tmin_c, [k] * 12, s=18, color="0.3")
            for _, r in g.iterrows():
                if r.month in (1, 3, 5, 7) and r.tmin_c > -6:
                    axr.annotate(MONTHS[int(r.month) - 1], (r.tmin_c, k), xytext=(0, 5),
                                 textcoords="offset points", ha="center", fontsize=6.5)
        axr.set_yticks(range(3)); axr.set_yticklabels([SITE_LABEL[s] for s in clim.site.unique()], fontsize=7.5)
        axr.set_xlim(-6, 24); axr.set_ylim(-0.6, 2.8); axr.grid(alpha=.2, axis="x")
        axr.set_xlabel("night minimum temperature (°C)")
    fig.suptitle("How much heat does a brood nest need at night, and how much of it does the hive wall decide?",
                 fontsize=12, y=0.98)
    fig.text(.5, -0.02, "Model, not measurement. Shaded area between solid and dashed line = difference wood vs EPS. Dots: monthly mean night minima 1991-2020 (Whitehorse Nov-Mar lie below −6 °C). "
             "Bees = watts / heat per bee: ~0.5-1 mW in winter and early spring, ~1-2 mW in the active season "
             "(Southwick 1982, 1985; Seeley 1995). Wall values for one brood box, sealed (Mitchell 2016).",
             ha="center", fontsize=7.8, wrap=True)
    fig.savefig(ROOT / "figures" / "fig1_brood_heat_demand.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # --- Fig 2: flow-night budget ------------------------------------------------
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    f40 = flow[flow.cells == 40_000].reset_index(drop=True)
    xs = np.arange(len(f40)); bw = 0.36
    for i, (mat, col, hatch) in enumerate((("wood", "#8B4513", ""), ("eps", "#1565C0", "//"))):
        x = xs + (i - 0.5) * bw
        c1 = f40[f"cond_{mat}"]; ax.bar(x, c1, bw, color=col, alpha=.85, hatch=hatch,
                                        label=f"conduction, {'wooden' if mat=='wood' else 'EPS'} hive")
        ax.bar(x, f40.evap, bw, bottom=c1, color="#7FB3D5", label="evaporation (nectar drying)" if i == 0 else None)
        ax.bar(x, f40.vent, bw, bottom=c1 + f40.evap, color="#B0BEC5",
               label="warm air leaving with the drying air (central case)" if i == 0 else None)
        ax.errorbar(x, f40[f"total_{mat}"], yerr=[f40.vent - f40.vent_min_W, f40.vent_max_W - f40.vent],
                    fmt="none", ecolor="k", capsize=4, lw=1,
                    label="range for exhaust 28-33 °C, 60-80 % RH" if i == 0 else None)
        for xi, tot, hi in zip(x, f40[f"total_{mat}"], f40.vent_max_W - f40.vent):
            ax.text(xi, tot + hi + 1.5, f"{tot:.0f} W", ha="center", fontsize=8)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{SITE_LABEL[s]}\n{m} night {t:.0f} °C" for s, m, t in zip(f40.site, f40.month, f40.tmin)],
                       fontsize=8.5)
    ax.set_ylabel("heat demand on a flow night (W)")
    ax.set_title("Flow night, 40 000 brood cells, bees not covering the brood (largest possible wall share)\n"
                 "most of the demand is paid regardless of hive material", fontsize=10.5)
    ax.legend(fontsize=7.5, loc="upper right"); ax.grid(alpha=.25, axis="y"); ax.set_ylim(0, 140)
    fig.text(.5, -0.04, "Drying at Mitchell's (2019) example rate, 458 g honey/day; strong flows can be several times higher. Ventilation = air needed to carry that "
             "water out, central case exhaust 30 °C / 70 % RH; real openings can only add to it.", ha="center", fontsize=7.8)
    fig.savefig(ROOT / "figures" / "fig2_flow_night_budget.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # --- Fig 3: sol-air ----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 5))
    sites = list(SITE_LABEL); jul = clim[clim.month == 7].set_index("site").loc[sites]
    bwd = 0.25
    for i, ((lab, a), col) in enumerate(zip(P["alpha"].items(), ("#4E342E", "#D7A86E", "#CFD8DC"))):
        t = jul.tmax_c.values + a * np.array([I_PEAK[s] for s in sites]) / P["h_out"]
        bars = ax.bar(np.arange(3) + (i - 1) * bwd, t, bwd, color=col, edgecolor="k", lw=.5, label=f"{lab} (α={a})")
        for bb, v in zip(bars, t):
            ax.text(bb.get_x() + bb.get_width() / 2, v + .8, f"{v:.0f}", ha="center", fontsize=8)
    ax.hlines(jul.tmax_c.values, np.arange(3) - 1.5 * bwd, np.arange(3) + 1.5 * bwd, colors="k", lw=2,
              label="air, mean daily max")
    ax.set_xticks(range(3)); ax.set_xticklabels([SITE_LABEL[s] for s in sites], fontsize=9)
    ax.set_ylabel("sunlit surface temperature at noon (°C)")
    ax.set_title("July noon, sunlit hive surface (sol-air temperature)\nhive colour sets the solar heat load", fontsize=10.5)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(0, 0.93)); ax.grid(alpha=.25, axis="y"); ax.set_ylim(0, 105)
    fig.text(.5, -0.03, "Surface, not interior temperature, horizontal roof. h = 15 W/m²K (light wind); in calm air h is lower and surfaces hotter. "
             "Clear-sky peak irradiance assumed 750/850/950 W/m². A roof with an air gap receives far less.",
             ha="center", fontsize=7.5)
    fig.savefig(ROOT / "figures" / "fig3_solair_july.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("\nfigures written")


if __name__ == "__main__":
    main()
