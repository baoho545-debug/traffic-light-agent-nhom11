from __future__ import annotations
import csv, math, random, statistics
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Tuple

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "ket_qua"

@dataclass(frozen=True)
class TrafficScenario:
    name: str
    arrival_rate_ns: float
    arrival_rate_ew: float

@dataclass(frozen=True)
class SimulationConfig:
    simulation_seconds: int = 3600
    replications: int = 20
    service_rate: float = 0.50
    fixed_green_seconds: int = 30
    yellow_seconds: int = 3
    all_red_seconds: int = 1
    min_green_seconds: int = 25
    max_green_seconds: int = 60
    estimation_alpha: float = 0.05
    prediction_horizon: int = 20
    switch_margin: float = 5.0

SCENARIOS = [
    TrafficScenario("Thap", 0.06, 0.06),
    TrafficScenario("Trung binh", 0.14, 0.14),
    TrafficScenario("Cao", 0.22, 0.22),
]
CONFIG = SimulationConfig()

def poisson_sample(lam: float, rng: random.Random) -> int:
    if lam <= 0: return 0
    threshold = math.exp(-lam)
    product, count = 1.0, 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1

def generate_arrival_stream(scenario, seconds, seed):
    rng = random.Random(seed)
    return [(poisson_sample(scenario.arrival_rate_ns, rng),
             poisson_sample(scenario.arrival_rate_ew, rng))
            for _ in range(seconds)]

class TrafficController:
    def __init__(self, config):
        self.config = config
        self.mode = "GREEN"
        self.green_direction = "NS"
        self.elapsed = 0
        self.next_direction = "EW"
        self.switch_count = 0

    def _begin_yellow(self):
        self.mode = "YELLOW"
        self.elapsed = 0
        self.next_direction = "EW" if self.green_direction == "NS" else "NS"
        self.switch_count += 1

    def update_arrival_estimates(self, arrivals):
        pass

class FixedTimeController(TrafficController):
    def advance(self, queues, arrivals=(0, 0)):
        if self.mode == "GREEN":
            self.elapsed += 1
            if self.elapsed >= self.config.fixed_green_seconds:
                self._begin_yellow()
        elif self.mode == "YELLOW":
            self.elapsed += 1
            if self.elapsed >= self.config.yellow_seconds:
                self.mode, self.elapsed = "ALL_RED", 0
        else:
            self.elapsed += 1
            if self.elapsed >= self.config.all_red_seconds:
                self.mode, self.green_direction, self.elapsed = "GREEN", self.next_direction, 0

class ModelBasedAdaptiveController(TrafficController):
    def __init__(self, config):
        super().__init__(config)
        self.estimated_rates = {"NS": 0.10, "EW": 0.10}

    def update_arrival_estimates(self, arrivals):
        alpha = self.config.estimation_alpha
        for d, count in zip(("NS", "EW"), arrivals):
            self.estimated_rates[d] = alpha * count + (1-alpha) * self.estimated_rates[d]

    def pressure(self, direction, queues):
        return len(queues[direction]) + self.estimated_rates[direction] * self.config.prediction_horizon

    def advance(self, queues, arrivals=(0, 0)):
        if self.mode == "GREEN":
            self.elapsed += 1
            current = self.green_direction
            other = "EW" if current == "NS" else "NS"
            can_switch = self.elapsed >= self.config.min_green_seconds
            should_switch = can_switch and (
                (len(queues[current]) == 0 and len(queues[other]) > 0) or
                self.pressure(other, queues) > self.pressure(current, queues) + self.config.switch_margin
            )
            if self.elapsed >= self.config.max_green_seconds or should_switch:
                self._begin_yellow()
        elif self.mode == "YELLOW":
            self.elapsed += 1
            if self.elapsed >= self.config.yellow_seconds:
                self.mode, self.elapsed = "ALL_RED", 0
        else:
            self.elapsed += 1
            if self.elapsed >= self.config.all_red_seconds:
                self.mode, self.green_direction, self.elapsed = "GREEN", self.next_direction, 0

@dataclass
class RunMetrics:
    strategy: str
    scenario: str
    replication: int
    average_wait_seconds: float
    total_arrivals: int
    served_vehicles: int
    vehicles_remaining: int
    max_queue: int
    average_queue: float
    phase_switches: int

def simulate_one_run(scenario, strategy_name, arrival_stream, config=CONFIG, replication=1):
    queues: Dict[str, Deque[int]] = {"NS": deque(), "EW": deque()}
    controller = FixedTimeController(config) if strategy_name == "Co dinh" else ModelBasedAdaptiveController(config)
    credit = {"NS": 0.0, "EW": 0.0}
    total_wait = total_arrivals = served = max_queue = queue_sum = 0
    for second, arrivals in enumerate(arrival_stream):
        for d, count in zip(("NS", "EW"), arrivals):
            queues[d].extend([second] * count)
            total_arrivals += count
        controller.update_arrival_estimates(arrivals)
        if controller.mode == "GREEN":
            d = controller.green_direction
            credit[d] += config.service_rate
            while credit[d] >= 1 and queues[d]:
                total_wait += second - queues[d].popleft()
                served += 1
                credit[d] -= 1
            if not queues[d]:
                credit[d] = min(credit[d], 1.0)
        qlen = len(queues["NS"]) + len(queues["EW"])
        max_queue = max(max_queue, qlen)
        queue_sum += qlen
        controller.advance(queues, arrivals)
    end = len(arrival_stream)
    remaining = 0
    for d in ("NS", "EW"):
        remaining += len(queues[d])
        total_wait += sum(end - t for t in queues[d])
    return RunMetrics(strategy_name, scenario.name, replication,
        total_wait / total_arrivals if total_arrivals else 0,
        total_arrivals, served, remaining, max_queue,
        queue_sum / len(arrival_stream) if arrival_stream else 0,
        controller.switch_count)

def run_experiments(config=CONFIG, scenarios=SCENARIOS):
    OUTPUT_DIR.mkdir(exist_ok=True)
    detail = []
    for si, scenario in enumerate(scenarios):
        print(f"Dang mo phong muc luu luong: {scenario.name}...")
        for rep in range(1, config.replications + 1):
            stream = generate_arrival_stream(scenario, config.simulation_seconds,
                                             2026 + si*100000 + rep)
            for strategy in ("Co dinh", "Phan xa theo mat do"):
                detail.append(simulate_one_run(scenario, strategy, stream, config, rep).__dict__)
    with (OUTPUT_DIR/"ket_qua_chi_tiet.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(detail[0].keys())); w.writeheader(); w.writerows(detail)
    summary = summarize_results(detail, scenarios)
    with (OUTPUT_DIR/"bang_so_sanh.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader(); w.writerows(summary)
    write_report(summary, config, scenarios)
    make_charts(summary, scenarios)
    print("\nHOAN THANH!")
    print(f"Ket qua duoc luu tai: {OUTPUT_DIR}")
    for r in summary:
        print(f"{r['scenario']:<12} | {r['strategy']:<22} | Cho TB: {r['average_wait_seconds']:.2f} giay")
    return summary

def summarize_results(detail, scenarios):
    rows=[]
    for sc in scenarios:
        for st in ("Co dinh", "Phan xa theo mat do"):
            chosen=[x for x in detail if x["scenario"]==sc.name and x["strategy"]==st]
            waits=[float(x["average_wait_seconds"]) for x in chosen]
            rows.append({"scenario":sc.name,"strategy":st,
                "average_wait_seconds":statistics.mean(waits),
                "std_wait_seconds":statistics.pstdev(waits),
                "average_queue":statistics.mean(float(x["average_queue"]) for x in chosen),
                "average_vehicles_remaining":statistics.mean(int(x["vehicles_remaining"]) for x in chosen),
                "replications":len(chosen),"wait_reduction_percent":0.0})
    for sc in scenarios:
        f=next(x for x in rows if x["scenario"]==sc.name and x["strategy"]=="Co dinh")
        a=next(x for x in rows if x["scenario"]==sc.name and x["strategy"]=="Phan xa theo mat do")
        a["wait_reduction_percent"]=(f["average_wait_seconds"]-a["average_wait_seconds"])/f["average_wait_seconds"]*100 if f["average_wait_seconds"] else 0
    return rows

def make_charts(rows, scenarios=SCENARIOS):
    if plt is None: return
    OUTPUT_DIR.mkdir(exist_ok=True)
    names=[s.name for s in scenarios]
    fixed=[next(r["average_wait_seconds"] for r in rows if r["scenario"]==n and r["strategy"]=="Co dinh") for n in names]
    adaptive=[next(r["average_wait_seconds"] for r in rows if r["scenario"]==n and r["strategy"]=="Phan xa theo mat do") for n in names]
    reductions=[next(r["wait_reduction_percent"] for r in rows if r["scenario"]==n and r["strategy"]=="Phan xa theo mat do") for n in names]
    x=list(range(len(names))); w=.36
    plt.figure(figsize=(9,5))
    plt.bar([i-w/2 for i in x],fixed,w,label="Co dinh")
    plt.bar([i+w/2 for i in x],adaptive,w,label="Phan xa theo mat do")
    plt.xticks(x,names); plt.ylabel("Thoi gian cho trung binh (giay/xe)")
    plt.xlabel("Muc luu luong"); plt.title("So sanh thoi gian cho trung binh")
    plt.legend(); plt.grid(axis="y",alpha=.25); plt.tight_layout()
    plt.savefig(OUTPUT_DIR/"so_sanh_thoi_gian_cho.png",dpi=180); plt.close()
    plt.figure(figsize=(9,5))
    bars=plt.bar(names,reductions); plt.axhline(0,linewidth=1)
    plt.ylabel("Muc giam thoi gian cho (%)"); plt.xlabel("Muc luu luong")
    plt.title("Ty le giam thoi gian cho cua tac tu phan xa"); plt.grid(axis="y",alpha=.25)
    for b,v in zip(bars,reductions):
        plt.text(b.get_x()+b.get_width()/2,v+(1 if v>=0 else -2),f"{v:.1f}%",ha="center",va="bottom" if v>=0 else "top")
    plt.tight_layout(); plt.savefig(OUTPUT_DIR/"ty_le_giam_thoi_gian_cho.png",dpi=180); plt.close()

def write_report(rows, config=CONFIG, scenarios=SCENARIOS):
    lines=["BAO CAO MO PHONG TAC TU DIEU KHIEN DEN GIAO THONG","="*55,
      f"Thoi gian mo phong moi lan: {config.simulation_seconds} giay",
      f"So lan lap moi muc: {config.replications}","Mo hinh xe den: phan phoi Poisson",
      "Chi so chinh: thoi gian cho trung binh cua moi xe",""]
    for sc in scenarios:
        f=next(r for r in rows if r["scenario"]==sc.name and r["strategy"]=="Co dinh")
        a=next(r for r in rows if r["scenario"]==sc.name and r["strategy"]=="Phan xa theo mat do")
        lines += [f"{sc.name}:","  Co dinh: %.2f giay"%f["average_wait_seconds"],
          "  Phan xa: %.2f giay"%a["average_wait_seconds"],
          "  Giam: %.2f%%"%a["wait_reduction_percent"],""]
    lines += ["Luu y: day la ket qua mo phong hoc tap, khong phai du lieu giao thong thuc te."]
    (OUTPUT_DIR/"bao_cao_tom_tat.txt").write_text("\n".join(lines),encoding="utf-8")

if __name__ == "__main__":
    run_experiments()
