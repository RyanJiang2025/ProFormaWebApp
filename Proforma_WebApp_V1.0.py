# To run: streamlit run [filename].py

# Changes: scaling, making sliders more sensitive (20 --> 30% max)

import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as nf
import altair as alt

st.title("Dynamic Zoning Simulation")
st.caption("Most Simple Pro Forma Web App Version 1")
st.markdown(
    "This activity simulates the activity of a real estate developer on a 9000 SqFt land plot in San Francisco. Based on policy inputs, their decision on what to built will change."
)
st.markdown(
    "Instructions: use the sliders to select the priority for each community benefit. This will affect the financial incentives for the developr, and affect what gets built. A greater priority means more market-rate apartment units are permitted for the developer, to make up the loss; however, be aware that apartment units and some amenities increase building height."
)

st.header("Control Panel")

# Scaling Values
Scaling_Grocery_Rent = 0.1
Scaling_ParkPlaza_MRUAdd = 2.15
Scaling_Micro_MRUAdd = 2
Scaling_CommunityCenter_MRUAdd = 0.75

# Assorted Items
MRU_count_initial = 48
soft_costs = 0.22
Rent_increase = 0.10
Upkeep_increase = 0.04
Other_expenses = -500
Discount_rate = 0.08
Market_rent_sqft = 4
Exit_value_multiple = 20


# Sliders. Change code here (specifically st.slider) when using the physical slider.
def rank_to_profit(rank):
    return 0.3 * (rank / 10) ** 2  # used to be 0.2, if problematic change here


st.subheader("Micro Units")
ranking_Housing_Micro = st.slider(
    "For Young Professionals", min_value=1, max_value=10, value=5
)
st.write(
    "Additional Profit: ", round(rank_to_profit(ranking_Housing_Micro) * 100, 2), "%"
)

st.subheader("Grocery Store")
ranking_InBuilding_Grocery = st.slider(
    "On-Site Grocery Store", min_value=1, max_value=10, value=5
)
st.write(
    "Additional Profit: ",
    round(rank_to_profit(ranking_InBuilding_Grocery) * 100, 2),
    "%",
)

st.subheader("Community Center")
ranking_InBuilding_CommunityCenter = st.slider(
    "Gathering Place for Community", min_value=1, max_value=10, value=5
)
st.write(
    "Additional Profit: ",
    round(rank_to_profit(ranking_InBuilding_CommunityCenter) * 100, 2),
    "%",
)

st.subheader("Park/Plaza")
ranking_OffSite_ParkPlaza = st.slider(
    "Off-site Public Area", min_value=1, max_value=10, value=5
)
st.write(
    "Additional Profit: ",
    round(rank_to_profit(ranking_OffSite_ParkPlaza) * 100, 2),
    "%",
)

# Item Accounting Table of Excel Sheet
Item_Accounting_table = {
    "Size": [9000, 750, 300, 7500, 20000, 0],
    "Rent_yearly": [0, 36000, 7200, 300000, 0, 0],
    "Construction_cost": [-900, -375000, -150000, -2750000, -10000000, -4500000],
    "Soft_Costs": [0, 0, 0, 0, 0, 0],
    "Upkeep_yearly": [0, -6000, -2400, -82500, -472000, -125000],
    "MRU_add_per_unit": [0, 0, 0, 0, 0, 0],
}
Item_Accounting_table = pd.DataFrame(Item_Accounting_table)
Item_Accounting_table.index = [
    "Land",
    "MRU",
    "Micro Units",
    "Grocery Store",
    "Community Center",
    "Park/Plaza",
]
for i in Item_Accounting_table.index:
    Item_Accounting_table.loc[i, "Soft_Costs"] = (
        Item_Accounting_table.loc[i, "Construction_cost"] * soft_costs
    )

Item_Accounting_table.loc["Grocery Store", "Rent_yearly"] = (
    Item_Accounting_table.loc["Grocery Store", "Rent_yearly"] * Scaling_Grocery_Rent
)  # Grocery Scaling


# Input Table of Excel Sheet: to be revised
Input_table = {
    "Units/Rank": [
        MRU_count_initial,
        ranking_Housing_Micro,
        ranking_InBuilding_Grocery,
        ranking_InBuilding_CommunityCenter,
        ranking_OffSite_ParkPlaza,
    ],
    "Net Profit/Year/SqFt": [0, 0, 0, 0, 0],
    "MRU_Add": [0, 0, 0, 0, 0],
}
Input_table = pd.DataFrame(Input_table)
Input_table.index = [
    "MRU",
    "Micro Units",
    "Grocery Store",
    "Community Center",
    "Park/Plaza",
]
for i in Item_Accounting_table.index[1:]:
    if Item_Accounting_table.loc[i, "Size"] != 0:
        Input_table.loc[i, "Net Profit/Year/SqFt"] = (
            Item_Accounting_table.loc[i, "Rent_yearly"]
            + Item_Accounting_table.loc[i, "Upkeep_yearly"]
        ) / Item_Accounting_table.loc[i, "Size"]
    else:
        Input_table.loc[i, "Net Profit/Year/SqFt"] = 0


# NOI Tables. This function returns the
def NOI_table_builder(item_type, return_type):
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


# Market Rate Unit Add Calculations
MRU_Add_Table = np.zeros((5, 4), dtype=float)  # Make the Table
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
for i in MRU_Add_Table.index:
    if (
        Item_Accounting_table.loc[i, "Size"] != 0
    ):  # This is for all calculations except for off-site items
        MRU_Add_Table.loc[i, "NPV/SqFt"] = (
            nf.npv(Discount_rate, NOI_table_builder(i, "NOI"))
            / Item_Accounting_table.loc[i, "Size"]
        )  # calculates NPV/sqft
        if i == "MRU":  # All MRU equivalent values for MRU is 0
            MRU_Add_Table.loc[i, "MRU Break Even"] = 0
            MRU_Add_Table.loc[i, "Scaled for Size"] = 0
            MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = 0
        else:  # for each row, fill out horizontally, left to right
            MRU_Add_Table.loc[i, "MRU Break Even"] = (
                MRU_Add_Table.loc["MRU", "NPV/SqFt"] - MRU_Add_Table.loc[i, "NPV/SqFt"]
            ) / MRU_Add_Table.loc[
                "MRU", "NPV/SqFt"
            ]  # this calculates MRUs to break even/sqft
            MRU_Add_Table.loc[i, "Scaled for Size"] = (
                MRU_Add_Table.loc[i, "MRU Break Even"]
                * Item_Accounting_table.loc[i, "Size"]
                / Item_Accounting_table.loc["MRU", "Size"]
            )
            MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = MRU_Add_Table.loc[
                i, "Scaled for Size"
            ] * (1 + rank_to_profit(Input_table.loc[i, "Units/Rank"]))
    else:  # for off site locations, since we don't calculate per sqft, only absolute. Similarly, calculate left to right
        MRU_Add_Table.loc[i, "NPV/SqFt"] = 0
        MRU_Add_Table.loc[i, "MRU Break Even"] = (
            nf.npv(Discount_rate, NOI_table_builder("MRU", "NOI"))
            - nf.npv(Discount_rate, NOI_table_builder(i, "NOI"))
        ) / nf.npv(Discount_rate, NOI_table_builder("MRU", "NOI"))
        MRU_Add_Table.loc[i, "Scaled for Size"] = MRU_Add_Table.loc[i, "MRU Break Even"]
        MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = (
            MRU_Add_Table.loc[i, "Scaled for Size"]
            * (1 + rank_to_profit(Input_table.loc[i, "Units/Rank"]))
        )  # this is the same as "Base Extra MRU Percent" in MSPF 4.2 "Natural Log Testing Stuff" sheet

# Scaling
MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] = (
    MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"]
    * Scaling_ParkPlaza_MRUAdd
)
MRU_Add_Table.loc["Micro Units", "Extra MRU From Rankings"] = (
    MRU_Add_Table.loc["Micro Units", "Extra MRU From Rankings"] * Scaling_Micro_MRUAdd
)
MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] = (
    MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"]
    * Scaling_CommunityCenter_MRUAdd
)


# Debugging
# st.subheader("Plaza MRU Add Scaler")
# Debug_ParkPlaza_MRUAdd_Slider = st.slider("Debugging: Park/Plaza MRU Add Slider", min_value=100, max_value=300, value=200)
# st.write("Plaza MRU Percentage: ", Debug_ParkPlaza_MRUAdd_Slider, "%")
# MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] * Debug_ParkPlaza_MRUAdd_Slider/100

# st.subheader("Community Center MRU Add Scaler")
# Debug_CommunityCenter_MRUAdd_Slider = st.slider("Debugging: Community Center MRU Add Slider", min_value=1, max_value=200, value=100)
# st.write("Community Center MRU Percentage: ", Debug_CommunityCenter_MRUAdd_Slider, "%")
# MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] * Debug_CommunityCenter_MRUAdd_Slider/100


# Update older tables with MRU add numbers
for i in MRU_Add_Table.index:
    Item_Accounting_table.loc[i, "MRU_add_per_unit"] = MRU_Add_Table.loc[
        i, "Extra MRU From Rankings"
    ]


# More Debugging, delete later
# st.subheader("Debugging Grocery Slider IRR")
# Debug_GroceryStore_IRR_Scaling_Slider = st.slider("Debugging: Grocery Store IRR Scaler", min_value=1, max_value=10, value=5)
# st.write("Debugging Grocery Store IRR Percent: ", Debug_GroceryStore_IRR_Scaling_Slider*10, "%")
# MRU_Add_Table.loc["Grocery Store", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Grocery Store", "Extra MRU From Rankings"] * Debug_GroceryStore_IRR_Scaling_Slider/100
# Item_Accounting_table.loc["Grocery Store", "MRU_add_per_unit"] = MRU_Add_Table.loc["Grocery Store", "Extra MRU From Rankings"]


# Write Tables
# st.write("Item Accounting Table")
# st.dataframe(Item_Accounting_table)
# st.write("Input Table")
# st.dataframe(Input_table)
# st.write("Extra Market Rate Units Chart")
# st.write(MRU_Add_Table)


# This section builds the output formulas for ChatGPT. For each amenity type, it builds a chart that shows for this many items of each community benefit, here is the IRR, NPV, and cost associated with that item PLUS the MRU add.
def GPTOutputTable_Builder(min_units, max_units, step, item):
    cols = list(range(min_units, max_units, step))
    if 0 not in cols:
        cols = [0] + cols
    cols = sorted(cols)

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
            NOI_table_builder("MRU", "NOI") * MRUAdd
            + NOI_table_builder(item, "NOI") * i
        )

        GPTOutputTable.at["IRR", i] = nf.irr(NOITable)
        GPTOutputTable.at["NPV", i] = nf.npv(Discount_rate, NOITable)
        GPTOutputTable.at["Costs", i] = (
            Item_Accounting_table.loc["MRU", "Construction_cost"]
            + Item_Accounting_table.loc["MRU", "Soft_Costs"]
        ) * MRUAdd + (
            Item_Accounting_table.loc[item, "Construction_cost"]
            + Item_Accounting_table.loc[item, "Soft_Costs"]
        ) * i

    return GPTOutputTable


# These four tables should be exported to Alan's ChatGPT API, along with a prompt of something along the following:
# "You are a real estate developer in [city]. In addition to what you already have approved, you can add the following community amenities (micro-unit housing, grocery store, community center, or funding for an off-site plaza), with the quantities and resulting IRR, NPV, and initial costs in the charts below.
# With this information, return a chart of how many of each amenity you would build. The first column should be labeled 'Micro Units', 'Grocery Store', 'Community Center', and 'Park/Plaza', and the second column should list how many of each amenity you decide to build."
GPTOutputTable_Housing_Micro = GPTOutputTable_Builder(5, 51, 5, "Micro Units")
GPTOutputTable_InBuilding_Grocery = GPTOutputTable_Builder(0, 6, 1, "Grocery Store")
GPTOutputTable_InBuilding_CommunityCenter = GPTOutputTable_Builder(
    0, 6, 1, "Community Center"
)
GPTOutputTable_OffSite_ParkPlaza = GPTOutputTable_Builder(0, 6, 1, "Park/Plaza")

# These are the outputs for ChatGPT
# st.write("Output Table Housing Micro")
# st.write(GPTOutputTable_Housing_Micro)
# st.write("Output Table Grocery Store")
# st.write(GPTOutputTable_InBuilding_Grocery)
# st.write("Output Table Community Center")
# st.write(GPTOutputTable_InBuilding_CommunityCenter)
# st.write("Output Table Park/Plaza")
# st.write(GPTOutputTable_OffSite_ParkPlaza)

# Debugging Start aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa


# Helper: return the first 6 IRR values from a GPTOutputTable_*
def _first_six_irrs(df: pd.DataFrame) -> list[float]:
    # ensure columns are sorted numerically, then take first six
    cols = sorted(df.columns)[:6]
    return df.loc["IRR", cols].tolist()


# Build the wide table
IRR_first6 = pd.DataFrame(
    [
        _first_six_irrs(GPTOutputTable_Housing_Micro),
        _first_six_irrs(GPTOutputTable_InBuilding_Grocery),
        _first_six_irrs(GPTOutputTable_InBuilding_CommunityCenter),
        _first_six_irrs(GPTOutputTable_OffSite_ParkPlaza),
    ],
    index=["Micro Units", "Grocery Store", "Community Center", "Park/Plaza"],
    columns=[f"Period {i + 1}" for i in range(6)],
)

# st.subheader("IRR (first 6 periods)")
# st.dataframe(IRR_first6.style.format("{:.4f}"))

# Optional: tidy / long format (Amenity, Period, IRR)
IRR_first6_long = (
    IRR_first6.reset_index()
    .melt(id_vars="index", var_name="Period", value_name="IRR")
    .rename(columns={"index": "Amenity"})
)
# st.dataframe(IRR_first6_long)


# If you used the helper from before:
# IRR_first6_long has columns: Amenity | Period | IRR

# st.subheader("IRR (first 6 periods) — Interactive")
chart = (
    alt.Chart(IRR_first6_long)
    .mark_line(point=True)
    .encode(
        x=alt.X(
            "Period:N", title="Period"
        ),  # if your columns are unit counts, use ':Q' and title='Units'
        y=alt.Y("IRR:Q", title="IRR", axis=alt.Axis(format="%")),
        color=alt.Color("Amenity:N", title="Amenity"),
        tooltip=["Amenity", "Period", alt.Tooltip("IRR:Q", format=".2%")],
    )
    .properties(height=380)
    .interactive()
)

st.altair_chart(chart, use_container_width=True)


# Helper: extract first 6 NPV values from a GPTOutputTable
def _first_six_npvs(df: pd.DataFrame) -> list[float]:
    cols = sorted(df.columns)[:6]  # first 6 columns (periods)
    return df.loc["NPV", cols].tolist()


# Assemble them into one dataframe
NPV_first6 = pd.DataFrame(
    [
        _first_six_npvs(GPTOutputTable_Housing_Micro),
        _first_six_npvs(GPTOutputTable_InBuilding_Grocery),
        _first_six_npvs(GPTOutputTable_InBuilding_CommunityCenter),
        _first_six_npvs(GPTOutputTable_OffSite_ParkPlaza),
    ],
    index=["Micro Units", "Grocery Store", "Community Center", "Park/Plaza"],
    columns=[f"Period {i + 1}" for i in range(6)],
)

# st.subheader("NPV (first 6 periods)")
# st.dataframe(NPV_first6.style.format("${:,.0f}"))

NPV_first6_long = (
    NPV_first6.reset_index()
    .melt(id_vars="index", var_name="Period", value_name="NPV")
    .rename(columns={"index": "Amenity"})
)

# st.subheader("NPV (first 6 periods) — Interactive Chart")
chart = (
    alt.Chart(NPV_first6_long)
    .mark_line(point=True)
    .encode(
        x=alt.X("Period:N", title="Period"),
        y=alt.Y("NPV:Q", title="Net Present Value", axis=alt.Axis(format="$,.0f")),
        color=alt.Color("Amenity:N", title="Amenity"),
        tooltip=["Amenity", "Period", alt.Tooltip("NPV:Q", format="$,.0f")],
    )
    .properties(height=380)
    .interactive()
)
st.altair_chart(chart, use_container_width=True)


# Debugging End aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa


# The results from ChatGPT then need to be re-inputted into the pro forma, here.

Final_Build_Table = pd.DataFrame(
    {"Number": [MRU_count_initial, 0, 0, 0, 0], "Size": [0, 0, 0, 0, 0]},
    index=Input_table.index,
)
for i in Final_Build_Table.index:
    if i != "MRU" and Final_Build_Table.loc[i, "Number"] != 0:
        Final_Build_Table.loc["MRU", "Number"] += MRU_Add_Table.loc[
            i, "Extra MRU From Rankings"
        ] * (1 + np.log(Final_Build_Table.loc[i, "Number"]))
Final_Build_Table.loc["MRU", "Number"] = np.round(
    Final_Build_Table.loc["MRU", "Number"]
)
for i in Final_Build_Table.index:
    Final_Build_Table.loc[i, "Size"] = (
        Item_Accounting_table.loc[i, "Size"] * Final_Build_Table.loc[i, "Number"]
    )

# Here, sum up the "height" column and divide by our land size (9000, maybe should be set as a variable?) to get final floor number, and then round up.
# The final build table, plus the height, should be sent to Adrian for the 3d visualization.

st.write("Final Build Table")
st.write(Final_Build_Table)


# This code writes the final financial table, which calculates overall revenue, upkeep, NOI, etc, culminating in pre-tax cash flow.
# We then use pre-tax cash flor to calculate various financial metrics in our final display table.
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
        NOI_table_builder(item, "Rent") * Final_Build_Table.loc[item, "Number"]
    )
    Master_Financial_Table.loc["Upkeep"] += (
        NOI_table_builder(item, "Upkeep") * Final_Build_Table.loc[item, "Number"]
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
# st.write(Master_Financial_Table)

Final_Display = pd.DataFrame(
    index=["Stories", "MRU Stories", "NPV", "IRR", "Likelihood of Construction"],
    columns=["Value"],
)
Final_Display.loc["Stories"] = np.ceil(
    Final_Build_Table.loc[:, "Size"].sum() / Item_Accounting_table.loc["Land", "Size"]
)
Final_Display.loc["MRU Stories"] = (
    Final_Build_Table.loc["MRU", "Size"] / Item_Accounting_table.loc["Land", "Size"]
)
Final_Display.loc["NPV"] = nf.npv(
    Discount_rate, Master_Financial_Table.loc["Pre-Tax Cash Flow", :]
)
Final_Display.loc["IRR"] = nf.irr(Master_Financial_Table.loc["Pre-Tax Cash Flow", :])
Final_Display.loc["Likelihood of Construction"] = 1 / (
    1 + np.e ** (-55 * (Final_Display.loc["IRR", "Value"] - 0.1))
)

st.write(Final_Display)
