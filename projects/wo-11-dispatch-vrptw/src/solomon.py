"""Solomon VRPTW 인스턴스 파싱, 탐욕 기준선, OR-Tools 탐색을 제공한다."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

DISTANCE_SCALE = 100
VEHICLE_FIXED_COST = 10_000_000
DEFAULT_SEARCH_SECONDS = 5
BENCHMARK_BEST: dict[str, tuple[int, float]] = {
    "c101": (10, 828.94),
    "c104": (10, 824.78),
    "c107": (10, 828.94),
}


@dataclass(frozen=True)
class SolomonInstance:
    """한 Solomon VRPTW 문제의 차량·고객·시간창 자료."""

    name: str
    vehicle_count: int
    capacity: int
    customer_ids: np.ndarray
    coordinates: np.ndarray
    demands: np.ndarray
    ready_times: np.ndarray
    due_times: np.ndarray
    service_times: np.ndarray


@dataclass(frozen=True)
class RouteSolution:
    """경로 집합과 이중 정밀도 거리 및 실행 가능성."""

    routes: list[list[int]]
    distance: float
    route_time: float
    feasible: bool
    unserved: int

    @property
    def vehicles(self) -> int:
        """고객을 한 명 이상 방문한 차량 수를 반환한다."""
        return sum(len(route) > 2 for route in self.routes)


def locate_instance(root: Path, name: str) -> Path:
    """압축 해제 구조와 대소문자에 무관하게 인스턴스 파일을 찾는다."""
    matches = [path for path in root.rglob("*") if path.is_file() and path.stem.lower() == name.lower()]
    if len(matches) != 1:
        raise FileNotFoundError(f"{name} 인스턴스 파일을 하나로 찾지 못했습니다: {matches}")
    return matches[0]


def load_instance(path: Path) -> SolomonInstance:
    """Solomon 텍스트 형식을 데이터 클래스로 변환한다."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    name = next((line.strip().lower() for line in lines if line.strip()), path.stem.lower())
    vehicle_index = next(index for index, line in enumerate(lines) if "NUMBER" in line.upper() and "CAPACITY" in line.upper())
    vehicle_values = [int(value) for value in re.findall(r"\d+", lines[vehicle_index + 1])]
    if len(vehicle_values) < 2:
        raise ValueError(f"차량 정보를 읽을 수 없습니다: {path}")
    customer_index = next(index for index, line in enumerate(lines) if "CUST NO" in line.upper())
    rows: list[list[int]] = []
    for line in lines[customer_index + 1 :]:
        values = [int(value) for value in re.findall(r"-?\d+", line)]
        if len(values) >= 7:
            rows.append(values[:7])
    if len(rows) != 101:
        raise ValueError(f"100-customer 인스턴스가 아닙니다: {path} ({len(rows) - 1} customers)")
    matrix = np.asarray(rows, dtype=np.int64)
    return SolomonInstance(
        name=name,
        vehicle_count=vehicle_values[0],
        capacity=vehicle_values[1],
        customer_ids=matrix[:, 0],
        coordinates=matrix[:, 1:3].astype(np.float64),
        demands=matrix[:, 3],
        ready_times=matrix[:, 4],
        due_times=matrix[:, 5],
        service_times=matrix[:, 6],
    )


def distance_matrix(instance: SolomonInstance) -> np.ndarray:
    """좌표의 이중 정밀도 유클리드 거리 행렬을 계산한다."""
    delta = instance.coordinates[:, None, :] - instance.coordinates[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def validate_routes(instance: SolomonInstance, routes: list[list[int]]) -> tuple[bool, int]:
    """용량·시간창·중복 방문과 전체 고객 방문 여부를 검증한다."""
    distances = distance_matrix(instance)
    visited: list[int] = []
    valid = True
    for route in routes:
        if len(route) < 2 or route[0] != 0 or route[-1] != 0:
            valid = False
            continue
        load = 0
        current_time = float(instance.ready_times[0])
        for previous, node in zip(route, route[1:]):
            arrival = current_time + distances[previous, node]
            start = max(arrival, float(instance.ready_times[node]))
            if start > instance.due_times[node] + 1e-7:
                valid = False
            if node != 0:
                visited.append(node)
                load += int(instance.demands[node])
            current_time = start + float(instance.service_times[node])
        if load > instance.capacity:
            valid = False
    unserved = len(set(range(1, len(instance.customer_ids))) - set(visited))
    if len(visited) != len(set(visited)) or unserved:
        valid = False
    return valid, unserved


def route_distance(instance: SolomonInstance, routes: list[list[int]]) -> float:
    """벤치마크 규약에 따라 이중 정밀도 총 이동거리를 계산한다."""
    distances = distance_matrix(instance)
    return float(sum(distances[a, b] for route in routes for a, b in zip(route, route[1:])))


def total_route_time(instance: SolomonInstance, routes: list[list[int]]) -> float:
    """이동·대기·서비스를 포함한 모든 차량의 경로 시간을 합산한다."""
    distances = distance_matrix(instance)
    total = 0.0
    for route in routes:
        current_time = float(instance.ready_times[0])
        start_time = current_time
        for previous, node in zip(route, route[1:]):
            arrival = current_time + distances[previous, node]
            service_start = max(arrival, float(instance.ready_times[node]))
            current_time = service_start + float(instance.service_times[node])
        total += current_time - start_time
    return total


def greedy_nearest(instance: SolomonInstance) -> RouteSolution:
    """가장 가까운 실행 가능 고객을 이어 붙이는 기준선을 푼다."""
    distances = distance_matrix(instance)
    remaining = set(range(1, len(instance.customer_ids)))
    routes: list[list[int]] = []
    while remaining and len(routes) < instance.vehicle_count:
        route = [0]
        current = 0
        current_time = float(instance.ready_times[0])
        load = 0
        while remaining:
            feasible: list[tuple[float, float, int]] = []
            for customer in remaining:
                new_load = load + int(instance.demands[customer])
                arrival = current_time + distances[current, customer]
                start = max(arrival, float(instance.ready_times[customer]))
                departure = start + float(instance.service_times[customer])
                returns_in_time = departure + distances[customer, 0] <= instance.due_times[0] + 1e-7
                if new_load <= instance.capacity and start <= instance.due_times[customer] + 1e-7 and returns_in_time:
                    feasible.append((distances[current, customer], start, customer))
            if not feasible:
                break
            _, start, chosen = min(feasible)
            route.append(chosen)
            remaining.remove(chosen)
            load += int(instance.demands[chosen])
            current_time = start + float(instance.service_times[chosen])
            current = chosen
        route.append(0)
        routes.append(route)
    valid, unserved = validate_routes(instance, routes)
    return RouteSolution(routes, route_distance(instance, routes), total_route_time(instance, routes), valid, unserved)


def solve_ortools(instance: SolomonInstance, vehicles: int, search_seconds: int = DEFAULT_SEARCH_SECONDS) -> RouteSolution:
    """차량 수를 고정하고 Guided Local Search로 VRPTW 경로를 탐색한다."""
    distances = distance_matrix(instance)
    scaled_distance = np.rint(distances * DISTANCE_SCALE).astype(np.int64)
    service = instance.service_times * DISTANCE_SCALE
    manager = pywrapcp.RoutingIndexManager(len(instance.customer_ids), vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        """RoutingModel 인덱스를 정수 거리 비용으로 변환한다."""
        return int(scaled_distance[manager.IndexToNode(from_index), manager.IndexToNode(to_index)])

    distance_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
    routing.SetFixedCostOfAllVehicles(VEHICLE_FIXED_COST)

    def time_callback(from_index: int, to_index: int) -> int:
        """출발 노드 서비스와 이동을 포함한 정수 시간 비용을 반환한다."""
        source = manager.IndexToNode(from_index)
        target = manager.IndexToNode(to_index)
        return int(service[source] + scaled_distance[source, target])

    time_index = routing.RegisterTransitCallback(time_callback)
    horizon = int(instance.due_times[0] * DISTANCE_SCALE)
    routing.AddDimension(time_index, horizon, horizon, False, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")
    for node in range(len(instance.customer_ids)):
        index = manager.NodeToIndex(node)
        time_dimension.CumulVar(index).SetRange(
            int(instance.ready_times[node] * DISTANCE_SCALE),
            int(instance.due_times[node] * DISTANCE_SCALE),
        )
    for vehicle in range(vehicles):
        time_dimension.CumulVar(routing.Start(vehicle)).SetRange(
            int(instance.ready_times[0] * DISTANCE_SCALE), int(instance.due_times[0] * DISTANCE_SCALE)
        )
        time_dimension.CumulVar(routing.End(vehicle)).SetRange(
            int(instance.ready_times[0] * DISTANCE_SCALE), int(instance.due_times[0] * DISTANCE_SCALE)
        )

    def demand_callback(index: int) -> int:
        """노드별 정수 수요를 반환한다."""
        return int(instance.demands[manager.IndexToNode(index)])

    demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_index, 0, [instance.capacity] * vehicles, True, "Capacity")

    assignment = None
    strategies = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION,
        routing_enums_pb2.FirstSolutionStrategy.LOCAL_CHEAPEST_INSERTION,
        routing_enums_pb2.FirstSolutionStrategy.SAVINGS,
        routing_enums_pb2.FirstSolutionStrategy.PATH_MOST_CONSTRAINED_ARC,
    )
    for strategy in strategies:
        parameters = pywrapcp.DefaultRoutingSearchParameters()
        parameters.first_solution_strategy = strategy
        parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        parameters.time_limit.seconds = search_seconds
        parameters.log_search = False
        assignment = routing.SolveWithParameters(parameters)
        if assignment is not None:
            break
    if assignment is None:
        return RouteSolution([], math.inf, math.inf, False, len(instance.customer_ids) - 1)

    routes: list[list[int]] = []
    for vehicle in range(vehicles):
        index = routing.Start(vehicle)
        route = [0]
        while not routing.IsEnd(index):
            index = assignment.Value(routing.NextVar(index))
            route.append(manager.IndexToNode(index))
        if len(route) > 2:
            routes.append(route)
    valid, unserved = validate_routes(instance, routes)
    return RouteSolution(routes, route_distance(instance, routes), total_route_time(instance, routes), valid, unserved)


def benchmark_record(instance: SolomonInstance, greedy: RouteSolution, optimized: RouteSolution) -> dict[str, object]:
    """알려진 최선 거리와 두 해법의 차량 수·거리 gap을 정리한다."""
    best_vehicles, best_distance = BENCHMARK_BEST[instance.name]

    def summary(solution: RouteSolution) -> dict[str, object]:
        """한 해의 검증 결과와 거리를 직렬화한다."""
        return {
            "vehicles": solution.vehicles,
            "vehicle_gap": solution.vehicles - best_vehicles,
            "distance": solution.distance,
            "distance_gap_percent": max(0.0, 100.0 * (solution.distance - best_distance) / best_distance),
            "total_route_time": solution.route_time,
            "feasible": solution.feasible,
            "unserved": solution.unserved,
        }

    return {
        "instance": instance.name,
        "customers": len(instance.customer_ids) - 1,
        "best_known": {"vehicles": best_vehicles, "distance": best_distance},
        "greedy": summary(greedy),
        "ortools": summary(optimized),
    }
