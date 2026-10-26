"""Protect resumed full-split runs with a persistent conservative spend cap."""

import asyncio

import pytest
from pytest import approx

from src.llm import BudgetExceededError, CostBudget


def test_budget_persists_reservations_and_blocks_before_overrun(tmp_path) -> None:
    """A second request is rejected when its upper-bound reserve exceeds the cap."""
    ledger_path = tmp_path / "budget.json"
    budget = CostBudget(ledger_path, "gpt-6-luna", 0.00015)

    async def reserve_twice() -> None:
        await budget.reserve("system", "question", 96)
        with pytest.raises(BudgetExceededError, match="above local cap"):
            await budget.reserve("system", "question", 96)

    asyncio.run(reserve_twice())
    resumed = CostBudget(ledger_path, "gpt-6-luna", 0.00015)
    assert resumed.reserved_usd == approx(budget.reserved_usd)
