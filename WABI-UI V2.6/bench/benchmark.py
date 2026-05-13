import os
import json
import time
import random
from dotenv import load_dotenv
from typing import Dict, Any, List, Callable

from langgraph_app.agents.ui_render.ui_node import ui_node, flush_metrics

load_dotenv()


def load_dataset(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_state(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent": item.get("intent"),
        "user_input": item.get("user_input"),
        "agent_response": item.get("agent_response"),
        "safety_passed": True,
    }


def run_mode(items: List[Dict[str, Any]], mode: str, log: Callable[[str], None]) -> None:
    os.environ["UI_RENDER_MODE"] = mode
    
    total = len(items)
    t0 = time.time()
    count = 0
    
    for i, it in enumerate(items, start=1):
        st = build_state(it)
        item_t0 = time.time()
        try:
            ui_node(st)
            ok = True
            err_msg = ""
        except Exception as exc:
            ok = False
            err_msg = str(exc)
        item_dt = time.time() - item_t0
        count += 1
        pct = count / total * 100.0
        msg = f"[{mode}] {count}/{total} ({pct:.1f}%) id={it.get('id')} elapsed={item_dt:.2f}s status={'OK' if ok else 'ERR'}"
        if not ok:
            msg += f" | {err_msg}"
        log(msg)
    dt = time.time() - t0
    log(f"[{mode}] done {count}/{total} items in {dt:.2f}s")


def main():
    base = os.path.dirname(__file__)
    # Log file: timestamped, saved alongside this script
    ts = time.strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(base, f"benchmark_{ts}.log")
    f = open(log_path, "a", encoding="utf-8")
    def tee(msg: str):
        print(msg)
        try:
            f.write(msg + "\n")
            f.flush()
        except Exception:
            pass
    dataset_path = os.path.join(base, "test_dataset.json")
    items = load_dataset(dataset_path)
    # You can adjust limit for a shorter run
    limit = 1
    if limit and limit < len(items):
        sampled_items = random.sample(items, limit)
        tee(f"Benchmark start | dataset={os.path.basename(dataset_path)} | total_items={len(items)} | sampled={len(sampled_items)}")
    else:
        sampled_items = items
        tee(f"Benchmark start | dataset={os.path.basename(dataset_path)} | total_items={len(items)} | sampled=all")
    run_mode(sampled_items, "plan", log=tee)
    run_mode(sampled_items, "html", log=tee)
    run_mode(sampled_items, "image", log=tee)
    flush_metrics(timeout_s=5.0)
    tee("Benchmark finished. Results appended to ui_node_metrics.csv")
    tee(f"Log saved to: {log_path}")
    f.close()


if __name__ == "__main__":
    main()
