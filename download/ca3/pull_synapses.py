"""
Pull the ENTIRE synapses_ca3_v1 table (36.8M rows) from CAVE mat 671.

Only 4 payload columns: pre_pt_root_id, post_pt_root_id, size, ctr_pt_position.
id-range chunks hit the primary-key index, so each 500k-id chunk returns in ~15s.
Threads give ~100k rows/s.

Output: D:\\Meshes\\syn_chunks\\c<lo>.parquet  (one per chunk, resumable)
"""
import os, sys, time, random, traceback
from pathlib import Path
import numpy as np
import pandas as pd
import requests

# CAVE will happily leave a socket hanging forever. A first run stalled with 8
# dead connections and zero progress while the server itself answered in 2.3 s.
# Force a timeout on every HTTP call caveclient makes.
_orig_request = requests.Session.request
def _timed_request(self, *a, **kw):
    kw.setdefault("timeout", (15, 180))
    return _orig_request(self, *a, **kw)
requests.Session.request = _timed_request

from caveclient import CAVEclient
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT = Path(r"D:\Meshes\syn_chunks")
OUT.mkdir(exist_ok=True)
MAXID = 46_300_000
STEP = 500_000          # keep: the 17 chunks already on disk use this stride
WORKERS = 6
COLS = ['pre_pt_root_id', 'post_pt_root_id', 'size', 'ctr_pt_position']

_local = {}


def get_client():
    tid = os.getpid(), __import__('threading').get_ident()
    if tid not in _local:
        c = CAVEclient("zheng_ca3")
        c.materialize.version = 671
        _local[tid] = c
    return _local[tid]


def chunk(lo):
    hi = lo + STEP
    dst = OUT / f"c{lo:09d}.parquet"
    if dst.exists():
        return lo, -1, 0.0
    for attempt in range(6):
        try:
            t0 = time.time()
            time.sleep(random.random() * 0.5)
            d = get_client().materialize.query_table(
                'synapses_ca3_v1',
                filter_greater_dict={'id': lo},
                filter_less_equal_dict={'id': hi},
                select_columns=COLS, split_positions=True, log_warning=False)
            d = d.astype({'pre_pt_root_id': 'int64', 'post_pt_root_id': 'int64',
                          'size': 'float32', 'ctr_pt_position_x': 'int32',
                          'ctr_pt_position_y': 'int32', 'ctr_pt_position_z': 'int32'})
            d.to_parquet(dst.with_suffix('.tmp'), index=False)
            dst.with_suffix('.tmp').replace(dst)
            return lo, len(d), time.time() - t0
        except Exception as exc:
            print(f"  chunk {lo} try {attempt+1}: {type(exc).__name__} {str(exc)[:120]}",
                  flush=True)
            if attempt == 5:
                print(f"  CHUNK {lo} FAILED after 6 tries", flush=True)
                return lo, -2, 0.0
            time.sleep(5 * (attempt + 1))


los = list(range(0, MAXID, STEP))
print(f"{len(los)} chunks of {STEP} ids, {WORKERS} workers", flush=True)
t0all = time.time()
tot = done = failed = 0
with ThreadPoolExecutor(WORKERS) as ex:
    futs = [ex.submit(chunk, lo) for lo in los]
    for f in as_completed(futs):
        lo, n, dt = f.result()
        done += 1
        if n == -2:
            failed += 1
        elif n >= 0:
            tot += n
        if done % 5 == 0:
            el = time.time() - t0all
            print(f"  {done}/{len(los)} chunks, {tot:,} rows, {el/60:.1f} min, "
                  f"eta {el/done*(len(los)-done)/60:.1f} min", flush=True)

print(f"\ndone: {tot:,} new rows, {failed} failed chunks, "
      f"{(time.time()-t0all)/60:.1f} min", flush=True)
mb = sum(p.stat().st_size for p in OUT.glob('*.parquet')) / 1024**2
print(f"{len(list(OUT.glob('*.parquet')))} files, {mb:,.0f} MB", flush=True)
print("PULL DONE", flush=True)
