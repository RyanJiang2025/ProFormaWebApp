import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as nf

st.title("Dynamic Zoning Simulation")
st.caption("Most Simple Pro Forma Web App Version 1")
st.markdown("This activity simulates the activity of a real estate developer on a 9000 SqFt land plot in San Francisco. Based on policy inputs, their decision on what to built will change.")
st.markdown("Instructions: use the sliders to select the priority for each community benefit. This will affect the financial incentives for the developr, and affect what gets built. A greater priority means more market-rate apartment units are permitted for the developer, to make up the loss; however, be aware that apartment units and some amenities increase building height.")

st.header("Control Panel")

MRU_count = 48

#Sliders
def rank_to_profit (rank):
    return 0.2*(rank/10)**2

st.subheader("Micro Units")
ranking_Housing_Micro = st.slider("For Young Professionals", min_value=1, max_value=10, value=5)
MRUadd_Housing_Micro = rank_to_profit(ranking_Housing_Micro)
st.write("Additional Profit: ", round(MRUadd_Housing_Micro*100, 2), "%")

st.subheader("Grocery Store")
ranking_InBuilding_Grocery = st.slider("On-Site Grocery Store", min_value=1, max_value=10, value=5)
MRUadd_InBuilding_Grocery = rank_to_profit(ranking_InBuilding_Grocery)
st.write("Additional Profit: ", round(MRUadd_InBuilding_Grocery*100, 2), "%")


st.subheader("Community Center")
ranking_InBuilding_CommunityCenter = st.slider("Gathering Place for Community", min_value=1, max_value=10, value=5)
MRUadd_InBuilding_CommunityCenter = rank_to_profit(ranking_InBuilding_CommunityCenter)
st.write("Additional Profit: ", round(MRUadd_InBuilding_CommunityCenter*100, 2), "%")

st.subheader("Park/Plaza")
ranking_OffSite_ParkPlaza = st.slider("Off-site Public Area", min_value=1, max_value=10, value=5)
MRUadd_OffSite_ParkPlaza = rank_to_profit(ranking_OffSite_ParkPlaza)
st.write("Additional Profit: ", round(MRUadd_OffSite_ParkPlaza*100, 2), "%")

#Item Accounting Table of Excel Sheet
Item_Accounting_table = {
    "Size": [9000, 750, 300, 7500, 20000, 0],
    "Rent_yearly": [0, 36000, 7200, 300000, 0, 0],
    "Construction_cost": [-900, -375000, -150000, -2750000, -10000000, -4500000],
    "Soft_Costs": 
    "Upkeep_yearly": [0, -6000, -2400, -82500, -472000, -125000],
    "MRU_add_per_unit": [0, 0, 0, 0, 0, 0]
}
Item_Accounting_table = pd.DataFrame(Item_Accounting_table)
Item_Accounting_table.index = ["Land", "MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"]
st.write("Item Accounting Table, old (see below)")
st.dataframe(Item_Accounting_table)

#Input Table of Excel Sheet: to be revised
Input_table = {
    "Units/Rank": [MRU_count, ranking_Housing_Micro, ranking_InBuilding_Grocery, ranking_InBuilding_CommunityCenter, ranking_OffSite_ParkPlaza],
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
st.write("Input Table")
st.dataframe(Input_table)

#Other Items
soft_costs = 0.22
Rent_increase = 0.10
Upkeep_increase = 0.04
Other_expenses = -500
Discount_rate = 0.08
Market_rent_sqft = 4
Exit_value_multiple = 20

#NOI Tables. This function returns the 
def NOI_table_builder (item_type, return_type):
    NoiTable = np.zeros((3, 11), dtype=int)
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
st.write("Extra Market Rate Units Chart")
MRU_Add_Table = np.zeros((5, 4), dtype=int) #Make the Table
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
        MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = MRU_Add_Table.loc[i, "Scaled for Size"]*(1+rank_to_profit(Input_table.loc[i, "Units/Rank"]))
st.write(MRU_Add_Table)

#Update older tables with MRU add numbers
for i in MRU_Add_Table.index:
    Item_Accounting_table.loc[i, "MRU_add_per_unit"] = MRU_Add_Table.loc[i, "Extra MRU From Rankings"]
st.write("Item Acocunting Table Updated")
st.dataframe(Item_Accounting_table)

#At this point, all coding that is in MSPF version 4.2 is complete, aside from the financials. Now, the rest of the calculations depend on how many units of each item to construct, which requires modeling developer behavior.



def marginal_return (item_type, nth_marginal_unit):
    first_unit_profit = rank_to_profit(Input_table.loc[item_type, Units/Rank])
    item_NOI_Table = NOI_table_builder(item_type, "NOI")
    MRU_NOI_Table = NOI_table_builder("MRU", "NOI")*

