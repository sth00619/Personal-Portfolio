"""실제 TLC 수요 분포를 사용하는 SimPy 동적 배차 정책 비교기."""

from __future__ import annotations

import math
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import simpy
from ortools.sat.python import cp_model
from scipy.stats import t

from src.demand import DemandProfile

PolicyName = Literal["fcfs", "nearest", "batch_bundle", "mip_batch"]
POLICIES: tuple[PolicyName, ...] = ("fcfs", "nearest", "batch_bundle", "mip_batch")
WARMUP_MINUTES = 60.0
MEASUREMENT_MINUTES = 240.0
DRAIN_MINUTES = 150.0
REALTIME_INTERVAL = 1.0
BATCH_INTERVAL = 5.0
MAX_WAIT_MINUTES = 30.0
BASE_ARRIVAL_RATE = 0.55
BUNDLE_RADIUS_MILES = 2.0
MAX_MIP_ORDERS = 60
MIP_SECONDS = 0.10
REPLICATIONS = 12
CONFIDENCE_LEVEL = 0.95
PRICE_CAP = 1.8
PRICE_STEP = 0.18
DEMAND_ELASTICITY = 0.35
SUPPLY_ELASTICITY = 0.50
RESERVE_SHARE = 0.50


@dataclass
class Order:
    """한 합성 배달 주문의 시공간 상태."""

    order_id: int
    created_at: float
    pickup: np.ndarray
    dropoff: np.ndarray
    direct_minutes: float
    price_multiplier: float
    assigned_at: float | None = None
    picked_up_at: float | None = None
    delivered_at: float | None = None
    expired: bool = False
    bundled: bool = False


@dataclass
class Rider:
    """라이더의 위치와 가동 상태."""

    rider_id: int
    location: np.ndarray
    active: bool
    reserve: bool
    busy: bool = False
    busy_minutes: float = 0.0
    distance_miles: float = 0.0


@dataclass(frozen=True)
class SimulationConfig:
    """정책·공급·가격 설정."""

    policy: PolicyName
    riders: int
    dynamic_price: bool = False
    seed: int = 42


@dataclass
class DispatchSimulation:
    """SimPy 환경에서 주문 도착과 배차·서비스를 실행한다."""

    profile: DemandProfile
    config: SimulationConfig
    env: simpy.Environment = field(init=False)
    random: np.random.Generator = field(init=False)
    orders: list[Order] = field(default_factory=list, init=False)
    waiting: list[Order] = field(default_factory=list, init=False)
    riders: list[Rider] = field(default_factory=list, init=False)
    price_multiplier: float = field(default=1.0, init=False)
    pressure_samples: list[float] = field(default_factory=list, init=False)
    price_samples: list[float] = field(default_factory=list, init=False)
    capacity_minutes: float = field(default=0.0, init=False)
    start_hour: int = field(init=False)

    def __post_init__(self) -> None:
        """난수·라이더·프로세스를 초기화한다."""
        self.env = simpy.Environment()
        self.random = np.random.default_rng(self.config.seed)
        self.start_hour = (int(np.argmax(self.profile.hour_counts)) - 2) % 24
        center = np.median(self.profile.pickup, axis=0)
        reserve_count = max(1, math.ceil(self.config.riders * RESERVE_SHARE))
        jitter = self.random.normal(0, 0.5, size=(self.config.riders + reserve_count, 2))
        self.riders = [
            Rider(index, center + jitter[index], index < self.config.riders, index >= self.config.riders)
            for index in range(self.config.riders + reserve_count)
        ]
        self.env.process(self._generate_orders())
        self.env.process(self._dispatch_loop())

    @property
    def generation_end(self) -> float:
        """주문 생성 종료 시각을 반환한다."""
        return WARMUP_MINUTES + MEASUREMENT_MINUTES

    def _natural_arrival_rate(self) -> float:
        """TLC 시간대 분포로 현재 포아송 도착률을 계산한다."""
        hour = (self.start_hour + int(self.env.now // 60)) % 24
        average = float(np.mean(self.profile.hour_counts))
        return BASE_ARRIVAL_RATE * float(self.profile.hour_counts[hour] / average)

    def _draw_trip(self) -> tuple[np.ndarray, np.ndarray, float]:
        """현재 시간대의 TLC 표본에서 하나의 OD와 이동시간을 추출한다."""
        hour = (self.start_hour + int(self.env.now // 60)) % 24
        candidates = np.flatnonzero(self.profile.pickup_hours == hour)
        if len(candidates) == 0:
            candidates = np.arange(len(self.profile.direct_minutes))
        index = int(self.random.choice(candidates))
        return self.profile.pickup[index].copy(), self.profile.dropoff[index].copy(), float(self.profile.direct_minutes[index])

    def _generate_orders(self) -> Generator[object, None, None]:
        """비정상 포아송 과정으로 합성 주문을 생성한다."""
        order_id = 0
        while self.env.now < self.generation_end:
            adjusted_rate = self._natural_arrival_rate() * self.price_multiplier ** (-DEMAND_ELASTICITY)
            wait = float(self.random.exponential(1.0 / max(adjusted_rate, 1e-6)))
            yield self.env.timeout(wait)
            if self.env.now >= self.generation_end:
                break
            pickup, dropoff, direct_minutes = self._draw_trip()
            order = Order(order_id, self.env.now, pickup, dropoff, direct_minutes, self.price_multiplier)
            self.orders.append(order)
            self.waiting.append(order)
            order_id += 1

    def _dispatch_loop(self) -> Generator[object, None, None]:
        """정책 주기에 맞춰 가격·공급 상태와 배차 결정을 갱신한다."""
        interval = BATCH_INTERVAL if self.config.policy in {"batch_bundle", "mip_batch"} else REALTIME_INTERVAL
        while self.env.now < self.generation_end + DRAIN_MINUTES:
            self._expire_orders()
            self._update_price_and_supply(interval)
            idle = [rider for rider in self.riders if rider.active and not rider.busy]
            available = [order for order in self.waiting if not order.expired and order.assigned_at is None]
            assignments = self._assign(idle, available)
            for rider, route in assignments:
                for order in route:
                    order.assigned_at = self.env.now
                    order.bundled = len(route) > 1
                    if order in self.waiting:
                        self.waiting.remove(order)
                rider.busy = True
                self.env.process(self._serve(rider, route))
            yield self.env.timeout(interval)

    def _expire_orders(self) -> None:
        """허용 대기시간을 넘은 미배차 주문을 만료한다."""
        for order in list(self.waiting):
            if self.env.now - order.created_at > MAX_WAIT_MINUTES:
                order.expired = True
                self.waiting.remove(order)

    def _update_price_and_supply(self, interval: float) -> None:
        """대기 주문/활성 공급 비율로 가격과 예비 라이더 유입을 갱신한다."""
        active = [rider for rider in self.riders if rider.active]
        idle = sum(not rider.busy for rider in active)
        pressure = len(self.waiting) / max(idle, 1)
        if self.config.dynamic_price:
            self.price_multiplier = float(np.clip(1.0 + PRICE_STEP * max(pressure - 1.0, 0.0), 1.0, PRICE_CAP))
            desired_reserve = math.ceil(self.config.riders * SUPPLY_ELASTICITY * (self.price_multiplier - 1.0))
            reserve = [rider for rider in self.riders if rider.reserve]
            for rank, rider in enumerate(reserve):
                if rank < desired_reserve:
                    rider.active = True
                elif not rider.busy:
                    rider.active = False
        else:
            self.price_multiplier = 1.0
        if WARMUP_MINUTES <= self.env.now < self.generation_end:
            current_active = sum(rider.active for rider in self.riders)
            measured_interval = min(interval, self.generation_end - self.env.now)
            self.capacity_minutes += current_active * measured_interval
            self.pressure_samples.append(pressure)
            self.price_samples.append(self.price_multiplier)

    def _assign(self, riders: list[Rider], orders: list[Order]) -> list[tuple[Rider, list[Order]]]:
        """설정된 정책으로 유휴 라이더와 대기 주문을 연결한다."""
        if not riders or not orders:
            return []
        if self.config.policy == "fcfs":
            ordered = sorted(orders, key=lambda order: order.created_at)
            return [(rider, [order]) for rider, order in zip(sorted(riders, key=lambda rider: rider.rider_id), ordered)]
        if self.config.policy == "nearest":
            return self._nearest_assignments(riders, orders)
        if self.config.policy == "batch_bundle":
            return self._bundle_assignments(riders, orders)
        return self._mip_assignments(riders, orders)

    def _nearest_assignments(self, riders: list[Rider], orders: list[Order]) -> list[tuple[Rider, list[Order]]]:
        """남은 모든 쌍 중 픽업 거리가 가장 짧은 연결을 반복한다."""
        remaining_riders = list(riders)
        remaining_orders = list(orders)
        assignments: list[tuple[Rider, list[Order]]] = []
        while remaining_riders and remaining_orders:
            _, rider_index, order_index = min(
                (float(np.linalg.norm(rider.location - order.pickup)), ri, oi)
                for ri, rider in enumerate(remaining_riders)
                for oi, order in enumerate(remaining_orders)
            )
            assignments.append((remaining_riders.pop(rider_index), [remaining_orders.pop(order_index)]))
        return assignments

    def _bundle_assignments(self, riders: list[Rider], orders: list[Order]) -> list[tuple[Rider, list[Order]]]:
        """가까운 픽업 두 개를 묶고 최근접 라이더에게 할당한다."""
        remaining = sorted(orders, key=lambda order: order.created_at)
        bundles: list[list[Order]] = []
        while remaining:
            first = remaining.pop(0)
            if remaining:
                distances = [float(np.linalg.norm(first.pickup - other.pickup)) for other in remaining]
                nearest_index = int(np.argmin(distances))
                if distances[nearest_index] <= BUNDLE_RADIUS_MILES:
                    bundles.append([first, remaining.pop(nearest_index)])
                    continue
            bundles.append([first])
        assignments: list[tuple[Rider, list[Order]]] = []
        remaining_riders = list(riders)
        while remaining_riders and bundles:
            _, rider_index, bundle_index = min(
                (float(np.linalg.norm(rider.location - bundle[0].pickup)), ri, bi)
                for ri, rider in enumerate(remaining_riders)
                for bi, bundle in enumerate(bundles)
            )
            assignments.append((remaining_riders.pop(rider_index), bundles.pop(bundle_index)))
        return assignments

    def _mip_assignments(self, riders: list[Rider], orders: list[Order]) -> list[tuple[Rider, list[Order]]]:
        """현재 배치의 픽업거리·대기 비용 최소 이분 매칭을 정확히 푼다."""
        candidates = sorted(orders, key=lambda order: order.created_at)[:MAX_MIP_ORDERS]
        model = cp_model.CpModel()
        variables = {
            (ri, oi): model.new_bool_var(f"x_{ri}_{oi}")
            for ri in range(len(riders))
            for oi in range(len(candidates))
        }
        for ri in range(len(riders)):
            model.add(sum(variables[ri, oi] for oi in range(len(candidates))) <= 1)
        for oi in range(len(candidates)):
            model.add(sum(variables[ri, oi] for ri in range(len(riders))) <= 1)
        match_count = min(len(riders), len(candidates))
        model.add(sum(variables.values()) == match_count)
        objective_terms = []
        for (ri, oi), variable in variables.items():
            pickup_cost = int(round(np.linalg.norm(riders[ri].location - candidates[oi].pickup) * 1_000))
            waiting_credit = int(round((self.env.now - candidates[oi].created_at) * 10))
            objective_terms.append((pickup_cost - waiting_credit) * variable)
        model.minimize(sum(objective_terms))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = MIP_SECONDS
        solver.parameters.num_search_workers = 1
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._nearest_assignments(riders, candidates)
        return [
            (riders[ri], [candidates[oi]])
            for (ri, oi), variable in variables.items()
            if solver.value(variable)
        ]

    def _travel_minutes(self, start: np.ndarray, end: np.ndarray) -> float:
        """Taxi Zone 대표점 직선거리를 관측 보정 이동시간으로 바꾼다."""
        return max(0.25, float(np.linalg.norm(start - end)) * self.profile.minutes_per_mile)

    def _serve(self, rider: Rider, route: list[Order]) -> Generator[object, None, None]:
        """한 건 또는 두 건 묶음의 픽업·배달 이벤트를 실행한다."""
        service_start = self.env.now
        current = rider.location.copy()
        for order in route:
            distance = float(np.linalg.norm(current - order.pickup))
            rider.distance_miles += distance
            yield self.env.timeout(self._travel_minutes(current, order.pickup))
            order.picked_up_at = self.env.now
            current = order.pickup

        deliveries = sorted(route, key=lambda order: np.linalg.norm(current - order.dropoff))
        for order in deliveries:
            distance = float(np.linalg.norm(current - order.dropoff))
            rider.distance_miles += distance
            if len(route) == 1:
                travel_minutes = order.direct_minutes
            else:
                travel_minutes = self._travel_minutes(current, order.dropoff)
            yield self.env.timeout(travel_minutes)
            order.delivered_at = self.env.now
            current = order.dropoff
        rider.location = current
        rider.busy = False
        overlap_start = max(service_start, WARMUP_MINUTES)
        overlap_end = min(self.env.now, self.generation_end)
        rider.busy_minutes += max(0.0, overlap_end - overlap_start)

    def run(self) -> dict[str, float | int | str | bool]:
        """시뮬레이션을 끝까지 실행하고 관측 구간 지표를 반환한다."""
        self.env.run(until=self.generation_end + DRAIN_MINUTES)
        measured = [order for order in self.orders if WARMUP_MINUTES <= order.created_at < self.generation_end]
        delivered = [order for order in measured if order.delivered_at is not None]
        delivery_times = np.asarray([order.delivered_at - order.created_at for order in delivered], dtype=float)
        pickup_waits = np.asarray([order.picked_up_at - order.created_at for order in delivered], dtype=float)
        busy_minutes = sum(rider.busy_minutes for rider in self.riders)
        return {
            "policy": self.config.policy,
            "riders": self.config.riders,
            "dynamic_price": self.config.dynamic_price,
            "seed": self.config.seed,
            "orders": len(measured),
            "completed": len(delivered),
            "mean_delivery_minutes": float(delivery_times.mean()) if len(delivery_times) else math.nan,
            "p90_delivery_minutes": float(np.quantile(delivery_times, 0.9)) if len(delivery_times) else math.nan,
            "mean_pickup_wait_minutes": float(pickup_waits.mean()) if len(pickup_waits) else math.nan,
            "utilization": busy_minutes / max(self.capacity_minutes, 1.0),
            "unassigned_rate": 1.0 - len(delivered) / max(len(measured), 1),
            "distance_miles": float(sum(rider.distance_miles for rider in self.riders)),
            "bundle_share": sum(order.bundled for order in delivered) / max(len(delivered), 1),
            "average_active_riders": self.capacity_minutes / MEASUREMENT_MINUTES,
            "mean_demand_supply_pressure": float(np.mean(self.pressure_samples)),
            "mean_price_multiplier": float(np.mean([order.price_multiplier for order in measured])) if measured else 1.0,
        }


def simulate(profile: DemandProfile, config: SimulationConfig) -> dict[str, float | int | str | bool]:
    """한 설정의 확률적 시뮬레이션을 실행한다."""
    return DispatchSimulation(profile, config).run()


def summarize_replications(records: list[dict[str, object]], group_keys: tuple[str, ...]) -> list[dict[str, object]]:
    """반복 실행을 그룹별 평균과 t 기반 95% 신뢰구간으로 요약한다."""
    metric_names = (
        "mean_delivery_minutes",
        "p90_delivery_minutes",
        "mean_pickup_wait_minutes",
        "utilization",
        "unassigned_rate",
        "distance_miles",
        "bundle_share",
        "average_active_riders",
        "mean_demand_supply_pressure",
        "mean_price_multiplier",
        "orders",
    )
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for record in records:
        key = tuple(record[name] for name in group_keys)
        groups.setdefault(key, []).append(record)
    summaries: list[dict[str, object]] = []
    for key, members in groups.items():
        summary: dict[str, object] = {name: value for name, value in zip(group_keys, key)}
        summary["replications"] = len(members)
        critical = float(t.ppf((1.0 + CONFIDENCE_LEVEL) / 2.0, len(members) - 1))
        for metric in metric_names:
            values = np.asarray([float(member[metric]) for member in members], dtype=float)
            half_width = critical * float(values.std(ddof=1)) / math.sqrt(len(values))
            summary[metric] = {
                "mean": float(values.mean()),
                "ci95_low": float(values.mean() - half_width),
                "ci95_high": float(values.mean() + half_width),
            }
        summaries.append(summary)
    return summaries
