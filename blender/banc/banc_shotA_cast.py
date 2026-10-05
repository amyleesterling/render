"""Shot A cast: the T1 left local loop, chosen from connectivity.

sensory (T1L) -> interneuron -> motor (left T1)

ON THE THRESHOLD. The paper does not use a raw synapse count to decide what is a
real connection. Its analysis uses an "adjusted influence" measure, normalised
and propagated through the network, with a cutoff of 17.18 chosen as the elbow of
the distribution. A raw count of 5 does appear in the paper, but as a DRAWING
convention: in Fig. 4d thin arrows are connections of 5-20 synapses, intermediate
20-100, thick >100. So 5 is the smallest connection the paper is willing to draw.

For a visualization of monosynaptic connectivity, matching the paper's drawing
floor is the defensible choice, so MIN_SYN defaults to 5. This is NOT a
reproduction of the paper's analysis and captions must not imply that it is.

Synapse queries are cached to parquet, so changing the threshold later costs
nothing.

  python banc_shotA_cast.py [min_syn]
"""
import json
import os
import sys

import caveclient
import pandas as pd

MIN_SYN = int(sys.argv[1]) if len(sys.argv) > 1 else 5
ROOT = r"D:\Meshes\banc"
CACHE = os.path.join(ROOT, "cache")
os.makedirs(CACHE, exist_ok=True)

c = caveclient.CAVEclient("brain_and_nerve_cord")
MV = max(c.materialize.get_versions())
q = lambda t, **kw: c.materialize.query_table(t, materialization_version=MV, **kw)
print(f"[shotA] materialization {MV}, MIN_SYN={MIN_SYN}", flush=True)

mech = q("leg_mechanosensory_axons")
cs = q("legcs_axons")
sens = pd.concat([mech, cs], ignore_index=True)
sens = sens[sens["classification_system"].astype(str).str.upper() == "T1L"]
sensory = sorted({int(x) for x in sens["pt_root_id"] if x and int(x) != 0})

npl = q("leg_mn_neuropil_reftable_v2")
motor = sorted({int(x) for x in npl.loc[npl["tag"].astype(str) == "left_t1", "pt_root_id"]
                if x and int(x) != 0})
print(f"[shotA] {len(sensory)} T1L sensory axons, {len(motor)} left T1 motor neurons", flush=True)


def syn_chunked(key, ids, name, chunk=100):
    p = os.path.join(CACHE, f"{name}_mv{MV}.parquet")
    if os.path.exists(p):
        print(f"[shotA] cache hit {name}", flush=True)
        return pd.read_parquet(p)
    out = []
    for i in range(0, len(ids), chunk):
        df = q("synapses_v3", filter_in_dict={key: ids[i:i + chunk]},
               select_columns=["pre_pt_root_id", "post_pt_root_id"])
        out.append(df)
        print(f"    {min(i+chunk, len(ids))}/{len(ids)} -> "
              f"{sum(len(x) for x in out):,} synapses", flush=True)
    d = pd.concat(out, ignore_index=True)
    d = pd.DataFrame({"pre": d["pre_pt_root_id"].astype("int64"),
                      "post": d["post_pt_root_id"].astype("int64")})
    d.to_parquet(p)
    return d


s_out = syn_chunked("pre_pt_root_id", sensory, "sensory_out")
m_in = syn_chunked("post_pt_root_id", motor, "motor_in")
print(f"[shotA] {len(s_out):,} sensory outgoing, {len(m_in):,} motor incoming", flush=True)

# ---- how the cast changes with the threshold ---------------------------------
print("\n[shotA] sensitivity to the threshold:")
print(f"  {'thr':>4} {'interneurons':>13} {'direct sens->motor':>19}")
a = s_out.groupby("post").size()
b = m_in.groupby("pre").size()
direct_all = s_out[s_out["post"].isin(motor)].groupby(["pre", "post"]).size()
for t in (1, 3, 5, 10, 20):
    inter_t = set(a[a >= t].index) & set(b[b >= t].index) - set(sensory) - set(motor)
    print(f"  {t:>4} {len(inter_t):>13} {int((direct_all >= t).sum()):>19}")

# ---- the chosen cast ----------------------------------------------------------
from_sens = a[a >= MIN_SYN]
to_motor = b[b >= MIN_SYN]
inter = sorted(set(from_sens.index) & set(to_motor.index) - set(sensory) - set(motor))

df = pd.DataFrame({"root_id": inter,
                   "syn_from_sensory": [int(from_sens[i]) for i in inter],
                   "syn_to_motor": [int(to_motor[i]) for i in inter]})
# rank by the WEAKER link: a relay must be substantial on both sides, otherwise
# lopsided premotor cells (12 in, 1802 out) crowd out genuine relays
df["relay"] = df[["syn_from_sensory", "syn_to_motor"]].min(axis=1)
df = df.sort_values("relay", ascending=False).reset_index(drop=True)
print(f"\n[shotA] interneurons at MIN_SYN={MIN_SYN}: {len(df)}")
print(df.head(12).to_string(index=False), flush=True)

N = 75
sel = df.head(N)
n_direct = int((direct_all >= MIN_SYN).sum())
print(f"\n[shotA] taking top {N} by relay strength "
      f"({sel['relay'].min()} to {sel['relay'].max()} synapses on the weaker side)")
print(f"[shotA] direct sensory->motor connections at >={MIN_SYN}: {n_direct}", flush=True)

groups = {"sensory": sensory, "motor": motor,
          "interneurons": [int(x) for x in sel["root_id"]],
          "min_syn": MIN_SYN, "n_direct_sensory_to_motor": n_direct,
          "materialization": int(MV)}
json.dump(groups, open(os.path.join(ROOT, "shotA_groups.json"), "w"), indent=1)
json.dump(sensory + motor + [int(x) for x in sel["root_id"]],
          open(os.path.join(ROOT, "shotA_ids.json"), "w"))
df.to_csv(os.path.join(ROOT, "shotA_cast.csv"), index=False)
print(f"[shotA] cast: {len(sensory)} + {len(motor)} + {N} = "
      f"{len(sensory) + len(motor) + N} cells", flush=True)
