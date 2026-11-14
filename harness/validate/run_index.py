"""Incremental byte-offset run index for O(Δ) live status and O(1) cell detail access.

Avoids re-reading growing ``results.jsonl`` files on every live dashboard poll
or cell click:
  - Tail-reads only newly appended ``\\n``-terminated lines from ``(st_ino, _offset)``.
  - Records ``(byte_offset, byte_length)`` per ``(scenario_id, backend_id)`` so
    ``get_detail(scenario, backend)`` seeks directly to the 1..K rows for that cell.
  - Caches sidecar metadata (``events.jsonl``, ``run_meta.json``, ``run_manifest.json``,
    ``suite.json``, ``judge*.jsonl``, ``judges/check-precision.json``, ``trace.jsonl``,
    ``inputs/scenarios/*.json``, ``inputs/charts/*.json``, and ``inputs/contexts/*.json``)
    by ``(st_ino, st_mtime_ns, st_size)``.
  - Maintains a bounded ``seq`` delta ring buffer so ``get_status(since_seq=...)``
    and SSE ``/api/stream`` emit only changed grid cells and summary counters.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Any

from harness.common.jsonl import read_jsonl as _read_jsonl
from harness.validate.bundle import run_chart
from harness.validate.check_precision import load_scores as load_check_precision
from harness.validate.context_store import rehydrate_response_envelope
from harness.validate.dashboard_data import (
    CLASSIFIER_SOURCE,
    _CLASSIFIER_ERROR,
    _make_feed_item,
    _read_scenario_expectations,
    _read_scenario_turn_count,
    _row_conformed,
    _row_judged,
    arm_models,
    build_detail_from_rows,
    catalyst_expectation,
    profile_titles,
    read_judge_actors,
    run_family,
)
from harness.validate.judging import judge_summary
from harness.validate.reconcile import combined_judge_summary, scout_summary
from harness.validate.review_presentation import (
    row_review_summary,
    status_display,
    status_legend,
    worst_status,
)


_ACTIVE_WINDOW_S = 120.0
_DELTA_HISTORY_LEN = 64


def _file_sig(path: Path) -> tuple[int, int, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (int(st.st_ino), int(st.st_mtime_ns), int(st.st_size))


class RunIndex:
    """Thread-safe incremental index over one evaluation run directory."""

    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir).resolve()
        self._lock = threading.RLock()
        self.seq = 0
        self.last_access = time.monotonic()

        # results.jsonl incremental cursor & accumulators
        self._res_ino: int | None = None
        self._res_offset: int = 0
        self._res_mtime: float = 0.0
        self._res_exists: bool = False
        self._row_count: int = 0
        self._scored_count: int = 0
        self._judged_passed: int = 0

        self._cell_offsets: dict[tuple[str, str], list[tuple[int, int]]] = {}
        self._cell_digests: dict[tuple[str, str], dict[str, Any]] = {}
        self._arm_acc: dict[str, dict[str, Any]] = {}
        self._obs_scenarios: list[str] = []
        self._obs_scenarios_set: set[str] = set()
        self._obs_backends: list[str] = []
        self._obs_backends_set: set[str] = set()
        self._max_obs_turns: dict[str, int] = {}
        self._feed_ring: deque[dict[str, Any]] = deque(maxlen=14)

        # Sidecar caches keyed by _file_sig(...)
        self._events_sig: Any = "__unset__"
        self._events: list[dict[str, Any]] = []
        self._run_ev: dict[str, Any] = {}
        self._labels: dict[str, str] = {}
        self._transport: str | None = None

        self._meta_sig: Any = "__unset__"
        self._run_meta: dict[str, Any] = {}

        self._manifest_sig: Any = "__unset__"
        self._family: str = "chartsearchai"

        self._suite_sig: Any = "__unset__"
        self._suite_exists: bool = False
        self._cat_exp_cache: dict[str, dict[str, Any] | None] = {}

        self._judge_sigs: Any = "__unset__"
        self._judge_actors: dict[str, list[dict[str, Any]]] = {}
        self._judge_by_cell: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        self._canonical_rows: list[dict[str, Any]] = []
        self._judging_summary: dict[str, Any] = {}

        self._cp_sig: Any = "__unset__"
        self._check_precision: Any = None

        self._trace_sig: Any = "__unset__"
        self._traces: list[dict[str, Any]] = []

        self._scen_turn_counts: dict[str, tuple[Any, int | None]] = {}
        self._scen_exp_cache: dict[str, tuple[Any, dict[str, Any]]] = {}
        self._chart_cache: dict[str, tuple[Any, dict[str, Any] | None]] = {}
        self._ctx_cache: dict[str, dict[str, Any]] = {}

        self._last_active: bool = False
        self._prev_running_key: tuple[str, str] | None = None
        self._grid_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._seq_history: deque[tuple[int, set[tuple[str, str]]]] = deque(
            maxlen=_DELTA_HISTORY_LEN
        )
        self._last_grid_sig: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())

    def _reset_results_state(self) -> None:
        self._res_ino = None
        self._res_offset = 0
        self._res_mtime = 0.0
        self._res_exists = False
        self._row_count = 0
        self._scored_count = 0
        self._judged_passed = 0
        self._cell_offsets.clear()
        self._cell_digests.clear()
        self._arm_acc.clear()
        self._obs_scenarios.clear()
        self._obs_scenarios_set.clear()
        self._obs_backends.clear()
        self._obs_backends_set.clear()
        self._max_obs_turns.clear()
        self._feed_ring.clear()
        self._prev_running_key = None
        self._grid_cache.clear()
        self._seq_history.clear()

    def _refresh_sidecars(self) -> tuple[bool, bool]:
        meta_changed = False
        events_path = self.run_dir / "events.jsonl"
        ev_sig = _file_sig(events_path)
        if ev_sig != self._events_sig:
            self._events_sig = ev_sig
            self._events = _read_jsonl(events_path, strict=False) if ev_sig else []
            self._run_ev = next(
                (e for e in self._events if e.get("event_type") == "run"), {}
            )
            self._labels = {
                e["backend_id"]: e.get("label", "")
                for e in self._events
                if e.get("event_type") == "backend_selected" and "backend_id" in e
            }
            self._transport = next(
                (
                    str(e.get("transport")).strip()
                    for e in self._events
                    if str(e.get("transport") or "").strip()
                ),
                None,
            )
            if not self._transport:
                for p in sorted((self.run_dir / "inputs" / "comparison_sets").glob("*.json")):
                    try:
                        d = json.loads(p.read_text(encoding="utf-8"))
                        if isinstance(d, dict) and d.get("transport"):
                            self._transport = str(d["transport"]).strip()
                            break
                    except Exception:
                        continue
            meta_changed = True

        meta_path = self.run_dir / "run_meta.json"
        m_sig = _file_sig(meta_path)
        if m_sig != self._meta_sig:
            self._meta_sig = m_sig
            if m_sig is not None:
                try:
                    loaded = json.loads(meta_path.read_text(encoding="utf-8"))
                    self._run_meta = loaded if isinstance(loaded, dict) else {}
                except Exception:
                    self._run_meta = {}
            else:
                self._run_meta = {}
            meta_changed = True

        man_sig = _file_sig(self.run_dir / "run_manifest.json")
        suite_sig = _file_sig(self.run_dir / "suite.json")
        if man_sig != self._manifest_sig or suite_sig != self._suite_sig:
            self._manifest_sig = man_sig
            if suite_sig != self._suite_sig:
                self._suite_sig = suite_sig
                self._suite_exists = suite_sig is not None
                self._cat_exp_cache.clear()
            self._family = run_family(self.run_dir)
            meta_changed = True

        judge_sigs: list[tuple[str, Any]] = [("root", _file_sig(self.run_dir / "judge.jsonl"))]
        judges_dir = self.run_dir / "judges"
        if judges_dir.is_dir():
            for jp in sorted(judges_dir.glob("*/judge.jsonl")):
                judge_sigs.append((jp.parent.name, _file_sig(jp)))
        judge_sigs_tuple = tuple(judge_sigs)
        if judge_sigs_tuple != self._judge_sigs:
            self._judge_sigs = judge_sigs_tuple
            self._judge_actors = read_judge_actors(self.run_dir)
            self._judge_by_cell.clear()
            for actor, a_rows in self._judge_actors.items():
                for jr in a_rows:
                    sid = str(jr.get("scenario_id") or "")
                    bid = str(jr.get("backend_id") or "")
                    if sid and bid:
                        self._judge_by_cell.setdefault((sid, bid), {}).setdefault(actor, jr)
            self._canonical_rows = (
                _read_jsonl(self.run_dir / "judge.jsonl", strict=False)
                if judge_sigs[0][1] is not None
                else []
            )
            self._judging_summary = judge_summary(self.run_dir)
            meta_changed = True

        cp_sig = _file_sig(self.run_dir / "judges" / "check-precision.json")
        if cp_sig != self._cp_sig:
            self._cp_sig = cp_sig
            self._check_precision = load_check_precision(self.run_dir)
            meta_changed = True

        return meta_changed, bool(self._events)

    def _consume_row(
        self, row: dict[str, Any], offset: int, length: int
    ) -> tuple[str, str] | None:
        sid = str(row.get("scenario_id") or "")
        bid = str(row.get("backend_id") or "")
        key = (sid, bid)
        self._cell_offsets.setdefault(key, []).append((offset, length))
        self._row_count += 1

        if sid and sid not in self._obs_scenarios_set:
            self._obs_scenarios_set.add(sid)
            self._obs_scenarios.append(sid)
        if bid and bid not in self._obs_backends_set:
            self._obs_backends_set.add(bid)
            self._obs_backends.append(bid)

        t_val = row.get("turn") or 1
        if isinstance(t_val, int) and sid and t_val > self._max_obs_turns.get(sid, 0):
            self._max_obs_turns[sid] = t_val

        m = row.get("metrics") or {}
        http_status = m.get("http_status")
        if bid:
            acc = self._arm_acc.get(bid)
            if acc is None:
                acc = {"rows": 0, "errors": 0, "lat_sum": 0, "ch_sum": 0, "last": ""}
                self._arm_acc[bid] = acc
            acc["rows"] += 1
            if http_status != 200:
                acc["errors"] += 1
            acc["lat_sum"] += m.get("latency_ms", 0) or 0
            acc["ch_sum"] += m.get("answer_chars", 0) or 0
            if sid:
                acc["last"] = sid

        digest = self._cell_digests.get(key)
        if digest is None:
            digest = {
                "rows": 0,
                "good": 0,
                "bad": 0,
                "has_passed": False,
                "row_reviews": [],
            }
            self._cell_digests[key] = digest
        digest["rows"] += 1
        if _row_conformed(row):
            digest["good"] += 1
        if http_status not in (200, None):
            digest["bad"] += 1
        if "passed" in m:
            digest["has_passed"] = True
            self._scored_count += 1
            if _row_judged(row):
                self._judged_passed += 1
        elif not digest["has_passed"]:
            digest["row_reviews"].append(row_review_summary(row))

        self._feed_ring.append(_make_feed_item(row))
        return key

    def refresh(self) -> bool:
        """Synchronize incremental state with disk; return True if any observed state changed."""
        with self._lock:
            self.last_access = time.monotonic()
            dirty_cells: set[tuple[str, str]] = set()
            meta_changed, _ = self._refresh_sidecars()
            data_changed = meta_changed

            res_path = self.run_dir / "results.jsonl"
            try:
                st = os.stat(res_path)
                exists = True
            except OSError:
                st = None
                exists = False

            if not exists or st is None:
                if self._res_exists or self._res_ino is not None or self._row_count > 0:
                    self._reset_results_state()
                    data_changed = True
            else:
                if self._res_ino is not None and (
                    st.st_ino != self._res_ino or st.st_size < self._res_offset
                ):
                    self._reset_results_state()
                    data_changed = True

                self._res_exists = True
                self._res_ino = int(st.st_ino)
                self._res_mtime = float(st.st_mtime)

                if st.st_size > self._res_offset:
                    with res_path.open("rb") as fh:
                        fh.seek(self._res_offset)
                        while True:
                            line_off = fh.tell()
                            raw_line = fh.readline()
                            if not raw_line:
                                break
                            # Never consume a partial line currently mid-write.
                            if not raw_line.endswith(b"\n"):
                                break
                            self._res_offset = fh.tell()
                            text = raw_line.decode("utf-8", errors="replace").strip()
                            if not text:
                                continue
                            try:
                                row = json.loads(text)
                            except json.JSONDecodeError:
                                continue
                            if not isinstance(row, dict):
                                continue
                            cell_key = self._consume_row(row, line_off, len(raw_line))
                            if cell_key is not None:
                                dirty_cells.add(cell_key)
                                data_changed = True

            active = bool(self._res_exists and (time.time() - self._res_mtime) < _ACTIVE_WINDOW_S)
            if active != self._last_active:
                self._last_active = active
                data_changed = True

            if data_changed or self.seq == 0:
                self.seq += 1
                if self.seq > 1:
                    self._seq_history.append((self.seq, set(dirty_cells)))
            return data_changed

    def _active_now(self) -> bool:
        return bool(self._res_exists and (time.time() - self._res_mtime) < _ACTIVE_WINDOW_S)

    def _layout(self) -> tuple[list[str], list[str], list[tuple[str, str]], dict[tuple[str, str], int], int, bool]:
        run_ev = self._run_ev
        cells = run_ev.get("cells")
        if cells:
            expected_cells = [(c["scenario_id"], c["backend_id"]) for c in cells]
            exp_turns = {(c["scenario_id"], c["backend_id"]): c["turns"] for c in cells}
            total = sum(c["turns"] for c in cells)
            scen_ids = list(dict.fromkeys(c["scenario_id"] for c in cells))
            back_ids = list(dict.fromkeys(c["backend_id"] for c in cells))
            return scen_ids, back_ids, expected_cells, exp_turns, total, True

        scen_ids = list(run_ev.get("scenario_ids", [])) or list(self._obs_scenarios)
        back_ids = list(run_ev.get("backend_ids", [])) or list(self._obs_backends)
        turns: dict[str, int] = {}
        for sid in scen_ids:
            scen_path = self.run_dir / "inputs" / "scenarios" / f"{sid}.json"
            sig = _file_sig(scen_path)
            cached = self._scen_turn_counts.get(sid)
            if cached is None or cached[0] != sig:
                cnt = _read_scenario_turn_count(self.run_dir, sid)
                self._scen_turn_counts[sid] = (sig, cnt)
            else:
                cnt = cached[1]
            turns[sid] = cnt if cnt is not None else (self._max_obs_turns.get(sid) or 1)
        expected_cells = [(s, b) for s in scen_ids for b in back_ids]
        exp_turns = {(s, b): turns.get(s, 1) for (s, b) in expected_cells}
        total = sum(turns.values()) * len(back_ids) if back_ids else 0
        return scen_ids, back_ids, expected_cells, exp_turns, total, False

    def _compute_grid_and_states(
        self,
        scen_ids: list[str],
        back_ids: list[str],
        expected_cells: list[tuple[str, str]],
        exp_turns: dict[tuple[str, str], int],
        total: int,
        has_cells_spec: bool,
        active: bool,
    ) -> tuple[dict[tuple[str, str], str], list[dict[str, Any]], set[tuple[str, str]]]:
        states: dict[tuple[str, str], str] = {}
        for s, b in expected_cells:
            exp = exp_turns.get((s, b), 1)
            digest = self._cell_digests.get((s, b))
            if digest is None:
                st = "pending"
            elif digest["bad"] > 0:
                st = "err"
            elif digest["good"] >= exp:
                st = "done"
            elif digest["rows"] >= exp:
                st = "err"
            else:
                st = "running" if active else "err"
            states[(s, b)] = st

        running_key: tuple[str, str] | None = None
        if total and self._row_count < total and active:
            if has_cells_spec:
                for s, b in expected_cells:
                    if states[(s, b)] in ("pending", "running"):
                        states[(s, b)] = "running"
                        running_key = (s, b)
                        break
            else:
                for b in back_ids:
                    for s in scen_ids:
                        if states[(s, b)] in ("pending", "running"):
                            states[(s, b)] = "running"
                            running_key = (s, b)
                            break
                    if running_key is not None:
                        break

        extra_changed: set[tuple[str, str]] = set()
        if running_key != self._prev_running_key:
            if self._prev_running_key is not None:
                extra_changed.add(self._prev_running_key)
            if running_key is not None:
                extra_changed.add(running_key)
            self._prev_running_key = running_key

        grid_list: list[dict[str, Any]] = []
        new_grid_cache: dict[tuple[str, str], dict[str, Any]] = {}
        for s, b in expected_cells:
            entry: dict[str, Any] = {
                "scenario": s,
                "backend": b,
                "state": states[(s, b)],
            }
            digest = self._cell_digests.get((s, b))
            if digest is not None and not digest["has_passed"] and digest["row_reviews"]:
                revs = digest["row_reviews"]
                ans = worst_status([x["answer"] for x in revs]) or "not_checked"
                ind = worst_status([x["indepth"] for x in revs])
                entry.update(
                    {
                        "answer": status_display(ans) if ans else None,
                        "indepth": status_display(ind) if ind else None,
                        "marked": sum(x["marked"] for x in revs),
                    }
                )
            prev_entry = self._grid_cache.get((s, b))
            if prev_entry != entry:
                extra_changed.add((s, b))
            new_grid_cache[(s, b)] = entry
            grid_list.append(entry)

        self._grid_cache = new_grid_cache
        return states, grid_list, extra_changed

    def _build_arms(self, back_ids: list[str]) -> dict[str, dict[str, Any]]:
        arms: dict[str, dict[str, Any]] = {}
        for b in back_ids:
            acc = self._arm_acc.get(b)
            n_rs = acc["rows"] if acc else 0
            arms[b] = {
                "label": self._labels.get(b, b),
                "rows": n_rs,
                "errors": acc["errors"] if acc else 0,
                "avg_latency_ms": (acc["lat_sum"] // n_rs) if n_rs else 0,
                "avg_chars": (acc["ch_sum"] // n_rs) if n_rs else 0,
                "last": acc["last"] if acc else "",
            }
        return arms

    def get_status(self, *, since_seq: int | None = None) -> dict[str, Any]:
        """Return full status dict or compact ``since_seq`` delta in O(Δ) time."""
        with self._lock:
            self.refresh()
            active = self._active_now()
            scen_ids, back_ids, expected_cells, exp_turns, total, has_cells = self._layout()
            states, grid_list, layout_changed = self._compute_grid_and_states(
                scen_ids, back_ids, expected_cells, exp_turns, total, has_cells, active
            )

            grid_sig = (tuple(scen_ids), tuple(back_ids))
            layout_reset = grid_sig != self._last_grid_sig
            self._last_grid_sig = grid_sig

            if layout_changed and self.seq > 0 and self._seq_history:
                last_s, last_set = self._seq_history[-1]
                if last_s == self.seq:
                    last_set.update(layout_changed)

            conformant = sum(1 for v in states.values() if v == "done")
            unexpected = sum(1 for v in states.values() if v == "err")
            finished = bool(total) and self._row_count >= total
            arms = self._build_arms(back_ids)

            if (
                since_seq is not None
                and not layout_reset
                and since_seq == self.seq
            ):
                return {
                    "run": self.run_dir.name,
                    "seq": self.seq,
                    "delta": True,
                    "unchanged": True,
                    "active": active,
                    "done": self._row_count,
                    "total": total,
                    "finished": finished,
                }

            can_delta = (
                since_seq is not None
                and not layout_reset
                and 0 < since_seq < self.seq
                and bool(self._seq_history)
                and self._seq_history[0][0] <= since_seq + 1
            )

            arm_cards_map = {
                bid: (self._run_meta.get("arm_cards") or {}).get(bid)
                for bid in back_ids
            }

            if can_delta:
                changed_keys: set[tuple[str, str]] = set(layout_changed)
                for s_no, keys in self._seq_history:
                    if s_no > since_seq:
                        changed_keys.update(keys)
                grid_updates = [
                    self._grid_cache[k]
                    for k in changed_keys
                    if k in self._grid_cache
                ]
                return {
                    "run": self.run_dir.name,
                    "seq": self.seq,
                    "delta": True,
                    "unchanged": False,
                    "active": active,
                    "family": self._family,
                    "check_precision": self._check_precision,
                    "done": self._row_count,
                    "total": total,
                    "conformant": conformant,
                    "unexpected": unexpected,
                    "judged_passed": self._judged_passed,
                    "judged_scored": self._scored_count,
                    "arms": arms,
                    "arm_cards": arm_cards_map,
                    "judge": scout_summary(self._canonical_rows, back_ids)
                    if self._canonical_rows
                    else [],
                    "judge_actors": sorted(self._judge_actors.keys()),
                    "judging": self._judging_summary,
                    "judge_combined": combined_judge_summary(
                        self._judge_actors, back_ids
                    ),
                    "grid_updates": grid_updates,
                    "feed": list(self._feed_ring),
                    "finished": finished,
                }

            return {
                "run": self.run_dir.name,
                "seq": self.seq,
                "active": active,
                "family": self._family,
                "check_precision": self._check_precision,
                "set": self._run_ev.get("comparison_set"),
                "done": self._row_count,
                "total": total,
                "warning": (
                    None
                    if CLASSIFIER_SOURCE
                    else "This page cannot classify assertions ("
                    + _CLASSIFIER_ERROR
                    + "), so every failure is shown as unexpected behaviour. "
                    "Serve the dashboard from a checkout whose harness package "
                    "matches this script."
                ),
                "conformant": conformant,
                "unexpected": unexpected,
                "judged_passed": self._judged_passed,
                "judged_scored": self._scored_count,
                "scenarios": scen_ids,
                "backends": back_ids,
                "arms": arms,
                "arm_cards": arm_cards_map,
                "judge": scout_summary(self._canonical_rows, back_ids)
                if self._canonical_rows
                else [],
                "judge_actors": sorted(self._judge_actors.keys()),
                "judging": self._judging_summary,
                "judge_combined": combined_judge_summary(
                    self._judge_actors, back_ids
                ),
                "grid": grid_list,
                "feed": list(self._feed_ring),
                "models": arm_models(self.run_dir, arm_cards_map),
                "status_legend": status_legend(),
                "profile_titles": profile_titles(self.run_dir, back_ids),
                "finished": finished,
            }

    def get_detail(self, scenario: str, backend: str) -> dict[str, Any]:
        """Return cell detail using O(1) byte-offset seek/read into ``results.jsonl``."""
        if not scenario or not backend:
            return {"turns": []}
        with self._lock:
            self.refresh()
            slices = self._cell_offsets.get((scenario, backend), [])
            rows: list[dict[str, Any]] = []
            res_path = self.run_dir / "results.jsonl"
            backends_meta = self._run_meta.get("backends") or {}
            if slices and res_path.is_file():
                with res_path.open("rb") as fh:
                    for off, length in slices:
                        fh.seek(off)
                        raw = fh.read(length).decode("utf-8", errors="replace").strip()
                        if not raw:
                            continue
                        try:
                            row = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(row, dict):
                            continue
                        req = row.get("request") or {}
                        row["request"] = req
                        if "patient" not in req and row.get("patient_id"):
                            req["patient"] = str(row["patient_id"])
                        b_meta = backends_meta.get(row.get("backend_id")) or {}
                        if "profile" not in req and b_meta.get("provider") != "bundled":
                            model = b_meta.get("modelName")
                            if model:
                                req["profile"] = model
                        if "transport" not in req and self._transport:
                            req["transport"] = self._transport
                        if isinstance(row.get("response"), dict) and "context_ref" in row["response"]:
                            row["response"] = rehydrate_response_envelope(
                                self.run_dir, row["response"], cache=self._ctx_cache
                            )
                        ind = row.get("indepth")
                        if isinstance(ind, dict) and isinstance(ind.get("response"), dict) and "context_ref" in ind["response"]:
                            ind["response"] = rehydrate_response_envelope(
                                self.run_dir, ind["response"], cache=self._ctx_cache
                            )
                        rows.append(row)

            tr_sig = _file_sig(self.run_dir / "trace.jsonl")
            if tr_sig != self._trace_sig:
                self._trace_sig = tr_sig
                self._traces = (
                    _read_jsonl(self.run_dir / "trace.jsonl", strict=False)
                    if tr_sig is not None
                    else []
                )

            scen_sig = _file_sig(self.run_dir / "inputs" / "scenarios" / f"{scenario}.json")
            cached_exp = self._scen_exp_cache.get(scenario)
            if cached_exp is None or cached_exp[0] != scen_sig:
                exp = _read_scenario_expectations(self.run_dir, scenario)
                self._scen_exp_cache[scenario] = (scen_sig, exp)
            else:
                exp = cached_exp[1]

            chart_sig = (
                _file_sig(self.run_dir / "inputs" / "charts"),
                _file_sig(self.run_dir / "inputs" / "charts" / f"{scenario}.json"),
                scen_sig,
            )
            cached_chart = self._chart_cache.get(scenario)
            if cached_chart is None or cached_chart[0] != chart_sig:
                chart_fixture = run_chart(self.run_dir, scenario)
                self._chart_cache[scenario] = (chart_sig, chart_fixture)
            else:
                chart_fixture = cached_chart[1]

            if self._family == "catalyst":
                if scenario not in self._cat_exp_cache:
                    self._cat_exp_cache[scenario] = catalyst_expectation(self.run_dir, scenario)
                cat_exp = self._cat_exp_cache[scenario]
            else:
                cat_exp = None

            return build_detail_from_rows(
                self.run_dir,
                scenario,
                backend,
                rows,
                traces=self._traces,
                judge_by_actor=self._judge_by_cell.get((scenario, backend), {}),
                chart_fixture=chart_fixture,
                chart_loaded=True,
                expectations=exp,
                catalyst_expected=cat_exp,
                family=self._family,
            )


class RunIndexRegistry:
    """Bounded LRU registry of ``RunIndex`` instances keyed by resolved run directory."""

    def __init__(self, *, max_runs: int = 16) -> None:
        self._max_runs = max(1, int(max_runs))
        self._lock = threading.Lock()
        self._entries: OrderedDict[Path, RunIndex] = OrderedDict()

    def get_if_loaded(self, run_dir: Path | str) -> RunIndex | None:
        key = Path(run_dir).resolve()
        with self._lock:
            return self._entries.get(key)

    def get(self, run_dir: Path | str) -> RunIndex:
        key = Path(run_dir).resolve()
        with self._lock:
            idx = self._entries.get(key)
            if idx is not None:
                self._entries.move_to_end(key)
                return idx
            idx = RunIndex(key)
            self._entries[key] = idx
            while len(self._entries) > self._max_runs:
                self._entries.popitem(last=False)
            return idx

    def invalidate(self, run_dir: Path | str | None = None) -> None:
        with self._lock:
            if run_dir is None:
                self._entries.clear()
            else:
                self._entries.pop(Path(run_dir).resolve(), None)


GLOBAL_RUN_INDEX = RunIndexRegistry(max_runs=16)
