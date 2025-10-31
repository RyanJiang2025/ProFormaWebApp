# Hello MAS 552 students! Here are the following instructions for changing the code to implement your own amenities for your neighborhood.
# Step 1: change the item name and descriptions to reflect your own amenities (lines 7-13).
# Step 2: change scaling to keep IRR values roughly grouped together (lines 14-23).
# Step 3: change the unit config to limit the number of units that can be built in each round (lines 25-34).
# Step 4: change item accounting table to reflect your own amenities (lines 50-92).

import pandas as pd
import numpy as np
import numpy_financial as nf
import streamlit as st

# Note for future reference: MRU stands for Market Rate Unit. Later versions changed the public-facing dataframes from "MRU" to "Market Rate Housing", however the coding still largely uses "MRU".

# TODO: These scale the IRR values for each amenity. You can change these to your own values. The main reason they are changed is to get the IRR values to roughly group together.
# You can do this in two ways: by scaling the Market Rate Unit add for each amenity, or to scale the rent itself. The rent scaling is more drastic, and so is only used here for the grocery store (where changing MRU add did little).
# Test the grouping of IRRs by looking at the IRR values on the slider scale of the web app. If one amenity is highly profitable compared to the others (given equal ratings), then you will see the IRR line jump up much higher.
# The reason we discuss grouping IRR is that NPV is much more diverse in the exact arc it takes.
# Scaling dictionary keyed by amenity names
Scaling_Grocery_Rent = 0.1
Scaling_ParkPlaza_MRUAdd = 2.15
Scaling_AffordableHousing_MRUAdd = 0.75
Scaling_CommunityCenter_MRUAdd = 0.75
Scaling_Fund_MRUAdd = 1  

# TODO: This configures how many units of each amenity to generate, and in what increments. For example, right now at default, the AI developer can build up to 5*10 affordable housing units in each round, while they can only build up to 1*3 grocery stores.
# As the AI developer chooses the build based on the tables that are generated using these numbers, the "count" and "step" variables limit developer options within a round.
INCLUDE_ZERO_BASELINE = True
AMENITY_UNIT_CONFIG = {
    "Affordable Housing": {"start": 0, "count": 11, "step": 5},
    "Grocery Store": {"start": 0, "count": 4, "step": 1},
    "Community Center": {"start": 0, "count": 4, "step": 1},
    "Park/Plaza": {"start": 0, "count": 4, "step": 1},
    "Fund": {"start": 0, "count": 11, "step": 1},
}

# Assorted Items
MRU_count_initial = 48
soft_costs = 0.22
Rent_increase = 0.10
Upkeep_increase = 0.04
Other_expenses = -500
Discount_rate = 0.08
Market_rent_sqft = 4
Exit_value_multiple = 20


def rank_to_profit(rank):
    return rank * 0.2

#TODO: This is the item accounting table. It is a table that contains the size, rent, construction cost, upkeep cost, and MRU add per unit for each amenity, plus land.
# Change this as you desire. The first item in each list is the land (size, no rent generated, cost/sqft, no upkeep). 
# For the other items, it lists the sqft size (0 for off-site amenities like a park or non-physical items like funds), the yearly rental income, the initial construction cost, soft costs (which should be left as 0, they are added later), and the yearly upkeep. MRU add per unit should also be left blank, as those are endogenous to the model.
def get_item_accounting_table():
    """Creates and returns the Item Accounting Table with all calculations and scaling applied."""
    # Item Accounting Table of Excel Sheet
    Item_Accounting_table = {
        "Size": [9000, 750, 750, 7500, 20000, 0, 0],
        "Rent_yearly": [0, 36000, 18000, 300000, 0, 0, 0],
        "Construction_cost": [-900, -375000, -375000, -2750000, -10000000, -4500000, 0],
        "Soft_Costs": [0, 0, 0, 0, 0, 0, 0],
        "Upkeep_yearly": [
            0,
            -6000,
            -6000,
            -82500,
            -472000,
            -125000,
            -100000,
        ],  # The fund increment has to be significant (i.e. at least 50,000) because of the way MRU add is calculated. Without it, for each increment of funding, it adds 1 MRU, whether that is $10,000 or $1, which creates a very high IRR.
        "MRU_add_per_unit": [0, 0, 0, 0, 0, 0, 0],
    }
    Item_Accounting_table = pd.DataFrame(Item_Accounting_table)
    Item_Accounting_table.index = [
        "Land",
        "Market Rate Housing",
        "Affordable Housing",
        "Grocery Store",
        "Community Center",
        "Park/Plaza",
        "Fund",
    ]
    for i in Item_Accounting_table.index:
        Item_Accounting_table.loc[i, "Soft_Costs"] = (
            Item_Accounting_table.loc[i, "Construction_cost"] * soft_costs
        )

    # Scaling
    Item_Accounting_table.loc["Grocery Store", "Rent_yearly"] = (
        Item_Accounting_table.loc["Grocery Store", "Rent_yearly"] * Scaling_Grocery_Rent
    )

    return Item_Accounting_table


def get_input_table(Item_Accounting_table, rankings=None):
    """Creates and returns the Input Table with all calculations applied.

    If ``rankings`` is provided (dict with keys matching amenity names), it will be
    used directly. Otherwise, fall back to Streamlit session state (for the UI).
    """
    # Get rankings from provided param or session state
    if rankings is None:
        rankings = st.session_state.current_rankings["rankings"]
    Input_table = {
        "Units/Rank": [
            MRU_count_initial,
            rankings["Affordable Housing"],
            rankings["Grocery Store"],
            rankings["Community Center"],
            rankings["Park/Plaza"],
            rankings["Fund"],
        ],
        "Net Profit/Year/SqFt": [0, 0, 0, 0, 0, 0],
    }
    Input_table = pd.DataFrame(Input_table)
    Input_table.index = [
        "Market Rate Housing",
        "Affordable Housing",
        "Grocery Store",
        "Community Center",
        "Park/Plaza",
        "Fund",
    ]
    for i in Item_Accounting_table.index[1:]:
        if Item_Accounting_table.loc[i, "Size"] != 0:
            Input_table.loc[i, "Net Profit/Year/SqFt"] = (
                Item_Accounting_table.loc[i, "Rent_yearly"]
                + Item_Accounting_table.loc[i, "Upkeep_yearly"]
            ) / Item_Accounting_table.loc[i, "Size"]
        else:
            Input_table.loc[i, "Net Profit/Year/SqFt"] = 0
    return Input_table


def NOI_table_builder(Item_Accounting_table, item_type, return_type):
    NoiTable = np.zeros((3, 11), dtype=float)
    NoiTable[2, 0] = Item_Accounting_table.loc[item_type, "Construction_cost"] * (
        1 + soft_costs
    )
    NoiTable[0, 1] = Item_Accounting_table.loc[item_type, "Rent_yearly"]
    NoiTable[1, 1] = Item_Accounting_table.loc[item_type, "Upkeep_yearly"]
    for i in range(2, 11):
        NoiTable[0, i] = NoiTable[0, i - 1] * (1 + Rent_increase)
        NoiTable[1, i] = NoiTable[1, i - 1] * (1 + Upkeep_increase)
    NoiTable[0, 10] = NoiTable[0, 10] * (Exit_value_multiple + 1)  # Sell price addition
    for i in range(1, 11):
        NoiTable[2, i] = NoiTable[0, i] + NoiTable[1, i]
    NoiTable = pd.DataFrame(NoiTable)
    NoiTable.index = ["Rent", "Upkeep", "NOI"]
    if return_type == "Rent":
        return NoiTable.loc["Rent"]
    elif return_type == "Upkeep":
        return NoiTable.loc["Upkeep"]
    elif return_type == "NOI":
        return NoiTable.loc["NOI"]
    else:
        return NoiTable


def get_MRU_Add_table(Item_Accounting_table, Input_table):
    MRU_Add_Table = np.zeros((6, 4), dtype=float)  # Make the Table
    MRU_Add_Table = pd.DataFrame(
        MRU_Add_Table,
        columns=[
            "NPV/SqFt",
            "MRU Break Even",
            "Scaled for Size",
            "Extra MRU From Rankings",
        ],
    )
    MRU_Add_Table.index = Input_table.index
    # if st.session_state.toggle: #this measures if we have our amenity button on or off
    for i in MRU_Add_Table.index:
        if (
            Item_Accounting_table.loc[i, "Size"] != 0
        ):  # This is for all calculations except for off-site items
            MRU_Add_Table.loc[i, "NPV/SqFt"] = (
                nf.npv(
                    Discount_rate, NOI_table_builder(Item_Accounting_table, i, "NOI")
                )
                / Item_Accounting_table.loc[i, "Size"]
            )  # calculates NPV/sqft
            if (
                i == "Market Rate Housing"
            ):  # All Market Rate Housing equivalent values for Market Rate Housing is 0
                MRU_Add_Table.loc[i, "MRU Break Even"] = 0
                MRU_Add_Table.loc[i, "Scaled for Size"] = 0
                MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = 0
            else:  # for each row, fill out horizontally, left to right
                MRU_Add_Table.loc[i, "MRU Break Even"] = (
                    MRU_Add_Table.loc["Market Rate Housing", "NPV/SqFt"]
                    - MRU_Add_Table.loc[i, "NPV/SqFt"]
                ) / MRU_Add_Table.loc[
                    "Market Rate Housing", "NPV/SqFt"
                ]  # this calculates Market Rate Housings to break even/sqft
                MRU_Add_Table.loc[i, "Scaled for Size"] = (
                    MRU_Add_Table.loc[i, "MRU Break Even"]
                    * Item_Accounting_table.loc[i, "Size"]
                    / Item_Accounting_table.loc["Market Rate Housing", "Size"]
                )
                MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = MRU_Add_Table.loc[
                    i, "Scaled for Size"
                ] * (rank_to_profit(Input_table.loc[i, "Units/Rank"]))
        else:  # for off site locations, since we don't calculate per sqft, only absolute. Similarly, calculate left to right
            MRU_Add_Table.loc[i, "NPV/SqFt"] = 0
            MRU_Add_Table.loc[i, "MRU Break Even"] = (
                nf.npv(
                    Discount_rate,
                    NOI_table_builder(
                        Item_Accounting_table, "Market Rate Housing", "NOI"
                    ),
                )
                - nf.npv(
                    Discount_rate, NOI_table_builder(Item_Accounting_table, i, "NOI")
                )
            ) / nf.npv(
                Discount_rate,
                NOI_table_builder(Item_Accounting_table, "Market Rate Housing", "NOI"),
            )  # here is the problem: since funds have an NOI of 0????
            MRU_Add_Table.loc[i, "Scaled for Size"] = MRU_Add_Table.loc[
                i, "MRU Break Even"
            ]
            MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = (
                MRU_Add_Table.loc[i, "Scaled for Size"]
                * (rank_to_profit(Input_table.loc[i, "Units/Rank"]))
            )  # this is the same as "Base Extra MRU Percent" in MSPF 4.2 "Natural Log Testing Stuff" sheet

    MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] = (
        MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"]
        * Scaling_ParkPlaza_MRUAdd
    )
    MRU_Add_Table.loc["Affordable Housing", "Extra MRU From Rankings"] = (
        MRU_Add_Table.loc["Affordable Housing", "Extra MRU From Rankings"]
        * Scaling_AffordableHousing_MRUAdd
    )
    MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] = (
        MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"]
        * Scaling_CommunityCenter_MRUAdd
    )
    MRU_Add_Table.loc["Fund", "Extra MRU From Rankings"] = (
        MRU_Add_Table.loc["Fund", "Extra MRU From Rankings"] * Scaling_Fund_MRUAdd
    )
    # Update older tables with MRU add numbers
    for i in MRU_Add_Table.index:
        Item_Accounting_table.loc[i, "MRU_add_per_unit"] = MRU_Add_Table.loc[
            i, "Extra MRU From Rankings"
        ]
    return MRU_Add_Table


def GPTOutputTable_Builder(
    Item_Accounting_table,
    MRU_Add_Table,
    item,
    cols=None,
    min_units: int = 0,
    max_units: int = 11,
    step: int = 1,
):
    # Determine the unit columns to compute
    if cols is None:
        cols = list(range(min_units, max_units, step))
    # Optionally include a zero baseline
    if INCLUDE_ZERO_BASELINE and 0 not in cols:
        cols = [0] + cols
    # Deduplicate and sort; ensure ints
    cols = sorted({int(c) for c in cols})

    GPTOutputTable = pd.DataFrame(
        0.0, index=["IRR", "NPV", "Costs"], columns=pd.Index(cols, dtype=int)
    )

    for i in cols:
        if i == 0:
            continue

        log_arg = max(i, 1)
        MRUAdd = MRU_Add_Table.loc[item, "Extra MRU From Rankings"] * (
            1 + np.log(log_arg)
        )

        NOITable = (
            NOI_table_builder(Item_Accounting_table, "Market Rate Housing", "NOI")
            * MRUAdd
            + NOI_table_builder(Item_Accounting_table, item, "NOI") * i
        )

        GPTOutputTable.at["IRR", i] = nf.irr(NOITable)
        GPTOutputTable.at["NPV", i] = nf.npv(Discount_rate, NOITable)
        GPTOutputTable.at["Costs", i] = (
            Item_Accounting_table.loc["Market Rate Housing", "Construction_cost"]
            + Item_Accounting_table.loc["Market Rate Housing", "Soft_Costs"]
        ) * MRUAdd + (
            Item_Accounting_table.loc[item, "Construction_cost"]
            + Item_Accounting_table.loc[item, "Soft_Costs"]
        ) * i

    return GPTOutputTable


def generate_gpt_tables(Item_Accounting_table, MRU_Add_Table):
    """Generate IRR/NPV/Costs tables for each amenity across unit counts.

    Returns a dict mapping amenity name to a DataFrame with index [IRR, NPV, Costs]
    and integer columns representing unit counts (0..10).
    """
    tables = {}
    for amenity in [
        "Affordable Housing",
        "Grocery Store",
        "Community Center",
        "Park/Plaza",
        "Fund",
    ]:
        cfg = AMENITY_UNIT_CONFIG.get(amenity, {"start": 0, "count": 11, "step": 1})
        # Build columns per amenity
        cols = [cfg["start"] + cfg["step"] * k for k in range(cfg["count"])]
        tables[amenity] = GPTOutputTable_Builder(
            Item_Accounting_table,
            MRU_Add_Table,
            item=amenity,
            cols=cols,
        )
    return tables


def get_Final_Build_Table(Item_Accounting_table, Input_table, MRU_Add_Table):
    """Creates and returns the Final Build Table with all calculations applied."""
    Final_Build_Table = pd.DataFrame(
        {"Number": [MRU_count_initial, 0, 0, 0, 0, 0], "Size": [0, 0, 0, 0, 0, 0]},
        index=Input_table.index,
    )
    for i in Final_Build_Table.index:
        if i != "Market Rate Housing" and Final_Build_Table.loc[i, "Number"] != 0:
            Final_Build_Table.loc["Market Rate Housing", "Number"] += MRU_Add_Table.loc[
                i, "Extra MRU From Rankings"
            ] * (1 + np.log(Final_Build_Table.loc[i, "Number"]))
    Final_Build_Table.loc["Market Rate Housing", "Number"] = np.round(
        Final_Build_Table.loc["Market Rate Housing", "Number"]
    )
    for i in Final_Build_Table.index:
        Final_Build_Table.loc[i, "Size"] = (
            Item_Accounting_table.loc[i, "Size"] * Final_Build_Table.loc[i, "Number"]
        )
    return Final_Build_Table


def get_Master_Financial_Table(Item_Accounting_table, Final_Build_Table):
    """Creates and returns the Master Financial Table with all calculations applied."""
    Master_Financial_Table = pd.DataFrame(index=range(8), columns=range(11))
    Master_Financial_Table.index = [
        "Revenue",
        "Upkeep",
        "Hard Costs",
        "Soft Costs",
        "Land Costs",
        "NOI",
        "Other Expenses",
        "Pre-Tax Cash Flow",
    ]
    Master_Financial_Table = Master_Financial_Table.fillna(0)
    for item in Final_Build_Table.index:
        Master_Financial_Table.loc["Revenue"] += (
            NOI_table_builder(Item_Accounting_table, item, "Rent")
            * Final_Build_Table.loc[item, "Number"]
        )
        Master_Financial_Table.loc["Upkeep"] += (
            NOI_table_builder(Item_Accounting_table, item, "Upkeep")
            * Final_Build_Table.loc[item, "Number"]
        )
        Master_Financial_Table.loc["Hard Costs", 0] += (
            Final_Build_Table.loc[item, "Number"]
            * Item_Accounting_table.loc[item, "Construction_cost"]
        )
    Master_Financial_Table.loc["Soft Costs", 0] = (
        Master_Financial_Table.loc["Hard Costs", 0] * soft_costs
    )
    Master_Financial_Table.loc["Land Costs", 0] = (
        Item_Accounting_table.loc["Land", "Size"]
        * Item_Accounting_table.loc["Land", "Construction_cost"]
    )
    for period in Master_Financial_Table.columns:
        Master_Financial_Table.loc["NOI", period] = Master_Financial_Table.loc[
            ["Revenue", "Hard Costs", "Soft Costs", "Land Costs", "Upkeep"], period
        ].sum()
        Master_Financial_Table.loc["Other Expenses", period] = Other_expenses
        Master_Financial_Table.loc["Pre-Tax Cash Flow", period] = (
            Master_Financial_Table.loc["NOI", period]
            + Master_Financial_Table.loc["Other Expenses", period]
        )
    return Master_Financial_Table


def get_Final_Display(Item_Accounting_table, Final_Build_Table, Master_Financial_Table):
    """Creates and returns the Final Display Table with all calculations applied."""
    Final_Display = pd.DataFrame(
        index=[
            "Stories",
            "Market Rate Housing Stories",
            "NPV",
            "IRR",
            "Likelihood of Construction",
        ],
        columns=["Value"],
    )
    Final_Display.loc["Stories"] = np.ceil(
        Final_Build_Table.loc[:, "Size"].sum()
        / Item_Accounting_table.loc["Land", "Size"]
    )
    Final_Display.loc["Market Rate Housing Stories"] = (
        Final_Build_Table.loc["Market Rate Housing", "Size"]
        / Item_Accounting_table.loc["Land", "Size"]
    )
    Final_Display.loc["NPV"] = nf.npv(
        Discount_rate, Master_Financial_Table.loc["Pre-Tax Cash Flow", :]
    )
    Final_Display.loc["IRR"] = nf.irr(
        Master_Financial_Table.loc["Pre-Tax Cash Flow", :]
    )
    Final_Display.loc["Likelihood of Construction"] = 1 / (
        1 + np.e ** (-55 * (Final_Display.loc["IRR", "Value"] - 0.135))
    )
    return Final_Display
