#Files V1.1 is intended to act as a compartmentalized version of V1.0.
#This file, V1.1p1, is part 1 of the code. This is the code that takes in the inputs from Yasushi's sliders and outputs results that are meant to be sent to Alan's ChatGPT API.

import pandas as pd
import numpy as np
import numpy_financial as nf

#Assorted Items
MRU_count_initial = 48
soft_costs = 0.22
Rent_increase = 0.10
Upkeep_increase = 0.04
Other_expenses = -500
Discount_rate = 0.08
Market_rent_sqft = 4
Exit_value_multiple = 20

#Sliders. Change code here (specifically st.slider) when using the physical slider.
def rank_to_profit (rank):
    return 0.2*(rank/10)**2

#Here is where we would have the rankings from Yasushi's slider.
#These originally were written with streamlit in V1.0, but as long as the rankings are translated to these variables, the code works.
#Right now I set them all to 5.
ranking_Housing_Micro = 5
ranking_InBuilding_Grocery = 5
ranking_InBuilding_CommunityCenter = 5
ranking_OffSite_ParkPlaza = 5

#Item Accounting Table of Excel Sheet
Item_Accounting_table = {
    "Size": [9000, 750, 300, 7500, 20000, 0],
    "Rent_yearly": [0, 36000, 7200, 300000, 0, 0],
    "Construction_cost": [-900, -375000, -150000, -2750000, -10000000, -4500000],
    "Soft_Costs": [0, 0, 0, 0, 0, 0],
    "Upkeep_yearly": [0, -6000, -2400, -82500, -472000, -125000],
    "MRU_add_per_unit": [0, 0, 0, 0, 0, 0]
}
Item_Accounting_table = pd.DataFrame(Item_Accounting_table)
Item_Accounting_table.index = ["Land", "MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"]
for i in Item_Accounting_table.index:
    Item_Accounting_table.loc[i, "Soft_Costs"] = Item_Accounting_table.loc[i, "Construction_cost"] * soft_costs


#Input Table of Excel Sheet: to be revised
Input_table = {
    "Units/Rank": [MRU_count_initial, ranking_Housing_Micro, ranking_InBuilding_Grocery, ranking_InBuilding_CommunityCenter, ranking_OffSite_ParkPlaza],
    "Net Profit/Year/SqFt": [0, 0, 0, 0, 0],
    "MRU_Add": [0, 0, 0, 0, 0]
}
Input_table = pd.DataFrame(Input_table)
Input_table.index = ["MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"]
for i in Item_Accounting_table.index[1:]:
    if Item_Accounting_table.loc[i, "Size"] != 0:
        Input_table.loc[i, "Net Profit/Year/SqFt"] = (Item_Accounting_table.loc[i, "Rent_yearly"]+Item_Accounting_table.loc[i, "Upkeep_yearly"])/Item_Accounting_table.loc[i, "Size"]
    else:
        Input_table.loc[i, "Net Profit/Year/SqFt"] = 0




#NOI Tables. This function returns the 
def NOI_table_builder (item_type, return_type):
    NoiTable = np.zeros((3, 11), dtype=float)
    NoiTable [2, 0] = Item_Accounting_table.loc[item_type, "Construction_cost"]*(1+soft_costs)
    NoiTable [0, 1] = Item_Accounting_table.loc[item_type, "Rent_yearly"]
    NoiTable [1, 1] = Item_Accounting_table.loc[item_type, "Upkeep_yearly"]
    for i in range (2, 11):
        NoiTable [0, i] = NoiTable [0, i-1]*(1+Rent_increase)
        NoiTable [1, i] = NoiTable [1, i-1]*(1+Upkeep_increase)
    NoiTable [0, 10] = NoiTable [0, 10] * (Exit_value_multiple+1) #Sell price addition
    for i in range (1, 11):
        NoiTable [2, i] = NoiTable [0, i] + NoiTable [1, i]
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

#Market Rate Unit Add Calculations
MRU_Add_Table = np.zeros((5, 4), dtype=float) #Make the Table
MRU_Add_Table = pd.DataFrame(MRU_Add_Table, columns = ["NPV/SqFt", "MRU Break Even", "Scaled for Size", "Extra MRU From Rankings"])
MRU_Add_Table.index = Input_table.index
for i in MRU_Add_Table.index:
    if Item_Accounting_table.loc [i, "Size"] != 0: #This is for all calculations except for off-site items
        MRU_Add_Table.loc[i, "NPV/SqFt"] = nf.npv(Discount_rate, NOI_table_builder(i, "NOI"))/Item_Accounting_table.loc [i, "Size"] #calculates NPV/sqft
        if i == "MRU": #All MRU equivalent values for MRU is 0
            MRU_Add_Table.loc[i, "MRU Break Even"] = 0
            MRU_Add_Table.loc[i, "Scaled for Size"] = 0
            MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = 0
        else: #for each row, fill out horizontally, left to right
            MRU_Add_Table.loc[i, "MRU Break Even"] = (MRU_Add_Table.loc["MRU", "NPV/SqFt"] - MRU_Add_Table.loc[i, "NPV/SqFt"])/MRU_Add_Table.loc["MRU", "NPV/SqFt"] #this calculates MRUs to break even/sqft
            MRU_Add_Table.loc[i, "Scaled for Size"] = MRU_Add_Table.loc[i, "MRU Break Even"]*Item_Accounting_table.loc[i, "Size"]/Item_Accounting_table.loc["MRU", "Size"]
            MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = MRU_Add_Table.loc[i, "Scaled for Size"]*(1+rank_to_profit(Input_table.loc[i, "Units/Rank"]))
    else: #for off site locations, since we don't calculate per sqft, only absolute. Similarly, calculate left to right
        MRU_Add_Table.loc[i, "NPV/SqFt"] = 0
        MRU_Add_Table.loc[i, "MRU Break Even"] = (nf.npv(Discount_rate, NOI_table_builder("MRU", "NOI"))-nf.npv(Discount_rate, NOI_table_builder(i, "NOI")))/nf.npv(Discount_rate, NOI_table_builder("MRU", "NOI"))
        MRU_Add_Table.loc[i, "Scaled for Size"] = MRU_Add_Table.loc[i, "MRU Break Even"]
        MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = MRU_Add_Table.loc[i, "Scaled for Size"]*(1+rank_to_profit(Input_table.loc[i, "Units/Rank"])) #this is the same as "Base Extra MRU Percent" in MSPF 4.2 "Natural Log Testing Stuff" sheet

#Update older tables with MRU add numbers
for i in MRU_Add_Table.index:
    Item_Accounting_table.loc[i, "MRU_add_per_unit"] = MRU_Add_Table.loc[i, "Extra MRU From Rankings"]


#This section builds the output formulas for ChatGPT. For each amenity type, it builds a chart that shows for this many items of each community benefit, here is the IRR, NPV, and cost associated with that item PLUS the MRU add.
def GPTOutputTable_Builder(min_units, max_units, step, item):
    cols = list(range(min_units, max_units, step))
    if 0 not in cols:
        cols = [0] + cols
    cols = sorted(cols)

    GPTOutputTable = pd.DataFrame(
        0.0, 
        index=['IRR', 'NPV', 'Costs'], 
        columns=pd.Index(cols, dtype=int)
    )

    for i in cols:
        if i == 0:
            continue

        log_arg = max(i, 1)
        MRUAdd = MRU_Add_Table.loc[item, "Extra MRU From Rankings"] * (1 + np.log(log_arg))

        NOITable = NOI_table_builder("MRU", "NOI") * MRUAdd + NOI_table_builder(item, "NOI") * i

        GPTOutputTable.at["IRR", i]   = nf.irr(NOITable)
        GPTOutputTable.at["NPV", i]   = nf.npv(Discount_rate, NOITable)
        GPTOutputTable.at["Costs", i] = (
            (Item_Accounting_table.loc["MRU", "Construction_cost"] + Item_Accounting_table.loc["MRU", "Soft_Costs"]) * MRUAdd
            + (Item_Accounting_table.loc[item, "Construction_cost"] + Item_Accounting_table.loc[item, "Soft_Costs"]) * i
        )

    return GPTOutputTable

#These four tables should be exported to Alan's ChatGPT API, along with a prompt of something along the following:
#"You are a real estate developer in [city]. In addition to what you already have approved, you can add the following community amenities (micro-unit housing, grocery store, community center, or funding for an off-site plaza), with the quantities and resulting IRR, NPV, and initial costs in the charts below.
# With this information, return a 2-row 1-column DataFrame of how many of each amenity you would build. The index should be labeled 'Micro Units', 'Grocery Store', 'Community Center', and 'Park/Plaza', and the only column should list how many of each amenity you decide to build. The column should remain unnamed."
GPTOutputTable_Prompt = "You are a real estate developer in San Francisco. In addition to what you already have approved by the city, you can add the following community amenities (micro-unit housing, grocery store, community center, or funding for an off-site plaza), with the quantities and resulting IRR, NPV, and initial costs in the charts below. With this information, return a 2-row 1-column DataFrame of how many of each amenity you would build. The index should be labeled 'Micro Units', 'Grocery Store', 'Community Center', and 'Park/Plaza', and the only column should list how many of each amenity you decide to build. The column should remain unnamed."
GPTOutputTable_Housing_Micro = GPTOutputTable_Builder(5, 51, 5, "Micro Units")
GPTOutputTable_InBuilding_Grocery = GPTOutputTable_Builder(0, 6, 1, "Grocery Store")
GPTOutputTable_InBuilding_CommunityCenter = GPTOutputTable_Builder(0, 6, 1, "Community Center")
GPTOutputTable_OffSite_ParkPlaza = GPTOutputTable_Builder(0, 6, 1, "Park/Plaza")