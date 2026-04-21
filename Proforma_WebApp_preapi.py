import math
from itertools import product
from typing import Any, Dict

import numpy as np
import numpy_financial as nf
import pandas as pd


Scaling_Grocery_Rent = 0.1
Scaling_ParkPlaza_MRUAdd = 2.15
Scaling_Micro_MRUAdd = 0.5
Scaling_CommunityCenter_MRUAdd = 2.5
PREFERENCE_BONUS_STRENGTH = 3.5
PREFERENCE_PENALTY_STRENGTH = 1.25
PREFERENCE_EXPONENT = 2.0
HEIGHT_COST_STORY_START = 5.0
HEIGHT_COST_STORY_TARGET = 10.0
HEIGHT_COST_MAX_PREMIUM = 0.65

PROGRAM_INDEX = ["MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"]
SUMMARY_INDEX = ["Stories", "MRU Stories", "NPV", "IRR", "Likelihood of Construction"]
CHOICE_RANGES = {
    "Micro Units": list(range(0, 26, 5)),
    "Grocery Store": list(range(0, 4)),
    "Community Center": list(range(0, 2)),
    "Park/Plaza": list(range(0, 3)),
}


def rank_to_profit(rank: float) -> float:
    return 0.2 * (rank / 10.0) ** 2


def _preference_multiplier(rank: float) -> float:
    normalized_rank = min(max(rank, 1.0), 10.0)
    support = (normalized_rank - 1.0) / 9.0
    bonus = PREFERENCE_BONUS_STRENGTH * (support ** PREFERENCE_EXPONENT)
    penalty = PREFERENCE_PENALTY_STRENGTH * ((1.0 - support) ** PREFERENCE_EXPONENT)
    return bonus - penalty


def _diminishing_bonus(quantity: float) -> float:
    if quantity <= 0:
        return 0.0
    return math.log1p(quantity)


def _height_cost_multiplier(stories: float) -> float:
    if stories <= HEIGHT_COST_STORY_START:
        return 1.0
    scaled_height = (stories - HEIGHT_COST_STORY_START) / max(HEIGHT_COST_STORY_TARGET - HEIGHT_COST_STORY_START, 1.0)
    scaled_height = max(scaled_height, 0.0)
    premium = HEIGHT_COST_MAX_PREMIUM * (1.0 - math.exp(-(scaled_height ** 2)))
    return 1.0 + premium


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (np.floating, float, np.integer, int)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    return float(value)


def _format_metric(value: float | None, *, digits: int = 3, percent: bool = False, currency: bool = False) -> str:
    if value is None:
        return "n/a"
    if currency:
        return f"${value:,.0f}"
    if percent:
        return f"{value * 100:.2f}%"
    return f"{value:,.{digits}f}"


def _safe_irr(values: np.ndarray) -> float:
    irr_value = nf.irr(values)
    if irr_value is None or np.isnan(irr_value) or np.isinf(irr_value):
        return float("-inf")
    return float(irr_value)


def _build_noi_table(
    item_accounting_table: pd.DataFrame,
    *,
    item_type: str,
    soft_costs: float,
    rent_increase: float,
    upkeep_increase: float,
    exit_value_multiple: float,
    return_type: str = "NOI",
) -> pd.Series | pd.DataFrame:
    noi_table = np.zeros((3, 11), dtype=float)
    noi_table[2, 0] = item_accounting_table.loc[item_type, "Construction_cost"] * (1.0 + soft_costs)
    noi_table[0, 1] = item_accounting_table.loc[item_type, "Rent_yearly"]
    noi_table[1, 1] = item_accounting_table.loc[item_type, "Upkeep_yearly"]

    for period in range(2, 11):
        noi_table[0, period] = noi_table[0, period - 1] * (1.0 + rent_increase)
        noi_table[1, period] = noi_table[1, period - 1] * (1.0 + upkeep_increase)

    noi_table[0, 10] = noi_table[0, 10] * (exit_value_multiple + 1.0)

    for period in range(1, 11):
        noi_table[2, period] = noi_table[0, period] + noi_table[1, period]

    df = pd.DataFrame(noi_table, index=["Rent", "Upkeep", "NOI"], columns=range(11))
    if return_type in ("Rent", "Upkeep", "NOI"):
        return df.loc[return_type]
    return df


def _build_tradeoff_table(
    item_accounting_table: pd.DataFrame,
    mru_add_table: pd.DataFrame,
    *,
    item: str,
    min_units: int,
    max_units: int,
    step: int,
    soft_costs: float,
    rent_increase: float,
    upkeep_increase: float,
    discount_rate: float,
    exit_value_multiple: float,
    mru_count_initial: int,
    other_expenses: float,
    rent_series_by_item: Dict[str, pd.Series] | None = None,
    upkeep_series_by_item: Dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    cols = list(range(min_units, max_units, step))
    if 0 not in cols:
        cols = [0] + cols
    cols = sorted(cols)

    out = pd.DataFrame(0.0, index=["IRR", "NPV", "Costs"], columns=pd.Index(cols, dtype=int))

    for units in cols:
        selected_quantities = {
            "Micro Units": 0,
            "Grocery Store": 0,
            "Community Center": 0,
            "Park/Plaza": 0,
        }
        selected_quantities[item] = units
        candidate = _evaluate_candidate(
            item_accounting_table,
            mru_add_table,
            selected_quantities=selected_quantities,
            mru_count_initial=mru_count_initial,
            soft_costs=soft_costs,
            rent_increase=rent_increase,
            upkeep_increase=upkeep_increase,
            other_expenses=other_expenses,
            discount_rate=discount_rate,
            exit_value_multiple=exit_value_multiple,
            rent_series_by_item=rent_series_by_item,
            upkeep_series_by_item=upkeep_series_by_item,
        )
        out.at["IRR", units] = candidate["summary_table"]["friendly"]["IRR"] or 0.0
        out.at["NPV", units] = candidate["summary_table"]["friendly"]["NPV"] or 0.0
        out.at["Costs", units] = -candidate["initial_cost_abs"]

    return out


def _build_program_table(
    item_accounting_table: pd.DataFrame,
    mru_add_table: pd.DataFrame,
    *,
    selected_quantities: Dict[str, int],
    mru_count_initial: int,
) -> pd.DataFrame:
    final_build_table = pd.DataFrame({"Number": 0.0, "Size": 0.0}, index=PROGRAM_INDEX)
    final_build_table.loc["MRU", "Number"] = float(mru_count_initial)

    for amenity_name, amenity_count in selected_quantities.items():
        final_build_table.loc[amenity_name, "Number"] = float(amenity_count)
        if amenity_count > 0:
            final_build_table.loc["MRU", "Number"] += (
                mru_add_table.loc[amenity_name, "Extra MRU From Rankings"] * _diminishing_bonus(amenity_count)
            )

    final_build_table.loc["MRU", "Number"] = np.round(final_build_table.loc["MRU", "Number"])

    for idx in final_build_table.index:
        final_build_table.loc[idx, "Size"] = item_accounting_table.loc[idx, "Size"] * final_build_table.loc[idx, "Number"]

    return final_build_table


def _apply_height_costs(
    item_accounting_table: pd.DataFrame,
    final_build_table: pd.DataFrame,
    *,
    soft_costs: float,
) -> tuple[pd.DataFrame, float, float]:
    adjusted_accounting_table = item_accounting_table.copy()
    stories = float(np.ceil(final_build_table["Size"].sum() / max(item_accounting_table.loc["Land", "Size"], 1.0)))
    height_multiplier = _height_cost_multiplier(stories)
    if height_multiplier != 1.0:
        adjusted_accounting_table["Construction_cost"] = item_accounting_table["Construction_cost"] * height_multiplier
        adjusted_accounting_table["Soft_Costs"] = adjusted_accounting_table["Construction_cost"] * soft_costs
    return adjusted_accounting_table, stories, height_multiplier


def _build_financial_tables(
    item_accounting_table: pd.DataFrame,
    final_build_table: pd.DataFrame,
    *,
    soft_costs: float,
    rent_increase: float,
    upkeep_increase: float,
    other_expenses: float,
    discount_rate: float,
    exit_value_multiple: float,
    rent_series_by_item: Dict[str, pd.Series] | None = None,
    upkeep_series_by_item: Dict[str, pd.Series] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    adjusted_accounting_table, stories, height_multiplier = _apply_height_costs(
        item_accounting_table,
        final_build_table,
        soft_costs=soft_costs,
    )

    master_financial_table = pd.DataFrame(0.0, index=[
        "Revenue",
        "Upkeep",
        "Hard Costs",
        "Soft Costs",
        "Land Costs",
        "NOI",
        "Other Expenses",
        "Pre-Tax Cash Flow",
    ], columns=range(11))

    if rent_series_by_item is None:
        rent_series_by_item = {
            item: _build_noi_table(
                adjusted_accounting_table,
                item_type=item,
                soft_costs=soft_costs,
                rent_increase=rent_increase,
                upkeep_increase=upkeep_increase,
                exit_value_multiple=exit_value_multiple,
                return_type="Rent",
            )
            for item in final_build_table.index
        }
    if upkeep_series_by_item is None:
        upkeep_series_by_item = {
            item: _build_noi_table(
                adjusted_accounting_table,
                item_type=item,
                soft_costs=soft_costs,
                rent_increase=rent_increase,
                upkeep_increase=upkeep_increase,
                exit_value_multiple=exit_value_multiple,
                return_type="Upkeep",
            )
            for item in final_build_table.index
        }

    for item in final_build_table.index:
        rent_series = rent_series_by_item[item]
        upkeep_series = upkeep_series_by_item[item]
        master_financial_table.loc["Revenue"] += rent_series * final_build_table.loc[item, "Number"]
        master_financial_table.loc["Upkeep"] += upkeep_series * final_build_table.loc[item, "Number"]
        master_financial_table.loc["Hard Costs", 0] += (
            final_build_table.loc[item, "Number"] * adjusted_accounting_table.loc[item, "Construction_cost"]
        )

    master_financial_table.loc["Soft Costs", 0] = master_financial_table.loc["Hard Costs", 0] * soft_costs
    master_financial_table.loc["Land Costs", 0] = (
        adjusted_accounting_table.loc["Land", "Size"] * adjusted_accounting_table.loc["Land", "Construction_cost"]
    )

    for period in master_financial_table.columns:
        master_financial_table.loc["NOI", period] = master_financial_table.loc[
            ["Revenue", "Hard Costs", "Soft Costs", "Land Costs", "Upkeep"], period
        ].sum()
        master_financial_table.loc["Other Expenses", period] = other_expenses
        master_financial_table.loc["Pre-Tax Cash Flow", period] = (
            master_financial_table.loc["NOI", period] + master_financial_table.loc["Other Expenses", period]
        )

    pre_tax_cash_flow = master_financial_table.loc["Pre-Tax Cash Flow"].to_numpy(dtype=float)
    irr_value = _safe_irr(pre_tax_cash_flow)
    likelihood = 0.0 if irr_value == float("-inf") else 1.0 / (1.0 + np.e ** (-55.0 * (irr_value - 0.1)))

    final_display = pd.DataFrame(index=SUMMARY_INDEX, columns=["Value"], dtype=float)
    final_display.loc["Stories", "Value"] = stories
    final_display.loc["MRU Stories", "Value"] = (
        final_build_table.loc["MRU", "Size"] / max(item_accounting_table.loc["Land", "Size"], 1.0)
    )
    final_display.loc["NPV", "Value"] = nf.npv(discount_rate, pre_tax_cash_flow)
    final_display.loc["IRR", "Value"] = irr_value
    final_display.loc["Likelihood of Construction", "Value"] = likelihood

    return master_financial_table, final_display, height_multiplier


def _friendly_summary(final_display: pd.DataFrame) -> Dict[str, float | None]:
    return {
        idx: _coerce_float(final_display.at[idx, "Value"])
        for idx in final_display.index
    }


def _friendly_program(final_build_table: pd.DataFrame) -> list[Dict[str, float | str | None]]:
    return [
        {
            "name": idx,
            "Number": _coerce_float(final_build_table.at[idx, "Number"]),
            "Size": _coerce_float(final_build_table.at[idx, "Size"]),
        }
        for idx in final_build_table.index
    ]


def _candidate_sort_key(candidate: Dict[str, Any]) -> tuple[float, float, float, float, float]:
    summary = candidate["summary_table"]["friendly"]
    return (
        summary["NPV"] if summary["NPV"] is not None else float("-inf"),
        summary["IRR"] if summary["IRR"] is not None else float("-inf"),
        summary["Likelihood of Construction"] if summary["Likelihood of Construction"] is not None else float("-inf"),
        -candidate["initial_cost_abs"],
        -candidate["total_amenity_count"],
    )


def _evaluate_candidate(
    item_accounting_table: pd.DataFrame,
    mru_add_table: pd.DataFrame,
    *,
    selected_quantities: Dict[str, int],
    mru_count_initial: int,
    soft_costs: float,
    rent_increase: float,
    upkeep_increase: float,
    other_expenses: float,
    discount_rate: float,
    exit_value_multiple: float,
    rent_series_by_item: Dict[str, pd.Series] | None = None,
    upkeep_series_by_item: Dict[str, pd.Series] | None = None,
) -> Dict[str, Any]:
    final_build_table = _build_program_table(
        item_accounting_table,
        mru_add_table,
        selected_quantities=selected_quantities,
        mru_count_initial=mru_count_initial,
    )
    master_financial_table, final_display, height_multiplier = _build_financial_tables(
        item_accounting_table,
        final_build_table,
        soft_costs=soft_costs,
        rent_increase=rent_increase,
        upkeep_increase=upkeep_increase,
        other_expenses=other_expenses,
        discount_rate=discount_rate,
        exit_value_multiple=exit_value_multiple,
        rent_series_by_item=rent_series_by_item,
        upkeep_series_by_item=upkeep_series_by_item,
    )

    initial_cost_abs = abs(float(
        master_financial_table.loc["Hard Costs", 0]
        + master_financial_table.loc["Soft Costs", 0]
        + master_financial_table.loc["Land Costs", 0]
    ))

    return {
        "selected_quantities": selected_quantities,
        "summary_table": {"friendly": _friendly_summary(final_display)},
        "program_table": {"friendly": _friendly_program(final_build_table)},
        "final_build_table": final_build_table,
        "master_financial_table": master_financial_table,
        "final_display": final_display,
        "initial_cost_abs": initial_cost_abs,
        "total_amenity_count": float(sum(selected_quantities.values())),
        "height_cost_multiplier": height_multiplier,
    }


def _build_reason(winner: Dict[str, Any], runner_up: Dict[str, Any] | None) -> str:
    selected = winner["selected_quantities"]
    summary = winner["summary_table"]["friendly"]
    parts = [
        "Selected the deterministic best program by maximizing NPV first, then IRR, then likelihood of construction."
    ]
    parts.append(
        "Chosen mix: "
        f"{selected['Micro Units']} micro units, "
        f"{selected['Grocery Store']} grocery stores, "
        f"{selected['Community Center']} community centers, "
        f"and {selected['Park/Plaza']} park/plaza contributions."
    )
    parts.append(
        "Winner metrics: "
        f"NPV {_format_metric(summary['NPV'], currency=True)}, "
        f"IRR {_format_metric(summary['IRR'], percent=True)}, "
        f"likelihood {_format_metric(summary['Likelihood of Construction'], percent=True)}."
    )
    parts.append(
        f"Height-adjusted construction multiplier: {winner['height_cost_multiplier']:.2f}x."
    )
    if runner_up is not None:
        runner_summary = runner_up["summary_table"]["friendly"]
        parts.append(
            "Top alternative: "
            f"NPV {_format_metric(runner_summary['NPV'], currency=True)}, "
            f"IRR {_format_metric(runner_summary['IRR'], percent=True)}, "
            f"likelihood {_format_metric(runner_summary['Likelihood of Construction'], percent=True)}."
        )
    return " ".join(parts)


def _top_candidate_snapshot(candidate: Dict[str, Any]) -> Dict[str, Any]:
    summary = candidate["summary_table"]["friendly"]
    return {
        "selected_quantities": dict(candidate["selected_quantities"]),
        "summary": {
            "NPV": summary["NPV"],
            "IRR": summary["IRR"],
            "Likelihood of Construction": summary["Likelihood of Construction"],
            "Stories": summary["Stories"],
        },
        "height_cost_multiplier": candidate["height_cost_multiplier"],
        "initial_cost_abs": candidate["initial_cost_abs"],
        "total_amenity_count": candidate["total_amenity_count"],
    }


def compute_developer_decision(
    *,
    ranking_Housing_Micro: float = 5,
    ranking_InBuilding_Grocery: float = 5,
    ranking_InBuilding_CommunityCenter: float = 5,
    ranking_OffSite_ParkPlaza: float = 5,
    MRU_count_initial: int = 48,
    soft_costs: float = 0.22,
    Rent_increase: float = 0.10,
    Upkeep_increase: float = 0.04,
    Other_expenses: float = -500,
    Discount_rate: float = 0.08,
    Market_rent_sqft: float = 4,
    Exit_value_multiple: float = 20,
    city_for_prompt: str = "San Francisco",
    diagnostics_limit: int = 5,
) -> Dict[str, Any]:
    base_results = compute_proforma(
        ranking_Housing_Micro=ranking_Housing_Micro,
        ranking_InBuilding_Grocery=ranking_InBuilding_Grocery,
        ranking_InBuilding_CommunityCenter=ranking_InBuilding_CommunityCenter,
        ranking_OffSite_ParkPlaza=ranking_OffSite_ParkPlaza,
        MRU_count_initial=MRU_count_initial,
        soft_costs=soft_costs,
        Rent_increase=Rent_increase,
        Upkeep_increase=Upkeep_increase,
        Other_expenses=Other_expenses,
        Discount_rate=Discount_rate,
        Market_rent_sqft=Market_rent_sqft,
        Exit_value_multiple=Exit_value_multiple,
        city_for_prompt=city_for_prompt,
    )

    item_accounting_table = base_results["Item_Accounting_table"]
    mru_add_table = base_results["MRU_Add_Table"]
    candidates: list[Dict[str, Any]] = []

    for micro_units, grocery, community, park in product(
        CHOICE_RANGES["Micro Units"],
        CHOICE_RANGES["Grocery Store"],
        CHOICE_RANGES["Community Center"],
        CHOICE_RANGES["Park/Plaza"],
    ):
        selected_quantities = {
            "Micro Units": micro_units,
            "Grocery Store": grocery,
            "Community Center": community,
            "Park/Plaza": park,
        }
        candidate = _evaluate_candidate(
            item_accounting_table,
            mru_add_table,
            selected_quantities=selected_quantities,
            mru_count_initial=MRU_count_initial,
            soft_costs=soft_costs,
            rent_increase=Rent_increase,
            upkeep_increase=Upkeep_increase,
            other_expenses=Other_expenses,
            discount_rate=Discount_rate,
            exit_value_multiple=Exit_value_multiple,
        )
        candidates.append(candidate)

    ranked_candidates = sorted(candidates, key=_candidate_sort_key, reverse=True)
    winner = ranked_candidates[0]
    runner_up = ranked_candidates[1] if len(ranked_candidates) > 1 else None

    return {
        "summary_table": winner["summary_table"],
        "program_table": winner["program_table"],
        "reason": _build_reason(winner, runner_up),
        "selected_quantities": dict(winner["selected_quantities"]),
        "diagnostics": {
            "top_candidates": [_top_candidate_snapshot(candidate) for candidate in ranked_candidates[:diagnostics_limit]],
            "objective": "NPV desc, IRR desc, Likelihood desc, initial cost asc, amenity count asc",
            "evaluated_combinations": len(ranked_candidates),
        },
        "intermediate_tables": {
            "final_build_table": winner["final_build_table"],
            "master_financial_table": winner["master_financial_table"],
            "final_display": winner["final_display"],
        },
        "proforma_results": base_results,
    }


def compute_proforma(
    *,
    # Sliders (rankings)
    ranking_Housing_Micro: float = 5,
    ranking_InBuilding_Grocery: float = 5,
    ranking_InBuilding_CommunityCenter: float = 5,
    ranking_OffSite_ParkPlaza: float = 5,
    # Assorted parameters
    MRU_count_initial: int = 48,
    soft_costs: float = 0.22,
    Rent_increase: float = 0.10,
    Upkeep_increase: float = 0.04,
    Other_expenses: float = -500,   # kept for parity (unused in original script)
    Discount_rate: float = 0.08,
    Market_rent_sqft: float = 4,    # kept for parity (unused in original script)
    Exit_value_multiple: float = 20,
    # City for the GPT prompt
    city_for_prompt: str = "San Francisco",
) -> Dict[str, Any]:
    """
    Computes the pro forma based on slider rankings and returns:
      - 'prompt': str
      - 'GPTOutputTable_Housing_Micro': DataFrame
      - 'GPTOutputTable_InBuilding_Grocery': DataFrame
      - 'GPTOutputTable_InBuilding_CommunityCenter': DataFrame
      - 'GPTOutputTable_OffSite_ParkPlaza': DataFrame
      - 'Item_Accounting_table': DataFrame (intermediate)
      - 'Input_table': DataFrame (intermediate)
      - 'MRU_Add_Table': DataFrame (intermediate)
    """

    # ---- Item Accounting (ensure float dtypes to avoid FutureWarning) ----
    Item_Accounting_table = pd.DataFrame(
        {
            "Size":            [9000,   750,   300,   7500,   20000,     0],
            "Rent_yearly":     [0,   36000,  7200, 300000,       0,     0],
            "Construction_cost":[-900, -375000, -150000, -2750000, -10000000, -4500000],
            "Soft_Costs":      [0,        0,     0,       0,        0,     0],
            "Upkeep_yearly":   [0,    -6000, -2400,  -82500,  -472000, -125000],
            "MRU_add_per_unit":[0,        0,     0,       0,        0,     0],
        },
        index=["Land", "MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"],
        dtype=float,  # <- critical: make everything float-friendly
    )

    # compute soft costs as float
    Item_Accounting_table["Soft_Costs"] = Item_Accounting_table["Construction_cost"] * soft_costs
    Item_Accounting_table.loc["Grocery Store", "Rent_yearly"] = Item_Accounting_table.loc["Grocery Store", "Rent_yearly"]*Scaling_Grocery_Rent





    # ---- Input Table (explicit dtypes per column to avoid int->float assignments) ----
    Input_table = pd.DataFrame(
        {
            "Units/Rank": [float(MRU_count_initial),
                           float(ranking_Housing_Micro),
                           float(ranking_InBuilding_Grocery),
                           float(ranking_InBuilding_CommunityCenter),
                           float(ranking_OffSite_ParkPlaza)],
            "Net Profit/Year/SqFt": [0.0, 0.0, 0.0, 0.0, 0.0],
            "MRU_Add": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=["MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"],
    )

    # fill Net Profit/Year/SqFt safely as float
    for idx in ["MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"]:
        size = Item_Accounting_table.loc[idx, "Size"]
        if size != 0:
            Input_table.loc[idx, "Net Profit/Year/SqFt"] = (
                (Item_Accounting_table.loc[idx, "Rent_yearly"] + Item_Accounting_table.loc[idx, "Upkeep_yearly"]) / float(size)
            )
        else:
            Input_table.loc[idx, "Net Profit/Year/SqFt"] = 0.0

    # ---- MRU Add Table (floats throughout) ----
    MRU_Add_Table = pd.DataFrame(
        0.0,
        index=Input_table.index,
        columns=["NPV/SqFt", "MRU Break Even", "Scaled for Size", "Extra MRU From Rankings"],
        dtype=float,
    )

    # Precompute NOI series we need multiple times
    NOI_by_item = {
        name: _build_noi_table(
            Item_Accounting_table,
            item_type=name,
            soft_costs=soft_costs,
            rent_increase=Rent_increase,
            upkeep_increase=Upkeep_increase,
            exit_value_multiple=Exit_value_multiple,
            return_type="NOI",
        )
        for name in Item_Accounting_table.index if name != "Land"
    }

    # NPV per sqft for items with size
    for idx in MRU_Add_Table.index:
        size = Item_Accounting_table.loc[idx, "Size"]
        if size != 0:
            MRU_Add_Table.loc[idx, "NPV/SqFt"] = nf.npv(Discount_rate, NOI_by_item[idx].to_numpy(dtype=float)) / float(size)
        else:
            MRU_Add_Table.loc[idx, "NPV/SqFt"] = 0.0

    # Fill the remaining columns
    # First, ensure MRU's row stays zeros for the three derived columns
    MRU_Add_Table.loc["MRU", ["MRU Break Even", "Scaled for Size", "Extra MRU From Rankings"]] = 0.0

    # For in-building items with size
    for idx in ["Micro Units", "Grocery Store", "Community Center"]:
        # Break-even in MRU terms, per sqft
        mru_npv_sqft = MRU_Add_Table.loc["MRU", "NPV/SqFt"]
        item_npv_sqft = MRU_Add_Table.loc[idx, "NPV/SqFt"]
        # Guard against divide-by-zero if MRU NPV/SqFt happens to be 0
        if mru_npv_sqft == 0:
            MRU_be = 0.0
        else:
            MRU_be = (mru_npv_sqft - item_npv_sqft) / mru_npv_sqft
        MRU_Add_Table.loc[idx, "MRU Break Even"] = MRU_be

        MRU_Add_Table.loc[idx, "Scaled for Size"] = MRU_be * (
            Item_Accounting_table.loc[idx, "Size"] / max(Item_Accounting_table.loc["MRU", "Size"], 1.0)
        )
        MRU_Add_Table.loc[idx, "Extra MRU From Rankings"] = MRU_Add_Table.loc[idx, "Scaled for Size"] * (
            _preference_multiplier(Input_table.loc[idx, "Units/Rank"])
        )

    # For off-site (size == 0) items, do absolute NPV comparison
    for idx in ["Park/Plaza"]:
        mru_npv_abs = nf.npv(Discount_rate, NOI_by_item["MRU"].to_numpy(dtype=float))
        item_npv_abs = nf.npv(Discount_rate, NOI_by_item[idx].to_numpy(dtype=float))
        if mru_npv_abs == 0:
            MRU_be_abs = 0.0
        else:
            MRU_be_abs = (mru_npv_abs - item_npv_abs) / mru_npv_abs
        MRU_Add_Table.loc[idx, "MRU Break Even"] = MRU_be_abs
        MRU_Add_Table.loc[idx, "Scaled for Size"] = MRU_be_abs
        MRU_Add_Table.loc[idx, "Extra MRU From Rankings"] = MRU_be_abs * (
            _preference_multiplier(Input_table.loc[idx, "Units/Rank"])
        )
    MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] * Scaling_ParkPlaza_MRUAdd
    MRU_Add_Table.loc["Micro Units", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Micro Units", "Extra MRU From Rankings"] * Scaling_Micro_MRUAdd
    MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] * Scaling_CommunityCenter_MRUAdd

    # Update Item_Accounting_table with float-compatible column (no warnings)
    Item_Accounting_table["MRU_add_per_unit"] = MRU_Add_Table["Extra MRU From Rankings"].astype(float)

    # ---- Build GPT output tables ----
    GPTOutputTable_Prompt = (
        f"You are a real estate developer in {city_for_prompt}. In addition to what you already have approved by the city, "
        "you can add the following community amenities (micro-unit housing, grocery store, community center, or funding for an off-site plaza), "
        "with the quantities and resulting IRR, NPV, and initial costs in the charts below. With this information, return a 2-row 1-column DataFrame "
        "of how many of each amenity you would build. The index should be labeled 'Micro Units', 'Grocery Store', 'Community Center', and 'Park/Plaza', "
        "and the only column should list how many of each amenity you decide to build. The column should remain unnamed."
    )

    GPTOutputTable_Housing_Micro = _build_tradeoff_table(
        Item_Accounting_table,
        MRU_Add_Table,
        item="Micro Units",
        min_units=0,
        max_units=30,
        step=5,
        soft_costs=soft_costs,
        rent_increase=Rent_increase,
        upkeep_increase=Upkeep_increase,
        discount_rate=Discount_rate,
        exit_value_multiple=Exit_value_multiple,
        mru_count_initial=MRU_count_initial,
        other_expenses=Other_expenses,
    )
    GPTOutputTable_InBuilding_Grocery = _build_tradeoff_table(
        Item_Accounting_table,
        MRU_Add_Table,
        item="Grocery Store",
        min_units=0,
        max_units=4,
        step=1,
        soft_costs=soft_costs,
        rent_increase=Rent_increase,
        upkeep_increase=Upkeep_increase,
        discount_rate=Discount_rate,
        exit_value_multiple=Exit_value_multiple,
        mru_count_initial=MRU_count_initial,
        other_expenses=Other_expenses,
    )
    GPTOutputTable_InBuilding_CommunityCenter = _build_tradeoff_table(
        Item_Accounting_table,
        MRU_Add_Table,
        item="Community Center",
        min_units=0,
        max_units=2,
        step=1,
        soft_costs=soft_costs,
        rent_increase=Rent_increase,
        upkeep_increase=Upkeep_increase,
        discount_rate=Discount_rate,
        exit_value_multiple=Exit_value_multiple,
        mru_count_initial=MRU_count_initial,
        other_expenses=Other_expenses,
    )
    GPTOutputTable_OffSite_ParkPlaza = _build_tradeoff_table(
        Item_Accounting_table,
        MRU_Add_Table,
        item="Park/Plaza",
        min_units=0,
        max_units=3,
        step=1,
        soft_costs=soft_costs,
        rent_increase=Rent_increase,
        upkeep_increase=Upkeep_increase,
        discount_rate=Discount_rate,
        exit_value_multiple=Exit_value_multiple,
        mru_count_initial=MRU_count_initial,
        other_expenses=Other_expenses,
    )

    return {
        "prompt": GPTOutputTable_Prompt,
        "GPTOutputTable_Housing_Micro": GPTOutputTable_Housing_Micro,
        "GPTOutputTable_InBuilding_Grocery": GPTOutputTable_InBuilding_Grocery,
        "GPTOutputTable_InBuilding_CommunityCenter": GPTOutputTable_InBuilding_CommunityCenter,
        "GPTOutputTable_OffSite_ParkPlaza": GPTOutputTable_OffSite_ParkPlaza,
        # helpful intermediates
        "Item_Accounting_table": Item_Accounting_table,
        "Input_table": Input_table,
        "MRU_Add_Table": MRU_Add_Table,
    }
