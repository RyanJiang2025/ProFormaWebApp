# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict
import pandas as pd
import numpy as np
import os
from openai import OpenAI
from Proforma_WebApp_preapi import compute_proforma  # your function from earlier
import json
import streamlit as st
import numpy_financial as nf


# === OpenAI client ===
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o")

app = FastAPI(title="Proforma API", version="1.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProformaRequest(BaseModel):
    ranking_Housing_Micro: float = Field(5, ge=0)
    ranking_InBuilding_Grocery: float = Field(5, ge=0)
    ranking_InBuilding_CommunityCenter: float = Field(5, ge=0)
    ranking_OffSite_ParkPlaza: float = Field(5, ge=0)
    model: str = Field(default=OPENAI_MODEL_DEFAULT)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=600)

def df_to_split_json(df: pd.DataFrame) -> Dict[str, Any]:
    data = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
    payload = data.to_dict(orient="split")
    payload["index"] = [int(i) if isinstance(i, (np.integer,)) else i for i in payload["index"]]
    payload["columns"] = [str(c) for c in payload["columns"]]
    return payload

def df_to_markdown(df: pd.DataFrame, title: str) -> str:
    """Compact markdown block (easy for ChatGPT to interpret)."""
    return f"### {title}\n\n" + df.to_markdown(index=True)

#Assorted Items
MRU_count_initial = 48
soft_costs = 0.22
Rent_increase = 0.10
Upkeep_increase = 0.04
Other_expenses = -500
Discount_rate = 0.08
Market_rent_sqft = 4
Exit_value_multiple = 20

Scaling_Grocery_Rent = 0.1
Scaling_ParkPlaza_MRUAdd = 2.15
Scaling_Micro_MRUAdd = 2
Scaling_CommunityCenter_MRUAdd = 0.75

def rank_to_profit (rank):
    return 0.2*(rank/10)**2
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

Item_Accounting_table.loc["Grocery Store", "Rent_yearly"] = Item_Accounting_table.loc["Grocery Store", "Rent_yearly"]*Scaling_Grocery_Rent

st.subheader("Micro Units")
ranking_Housing_Micro = st.slider("For Young Professionals", min_value=1, max_value=10, value=5)
st.write("Additional Profit: ", round(rank_to_profit(ranking_Housing_Micro)*100, 2), "%")

st.subheader("Grocery Store")
ranking_InBuilding_Grocery = st.slider("On-Site Grocery Store", min_value=1, max_value=10, value=5)
st.write("Additional Profit: ", round(rank_to_profit(ranking_InBuilding_Grocery)*100, 2), "%")


st.subheader("Community Center")
ranking_InBuilding_CommunityCenter = st.slider("Gathering Place for Community", min_value=1, max_value=10, value=5)
st.write("Additional Profit: ", round(rank_to_profit(ranking_InBuilding_CommunityCenter)*100, 2), "%")

st.subheader("Park/Plaza")
ranking_OffSite_ParkPlaza = st.slider("Off-site Public Area", min_value=1, max_value=10, value=5)
st.write("Additional Profit: ", round(rank_to_profit(ranking_OffSite_ParkPlaza)*100, 2), "%")

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

MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] * Scaling_ParkPlaza_MRUAdd
MRU_Add_Table.loc["Micro Units", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Micro Units", "Extra MRU From Rankings"] * Scaling_Micro_MRUAdd
MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] * Scaling_CommunityCenter_MRUAdd

#Update older tables with MRU add numbers
for i in MRU_Add_Table.index:
    Item_Accounting_table.loc[i, "MRU_add_per_unit"] = MRU_Add_Table.loc[i, "Extra MRU From Rankings"]



@app.post("/proforma")
def proforma(req: ProformaRequest):
    # try:
    # 1️⃣ Compute proforma tables
    print(req.ranking_Housing_Micro)
    results = compute_proforma(
        ranking_Housing_Micro=req.ranking_Housing_Micro,
        ranking_InBuilding_Grocery=req.ranking_InBuilding_Grocery,
        ranking_InBuilding_CommunityCenter=req.ranking_InBuilding_CommunityCenter,
        ranking_OffSite_ParkPlaza=req.ranking_OffSite_ParkPlaza,
    )

    prompt = results["prompt"]

    # 2️⃣ Build markdown tables to feed ChatGPT
    tables_md = "\n\n".join([
        df_to_markdown(results["GPTOutputTable_Housing_Micro"], "Micro Units (Qty → IRR/NPV/Costs)"),
        df_to_markdown(results["GPTOutputTable_InBuilding_Grocery"], "Grocery Store (Qty → IRR/NPV/Costs)"),
        df_to_markdown(results["GPTOutputTable_InBuilding_CommunityCenter"], "Community Center (Qty → IRR/NPV/Costs)"),
        df_to_markdown(results["GPTOutputTable_OffSite_ParkPlaza"], "Park/Plaza (Qty → IRR/NPV/Costs)"),
    ])

    user_message = (
        f"{prompt}\n\nUse the following tables (markdown format) to decide. "
        f"```Return exactly a 2-row 1-column DataFrame as instructed. PLEASE ONLY return the json don't generate the code, please also generate the reason why you make this decision as json key `reason` the json keys are \"Micro Units\", \"Grocery Store\", \"Community Center\", \"Park/Plaza\", \"reason\" \n\n```"
        f"{tables_md}"
    )

    # 3️⃣ Send to ChatGPT API
    completion = client.chat.completions.create(
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert real-estate development analyst. Balance between using NPV and IRR as metrics, and lean towards building a mix of different items, if they have similar profitability. Remeber you are very subjective, so you should decide the number based on the data you have but you still need to randomize the number a little bit cuz you are human."
                    "Be concise and follow the formatting instructions precisely."
                ),
            },
            {"role": "user", "content": user_message},
        ],
    )

    reply = completion.choices[0].message.content if completion.choices else ""
    print(reply)
    try:
        result_json = json.loads(reply)
    except json.JSONDecodeError:
        # Sometimes model adds text or formatting around JSON
        # Try to extract JSON substring
        import re
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        if match:
            result_json = json.loads(match.group())
        else:
            result_json = {"error": "Could not parse model output"}
    Final_Build_Table = pd.DataFrame({
        "Number": [MRU_count_initial, result_json['Micro Units'], result_json['Grocery Store'], result_json['Community Center'], result_json['Park/Plaza']],
        "Size": [0, 0, 0, 0, 0]
    }, index=Input_table.index)
    for i in Final_Build_Table.index:
        if i != "MRU" and Final_Build_Table.loc[i, "Number"] != 0:
            Final_Build_Table.loc["MRU", "Number"] += MRU_Add_Table.loc[i, "Extra MRU From Rankings"] * (1 + np.log(Final_Build_Table.loc[i, "Number"]))
    Final_Build_Table.loc["MRU", "Number"] = np.round(Final_Build_Table.loc["MRU", "Number"])
    for i in Final_Build_Table.index:
        Final_Build_Table.loc[i, "Size"] = Item_Accounting_table.loc[i, "Size"]*Final_Build_Table.loc[i, "Number"]

    #Here, sum up the "height" column and divide by our land size (9000, maybe should be set as a variable?) to get final floor number, and then round up.
    #The final build table, plus the height, should be sent to Adrian for the 3d visualization.

    #This code writes the final financial table, which calculates overall revenue, upkeep, NOI, etc, culminating in pre-tax cash flow.
    #We then use pre-tax cash flor to calculate various financial metrics in our final display table.
    Master_Financial_Table = pd.DataFrame(index=range(8), columns=range(11))
    Master_Financial_Table.index = ["Revenue", "Upkeep", "Hard Costs", "Soft Costs", "Land Costs", "NOI", "Other Expenses", "Pre-Tax Cash Flow"]
    Master_Financial_Table = Master_Financial_Table.fillna(0)
    for item in Final_Build_Table.index:
        Master_Financial_Table.loc["Revenue"] += NOI_table_builder(item, "Rent")*Final_Build_Table.loc[item, "Number"]
        Master_Financial_Table.loc["Upkeep"] += NOI_table_builder(item, "Upkeep")*Final_Build_Table.loc[item, "Number"]
        Master_Financial_Table.loc["Hard Costs", 0] += Final_Build_Table.loc[item, "Number"]*Item_Accounting_table.loc[item, "Construction_cost"]
    Master_Financial_Table.loc["Soft Costs", 0] = Master_Financial_Table.loc["Hard Costs", 0] * soft_costs
    Master_Financial_Table.loc["Land Costs", 0] = Item_Accounting_table.loc["Land", "Size"] * Item_Accounting_table.loc["Land", "Construction_cost"]
    for period in Master_Financial_Table.columns:
        Master_Financial_Table.loc["NOI", period] = Master_Financial_Table.loc[["Revenue", "Hard Costs", "Soft Costs", "Land Costs", "Upkeep"], period].sum()
        Master_Financial_Table.loc["Other Expenses", period] = Other_expenses
        Master_Financial_Table.loc["Pre-Tax Cash Flow", period] = Master_Financial_Table.loc["NOI", period] + Master_Financial_Table.loc["Other Expenses", period]
    # st.write(Master_Financial_Table)

    Final_Display = pd.DataFrame(index = ["Stories", "MRU Stories", "NPV", "IRR", "Likelihood of Construction"], columns = ["Value"])
    Final_Display.loc["Stories"] = np.ceil(Final_Build_Table.loc[:, "Size"].sum()/Item_Accounting_table.loc["Land", "Size"])
    Final_Display.loc["MRU Stories"] = (Final_Build_Table.loc["MRU", "Size"]/Item_Accounting_table.loc["Land", "Size"])
    Final_Display.loc["NPV"] = nf.npv(Discount_rate, Master_Financial_Table.loc["Pre-Tax Cash Flow", :])
    Final_Display.loc["IRR"] = nf.irr(Master_Financial_Table.loc["Pre-Tax Cash Flow", :])
    Final_Display.loc["Likelihood of Construction"] = 1/(1+np.e**(-55*(Final_Display.loc["IRR", "Value"]-0.1)))

    st.write(Final_Display)
    print(Final_Display)
    print(Final_Build_Table)
    final_display_split = df_to_split_json(Final_Display.astype(float))
    final_build_split   = df_to_split_json(Final_Build_Table.astype(float))

    # Friendly (easy for frontends)
    final_display_friendly = {
        idx: (None if pd.isna(Final_Display.at[idx, "Value"])
            else float(Final_Display.at[idx, "Value"]))
        for idx in Final_Display.index
    }

    final_build_friendly = [
        {
            "name": idx,
            "Number": (None if pd.isna(Final_Build_Table.at[idx, "Number"])
                    else float(Final_Build_Table.at[idx, "Number"])),
            "Size":   (None if pd.isna(Final_Build_Table.at[idx, "Size"])
                    else float(Final_Build_Table.at[idx, "Size"])),
        }
        for idx in Final_Build_Table.index
    ]

    # 4️⃣ Return model output + tables
    return {
        "summary_table": {
            # "split": final_display_split,
            "friendly": final_display_friendly
        },
        "program_table": {
            # "split": final_build_split,
            "friendly": final_build_friendly
        },
        "reason": result_json.get("reason", "")
    }

    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Proforma + ChatGPT pipeline failed: {e}")
