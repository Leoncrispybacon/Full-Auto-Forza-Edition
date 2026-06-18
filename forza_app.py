# ============================================================
#  forza_app.py — Entry point for Forza Auto GUI app
#  Flat file structure — no package folders needed
# ============================================================

import sys
import os
import traceback

# Cap native thread pools BEFORE cv2 / numpy / onnxruntime load — each defaults
# to ALL cores, which pegs CPU and lags the game during detection/OCR. Env must
# be set before those libs import (the pools read it once at load). This is the
# lever cv2.setNumThreads alone missed: an OpenMP-built OpenCV and onnxruntime
# both honor these, not setNumThreads. setdefault so a real env override wins.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
           "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
# The bigger win, and resolution-independent: stop idle worker threads from
# BUSY-SPINNING between detections. OpenMP defaults to active-wait (Intel OpenMP
# KMP_BLOCKTIME=200ms spins after every parallel region), which pegs cores even
# when each detection's actual work is tiny — exactly what 1080p users hit.
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")  # idle OpenMP threads sleep
os.environ.setdefault("KMP_BLOCKTIME", "0")          # Intel OpenMP: no post-region spin

def _except_hook(exc_type, exc_value, exc_tb):
    import tkinter.messagebox as mb
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    # Persist the crash so frozen --windowed failures (no stderr, and the
    # message box can be missed/auto-closed during startup) aren't lost.
    try:
        import os as _os, sys as _sys, time as _t
        base = (_os.path.dirname(_sys.executable)
                if getattr(_sys, 'frozen', False)
                else _os.path.dirname(_os.path.abspath(_sys.argv[0])))
        with open(_os.path.join(base, 'fafe_crash.log'), 'a',
                  encoding='utf-8') as f:
            f.write(_t.strftime('%Y-%m-%d %H:%M:%S\n') + msg + '\n')
    except Exception:
        pass
    try:
        mb.showerror("Forza Auto — Error", msg)
    except Exception:
        print(msg)

sys.excepthook = _except_hook

# Background-thread crashes don't reach sys.excepthook either — route them here.
import threading as _threading
def _thread_excepthook(args):
    _except_hook(args.exc_type, args.exc_value, args.exc_traceback)
try:
    _threading.excepthook = _thread_excepthook
except Exception:
    pass

# ── Path setup for frozen exe and dev ────────────────────────
if getattr(sys, 'frozen', False):
    # --onedir: exe and all files are in the same folder
    BASE = os.path.dirname(sys.executable)
    sys.path.insert(0, BASE)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE)

# ── Launch ────────────────────────────────────────────────────
import customtkinter as ctk
from main_window import MainWindow

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
