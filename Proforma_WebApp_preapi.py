import numpy as np
import pandas as pd
import numpy_financial as nf
from typing import Dict, Any


Scaling_Grocery_Rent = 0.1
Scaling_ParkPlaza_MRUAdd = 2.15
Scaling_Micro_MRUAdd = 0.5
Scaling_CommunityCenter_MRUAdd = 0.75


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

    # ---- helpers ----
    def rank_to_profit(rank: float) -> float:
        return 0.2 * (rank / 10.0) ** 2

    # NOI table builder (returns a Series or full table depending on return_type)
    def NOI_table_builder(item_type: str, return_type: str = "NOI") -> pd.Series | pd.DataFrame:
        # 3 rows (Rent, Upkeep, NOI) x 11 years (year 0..10)
        NoiTable = np.zeros((3, 11), dtype=float)
        # Year 0: capex (construction + soft costs) goes into NOI row
        NoiTable[2, 0] = Item_Accounting_table.loc[item_type, "Construction_cost"] * (1.0 + soft_costs)
        # Year 1 base values
        NoiTable[0, 1] = Item_Accounting_table.loc[item_type, "Rent_yearly"]
        NoiTable[1, 1] = Item_Accounting_table.loc[item_type, "Upkeep_yearly"]

        # Grow rent & upkeep years 2..10
        for t in range(2, 11):
            NoiTable[0, t] = NoiTable[0, t - 1] * (1.0 + Rent_increase)
            NoiTable[1, t] = NoiTable[1, t - 1] * (1.0 + Upkeep_increase)

        # Add exit value at year 10 to the rent stream
        NoiTable[0, 10] = NoiTable[0, 10] * (Exit_value_multiple + 1.0)

        # NOI row is rent + upkeep (note upkeep is negative in your inputs)
        for t in range(1, 11):
            NoiTable[2, t] = NoiTable[0, t] + NoiTable[1, t]

        df = pd.DataFrame(NoiTable, index=["Rent", "Upkeep", "NOI"], columns=range(11))
        if return_type in ("Rent", "Upkeep", "NOI"):
            return df.loc[return_type]
        return df

    def GPTOutputTable_Builder(min_units: int, max_units: int, step: int, item: str) -> pd.DataFrame:
        cols = list(range(min_units, max_units, step))
        if 0 not in cols:
            cols = [0] + cols
        cols = sorted(cols)

        out = pd.DataFrame(0.0, index=["IRR", "NPV", "Costs"], columns=pd.Index(cols, dtype=int))

        NOI_MRU = NOI_table_builder("MRU", "NOI")
        NOI_ITEM = NOI_table_builder(item, "NOI")

        for i in cols:
            if i == 0:
                continue

            # your original "1 + log(max(i,1))" factor; keep the behavior but make it explicit
            MRUAdd_multiplier = 1.0 + np.log(max(i, 1))
            MRUAdd = MRU_Add_Table.loc[item, "Extra MRU From Rankings"] * MRUAdd_multiplier

            NOITable = NOI_MRU * MRUAdd + NOI_ITEM * i

            # numpy_financial.irr may return np.nan for non-standard cashflows; keep that behavior
            out.at["IRR", i] = nf.irr(NOITable.to_numpy(dtype=float))
            out.at["NPV", i] = nf.npv(Discount_rate, NOITable.to_numpy(dtype=float))
            out.at["Costs", i] = (
                (Item_Accounting_table.loc["MRU", "Construction_cost"] + Item_Accounting_table.loc["MRU", "Soft_Costs"]) * MRUAdd
                + (Item_Accounting_table.loc[item, "Construction_cost"] + Item_Accounting_table.loc[item, "Soft_Costs"]) * i
            )

        return out

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
    NOI_by_item = {name: NOI_table_builder(name, "NOI") for name in Item_Accounting_table.index if name != "Land"}

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
            1.0 + rank_to_profit(Input_table.loc[idx, "Units/Rank"])
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
            1.0 + rank_to_profit(Input_table.loc[idx, "Units/Rank"])
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

    GPTOutputTable_Housing_Micro = GPTOutputTable_Builder(5, 51, 5, "Micro Units")
    GPTOutputTable_InBuilding_Grocery = GPTOutputTable_Builder(0, 6, 1, "Grocery Store")
    GPTOutputTable_InBuilding_CommunityCenter = GPTOutputTable_Builder(0, 6, 1, "Community Center")
    GPTOutputTable_OffSite_ParkPlaza = GPTOutputTable_Builder(0, 6, 1, "Park/Plaza")

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


