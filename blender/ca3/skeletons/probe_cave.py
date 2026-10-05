import sys, json, traceback
from caveclient import CAVEclient
import caveclient
print('caveclient', caveclient.__version__, flush=True)
c = CAVEclient('zheng_ca3')
print('datastack ok', flush=True)
try:
    print('available services:', c.info.get_datastack_info().get('skeleton_source', 'NO skeleton_source key'), flush=True)
except Exception as e:
    print('info err', e, flush=True)
try:
    info = c.info.get_datastack_info()
    print(json.dumps({k: str(v)[:120] for k, v in info.items()}, indent=1), flush=True)
except Exception as e:
    print('dsinfo err', e, flush=True)
try:
    sk = c.skeleton
    print('has .skeleton ->', sk, flush=True)
    for m in ('get_versions','get_skeleton','skeletons_exist','get_cache_contents'):
        print('  method', m, hasattr(sk, m), flush=True)
    try:
        print('versions:', sk.get_versions(), flush=True)
    except Exception as e:
        print('  get_versions FAILED:', type(e).__name__, str(e)[:300], flush=True)
    try:
        s = sk.get_skeleton(648518346438632877)
        print('GOT SKELETON', type(s), flush=True)
        if isinstance(s, dict):
            print('keys', list(s.keys()), flush=True)
    except Exception as e:
        print('  get_skeleton FAILED:', type(e).__name__, str(e)[:400], flush=True)
except Exception as e:
    print('no .skeleton:', type(e).__name__, str(e)[:300], flush=True)
print('PROBE DONE', flush=True)
