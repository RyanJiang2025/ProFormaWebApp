from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, conint
from typing import Dict, Any
import pandas as pd
import numpy as np
import numpy_financial as nf

# ======================
# CONSTANTS / PARAMETERS
# ======================
Scaling_Grocery_Rent = 0.1
Scaling_ParkPlaza_MRUAdd = 2.15
Scaling_AffordableHousing_MRUAdd = 0.75
Scaling_CommunityCenter_MRUAdd = 0.75
Scaling_Fund_MRUAdd = 1

MRU_count_initial = 48
soft_costs = 0.22
Rent_increase = 0.10
Upkeep_increase = 0.04
Other_expenses = -500
Discount_rate = 0.08
Market_rent_sqft = 4
Exit_value_multiple = 20


import os, json
from openai import OpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # choose / override via env
client = OpenAI()


def df_to_compact_csv(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = [",".join(["metric"] + cols)]
    for r in df.index:
        vals = [f"{df.loc[r, c]:.6g}" for c in df.columns]
        lines.append(",".join([r] + vals))
    return "\n".join(lines)

def call_gpt_decider(city: str, gpt_tables: dict) -> dict:
    t_aff = df_to_compact_csv(gpt_tables["Affordable Housing"])
    t_gro = df_to_compact_csv(gpt_tables["Grocery Store"])
    t_cc  = df_to_compact_csv(gpt_tables["Community Center"])
    t_park= df_to_compact_csv(gpt_tables["Park/Plaza"])
    t_fund= df_to_compact_csv(gpt_tables["Fund"])

    system_msg = (
        "You are a pragmatic real-estate developer. "
        "Choose integer quantities (must be one of the column headers) per amenity. "
        "Favor higher NPV with reasonable IRR."
    )
    user_msg = f"""
City: {city}
Return STRICT JSON only:

{{
  "decision": {{
    "Affordable Housing": <int>,
    "Grocery Store": <int>,
    "Community Center": <int>,
    "Park/Plaza": <int>,
    "Fund": <int>
  }},
  "rationale": "<short explanation>"
}}

Tables (CSV):

[Affordable Housing]
{t_aff}

[Grocery Store]
{t_gro}

[Community Center]
{t_cc}

[Park/Plaza]
{t_park}

[Fund]
{t_fund}
"""

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[{"role":"system","content":system_msg},
                  {"role":"user","content":user_msg}],
    )
    return json.loads(resp.choices[0].message.content)


def apply_plan(item_df: pd.DataFrame, mr_add: pd.DataFrame, plan: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    plan keys: 'Affordable Housing', 'Grocery Store', 'Community Center', 'Park/Plaza', 'Fund'
    Apply quantities, adjust Market Rate Housing via MRU-add, compute financials.
    """
    fb = pd.DataFrame(
        {"Number": [MRU_count_initial, 0, 0, 0, 0, 0], "Size": 0.0},
        index=["Market Rate Housing", "Affordable Housing", "Grocery Store", "Community Center", "Park/Plaza", "Fund"]
    )
    # Set GPT quantities (default to 0 if missing)
    fb.loc["Affordable Housing", "Number"] = int(plan.get("Affordable Housing", 0))
    fb.loc["Grocery Store", "Number"]      = int(plan.get("Grocery Store", 0))
    fb.loc["Community Center", "Number"]   = int(plan.get("Community Center", 0))
    fb.loc["Park/Plaza", "Number"]         = int(plan.get("Park/Plaza", 0))
    fb.loc["Fund", "Number"]               = int(plan.get("Fund", 0))

    # MRU-add → adjust MRH
    for idx in fb.index:
        if idx != "Market Rate Housing" and fb.loc[idx, "Number"] > 0:
            fb.loc["Market Rate Housing", "Number"] += mr_add.loc[idx, "Extra MRU From Rankings"] * (1 + np.log(fb.loc[idx, "Number"]))

    fb.loc["Market Rate Housing", "Number"] = np.round(fb.loc["Market Rate Housing", "Number"])

    # sizes
    for idx in fb.index:
        fb.loc[idx, "Size"] = item_df.loc[idx, "Size"] * fb.loc[idx, "Number"]

    mf = get_Master_Financial_Table(item_df, fb)
    fd = get_Final_Display(item_df, fb, mf)
    return fb, mf, fd


# ======================
# Pydantic Schemas
# ======================


class Rankings(BaseModel):
    affordable_housing: conint(ge=1, le=10)
    grocery_store:      conint(ge=1, le=10)
    community_center:   conint(ge=1, le=10)
    park_plaza:         conint(ge=1, le=10)
    fund:               conint(ge=1, le=10)

class SimulationRequest(BaseModel):
    rankings: Rankings
    gpt_decide: bool = False
    city: str = "San Francisco"

# ======================
# Utility
# ======================
def rank_to_profit(rank: int) -> float:
    return rank * 0.2  # linear mapping

def df_split(df: pd.DataFrame) -> Dict[str, Any]:
    """Return a JSON-serializable dict using pandas 'split' orient."""
    return df.to_dict(orient="split")

class DecideRequest(BaseModel):
    rankings: Rankings
    city: str = "San Francisco"


# ======================
# Calculation Functions
# ======================
def get_item_accounting_table() -> pd.DataFrame:
    Item_Accounting_table = {
        "Size": [9000, 750, 750, 7500, 20000, 0, 0],
        "Rent_yearly": [0, 36000, 18000, 300000, 0, 0, 0],
        "Construction_cost": [-900, -375000, -375000, -2750000, -10000000, -4500000, 0],
        "Soft_Costs": [0, 0, 0, 0, 0, 0, 0],
        "Upkeep_yearly": [0, -6000, -6000, -82500, -472000, -125000, -100000],
        "MRU_add_per_unit": [0, 0, 0, 0, 0, 0, 0],
    }
    df = pd.DataFrame(Item_Accounting_table)
    df.index = ["Land", "Market Rate Housing", "Affordable Housing", "Grocery Store", "Community Center", "Park/Plaza", "Fund"]
    for i in df.index:
        df.loc[i, "Soft_Costs"] = df.loc[i, "Construction_cost"] * soft_costs
    df.loc["Grocery Store", "Rent_yearly"] = df.loc["Grocery Store", "Rent_yearly"] * Scaling_Grocery_Rent
    return df

def get_input_table(item_df: pd.DataFrame, r: Rankings) -> pd.DataFrame:
    Input_table = {
        "Units/Rank": [
            MRU_count_initial,
            r.affordable_housing,
            r.grocery_store,
            r.community_center,
            r.park_plaza,
            r.fund,
        ],
        "Net Profit/Year/SqFt": [0, 0, 0, 0, 0, 0],
    }
    df = pd.DataFrame(Input_table, index=["Market Rate Housing", "Affordable Housing", "Grocery Store", "Community Center", "Park/Plaza", "Fund"])
    for i in item_df.index[1:]:
        if item_df.loc[i, "Size"] != 0:
            df.loc[i, "Net Profit/Year/SqFt"] = (item_df.loc[i, "Rent_yearly"] + item_df.loc[i, "Upkeep_yearly"]) / item_df.loc[i, "Size"]
        else:
            df.loc[i, "Net Profit/Year/SqFt"] = 0
    return df

def NOI_table_builder(item_df: pd.DataFrame, item_type: str, return_type: str) -> pd.Series | pd.DataFrame:
    NoiTable = np.zeros((3, 11), dtype=float)
    NoiTable[2, 0] = item_df.loc[item_type, "Construction_cost"] * (1 + soft_costs)
    NoiTable[0, 1] = item_df.loc[item_type, "Rent_yearly"]
    NoiTable[1, 1] = item_df.loc[item_type, "Upkeep_yearly"]
    for i in range(2, 11):
        NoiTable[0, i] = NoiTable[0, i - 1] * (1 + Rent_increase)
        NoiTable[1, i] = NoiTable[1, i - 1] * (1 + Upkeep_increase)
    NoiTable[0, 10] = NoiTable[0, 10] * (Exit_value_multiple + 1)  # exit
    for i in range(1, 11):
        NoiTable[2, i] = NoiTable[0, i] + NoiTable[1, i]
    df = pd.DataFrame(NoiTable, index=["Rent", "Upkeep", "NOI"])
    if return_type in ["Rent", "Upkeep", "NOI"]:
        return df.loc[return_type]
    return df

def get_MRU_Add_table(item_df: pd.DataFrame, input_df: pd.DataFrame) -> pd.DataFrame:
    mr = pd.DataFrame(0.0, index=input_df.index, columns=["NPV/SqFt", "MRU Break Even", "Scaled for Size", "Extra MRU From Rankings"])
    for i in mr.index:
        if item_df.loc[i, "Size"] != 0:
            mr.loc[i, "NPV/SqFt"] = nf.npv(Discount_rate, NOI_table_builder(item_df, i, "NOI")) / item_df.loc[i, "Size"]
            if i == "Market Rate Housing":
                mr.loc[i, ["MRU Break Even", "Scaled for Size", "Extra MRU From Rankings"]] = 0
            else:
                mr.loc[i, "MRU Break Even"] = (mr.loc["Market Rate Housing", "NPV/SqFt"] - mr.loc[i, "NPV/SqFt"]) / mr.loc["Market Rate Housing", "NPV/SqFt"]
                mr.loc[i, "Scaled for Size"] = mr.loc[i, "MRU Break Even"] * item_df.loc[i, "Size"] / item_df.loc["Market Rate Housing", "Size"]
                mr.loc[i, "Extra MRU From Rankings"] = mr.loc[i, "Scaled for Size"] * rank_to_profit(int(input_df.loc[i, "Units/Rank"]))
        else:
            mr.loc[i, "NPV/SqFt"] = 0
            mr.loc[i, "MRU Break Even"] = (
                nf.npv(Discount_rate, NOI_table_builder(item_df, "Market Rate Housing", "NOI"))
                - nf.npv(Discount_rate, NOI_table_builder(item_df, i, "NOI"))
            ) / nf.npv(Discount_rate, NOI_table_builder(item_df, "Market Rate Housing", "NOI"))
            mr.loc[i, "Scaled for Size"] = mr.loc[i, "MRU Break Even"]
            mr.loc[i, "Extra MRU From Rankings"] = mr.loc[i, "Scaled for Size"] * rank_to_profit(int(input_df.loc[i, "Units/Rank"]))

    # Scaling
    mr.loc["Park/Plaza", "Extra MRU From Rankings"] *= Scaling_ParkPlaza_MRUAdd
    mr.loc["Affordable Housing", "Extra MRU From Rankings"] *= Scaling_AffordableHousing_MRUAdd
    mr.loc["Community Center", "Extra MRU From Rankings"] *= Scaling_CommunityCenter_MRUAdd
    mr.loc["Fund", "Extra MRU From Rankings"] *= Scaling_Fund_MRUAdd

    # mirror back to item_df (not required for API, but kept for parity)
    for i in mr.index:
        item_df.loc[i, "MRU_add_per_unit"] = mr.loc[i, "Extra MRU From Rankings"]

    return mr

def GPTOutputTable_Builder(item_df: pd.DataFrame, mr_add: pd.DataFrame, min_units: int, max_units: int, step: int, item: str) -> pd.DataFrame:
    cols = list(range(min_units, max_units, step))
    if 0 not in cols:
        cols = [0] + cols
    cols = sorted(cols)
    out = pd.DataFrame(0.0, index=["IRR", "NPV", "Costs"], columns=pd.Index(cols, dtype=int))
    for i in cols:
        if i == 0:
            continue
        log_arg = max(i, 1)
        MRUAdd = mr_add.loc[item, "Extra MRU From Rankings"] * (1 + np.log(log_arg))
        NOITable = NOI_table_builder(item_df, "Market Rate Housing", "NOI") * MRUAdd + NOI_table_builder(item_df, item, "NOI") * i
        out.at["IRR", i] = nf.irr(NOITable)
        out.at["NPV", i] = nf.npv(Discount_rate, NOITable)
        out.at["Costs", i] = (
            (item_df.loc["Market Rate Housing", "Construction_cost"] + item_df.loc["Market Rate Housing", "Soft_Costs"]) * MRUAdd
            + (item_df.loc[item, "Construction_cost"] + item_df.loc[item, "Soft_Costs"]) * i
        )
    return out

def generate_gpt_tables(item_df: pd.DataFrame, mr_add: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    return {
        "Affordable Housing": GPTOutputTable_Builder(item_df, mr_add, 5, 51, 5, "Affordable Housing"),
        "Grocery Store":      GPTOutputTable_Builder(item_df, mr_add, 0, 6, 1, "Grocery Store"),
        "Community Center":   GPTOutputTable_Builder(item_df, mr_add, 0, 6, 1, "Community Center"),
        "Park/Plaza":         GPTOutputTable_Builder(item_df, mr_add, 0, 6, 1, "Park/Plaza"),
        "Fund":               GPTOutputTable_Builder(item_df, mr_add, 0, 21, 1, "Fund"),
    }

def get_Final_Build_Table(item_df: pd.DataFrame, input_df: pd.DataFrame, mr_add: pd.DataFrame) -> pd.DataFrame:
    fb = pd.DataFrame({"Number": [MRU_count_initial, 0, 0, 0, 0, 0], "Size": [0, 0, 0, 0, 0, 0]}, index=input_df.index)
    for i in fb.index:
        if i != "Market Rate Housing" and fb.loc[i, "Number"] != 0:
            fb.loc["Market Rate Housing", "Number"] += mr_add.loc[i, "Extra MRU From Rankings"] * (1 + np.log(fb.loc[i, "Number"]))
    fb.loc["Market Rate Housing", "Number"] = np.round(fb.loc["Market Rate Housing", "Number"])
    for i in fb.index:
        fb.loc[i, "Size"] = item_df.loc[i, "Size"] * fb.loc[i, "Number"]
    return fb

def get_Master_Financial_Table(item_df: pd.DataFrame, fb: pd.DataFrame) -> pd.DataFrame:
    m = pd.DataFrame(0.0, index=["Revenue", "Upkeep", "Hard Costs", "Soft Costs", "Land Costs", "NOI", "Other Expenses", "Pre-Tax Cash Flow"], columns=range(11))
    for item in fb.index:
        m.loc["Revenue"] += NOI_table_builder(item_df, item, "Rent") * fb.loc[item, "Number"]
        m.loc["Upkeep"]  += NOI_table_builder(item_df, item, "Upkeep") * fb.loc[item, "Number"]
        m.loc["Hard Costs", 0] += fb.loc[item, "Number"] * item_df.loc[item, "Construction_cost"]
    m.loc["Soft Costs", 0] = m.loc["Hard Costs", 0] * soft_costs
    m.loc["Land Costs", 0] = item_df.loc["Land", "Size"] * item_df.loc["Land", "Construction_cost"]
    for period in m.columns:
        m.loc["NOI", period] = m.loc[["Revenue", "Hard Costs", "Soft Costs", "Land Costs", "Upkeep"], period].sum()
        m.loc["Other Expenses", period] = Other_expenses
        m.loc["Pre-Tax Cash Flow", period] = m.loc["NOI", period] + m.loc["Other Expenses", period]
    return m

def get_Final_Display(item_df: pd.DataFrame, fb: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    fd = pd.DataFrame(index=["Stories", "Market Rate Housing Stories", "NPV", "IRR", "Likelihood of Construction"], columns=["Value"])
    fd.loc["Stories"] = np.ceil(fb.loc[:, "Size"].sum() / item_df.loc["Land", "Size"])
    fd.loc["Market Rate Housing Stories"] = (fb.loc["Market Rate Housing", "Size"] / item_df.loc["Land", "Size"])
    fd.loc["NPV"] = nf.npv(Discount_rate, m.loc["Pre-Tax Cash Flow", :])
    fd.loc["IRR"] = nf.irr(m.loc["Pre-Tax Cash Flow", :])
    fd.loc["Likelihood of Construction"] = 1 / (1 + np.e ** (-55 * (float(fd.loc["IRR", "Value"]) - 0.135)))
    return fd

def first6(series_df: pd.DataFrame, row: str) -> list[float]:
    cols = sorted([c for c in series_df.columns if isinstance(c, (int, float))])[:6]
    return series_df.loc[row, cols].tolist()

# ======================
# FastAPI App
# ======================
app = FastAPI(title="Dynamic Zoning Simulation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/simulate")
def simulate(payload: SimulationRequest):
    # 1) Build core tables
    item = get_item_accounting_table()
    inp  = get_input_table(item, payload.rankings)
    mr   = get_MRU_Add_table(item, inp)

    # 2) Precompute GPT charts (always useful for frontend plots)
    gpt  = generate_gpt_tables(item, mr)
    irr_series = {
        "Affordable Housing": first6(gpt["Affordable Housing"], "IRR"),
        "Grocery Store":      first6(gpt["Grocery Store"], "IRR"),
        "Community Center":   first6(gpt["Community Center"], "IRR"),
        "Park/Plaza":         first6(gpt["Park/Plaza"], "IRR"),
        "Fund":               first6(gpt["Fund"], "IRR"),
    }
    npv_series = {
        "Affordable Housing": first6(gpt["Affordable Housing"], "NPV"),
        "Grocery Store":      first6(gpt["Grocery Store"], "NPV"),
        "Community Center":   first6(gpt["Community Center"], "NPV"),
        "Park/Plaza":         first6(gpt["Park/Plaza"], "NPV"),
        "Fund":               first6(gpt["Fund"], "NPV"),
    }

    gpt_decision = None
    gpt_rationale = None
    fb = get_Final_Build_Table(item, inp, mr)  # default baseline (amenities zero)
    mf = get_Master_Financial_Table(item, fb)
    fd = get_Final_Display(item, fb, mf)

    # 3) If GPT-decide, replace baseline with GPT plan
    if payload.gpt_decide:
        gpt_out = call_gpt_decider(payload.city, gpt)
        gpt_decision = gpt_out.get("decision", {})
        gpt_rationale = gpt_out.get("rationale", "")

        fb, mf, fd = apply_plan(item, mr, gpt_decision)

    # 4) Return one response
    return {
        "item_accounting_table":  df_split(item),
        "input_table":            df_split(inp),
        "mru_add_table":          df_split(mr),

        "irr_series_first6":      irr_series,
        "npv_series_first6":      npv_series,

        "gpt_decision":           gpt_decision,     # null if gpt_decide=False
        "gpt_rationale":          gpt_rationale,    # null if gpt_decide=False

        "final_build_table":      df_split(fb),
        "master_financial_table": df_split(mf),
        "final_display":          df_split(fd),
    }


@app.post("/decide")
def decide(payload: DecideRequest):
    """
    1) Run the same calculations as /simulate to produce GPT tables.
    2) Ask GPT to select a build plan (integers per amenity).
    3) Return the decision + rationale + (optional) echo of tables.
    """
    # --- 1) same math as /simulate up to GPT tables ---
    item = get_item_accounting_table()
    inp  = get_input_table(item, payload.rankings)
    mr   = get_MRU_Add_table(item, inp)
    gpt  = generate_gpt_tables(item, mr)

    # gpt tables keyed exactly as your frontend expects
    t_affordable = gpt["Affordable Housing"]
    t_grocery    = gpt["Grocery Store"]
    t_cc         = gpt["Community Center"]
    t_park       = gpt["Park/Plaza"]
    t_fund       = gpt["Fund"]

    # --- 2) GPT chooses plan ---
    gpt_out = call_gpt_decider(
        city=payload.city,
        t_affordable=t_affordable,
        t_grocery=t_grocery,
        t_cc=t_cc,
        t_park=t_park,
        t_fund=t_fund,
    )

    # (Optional) if you want to immediately compute a build using GPT’s plan,
    # you can apply it to Final_Build_Table here. For now, we just return the decision.

    return {
        "decision": gpt_out.get("decision", {}),
        "rationale": gpt_out.get("rationale", ""),
        "tables": {
            "Affordable Housing": df_split(t_affordable),
            "Grocery Store":      df_split(t_grocery),
            "Community Center":   df_split(t_cc),
            "Park/Plaza":         df_split(t_park),
            "Fund":               df_split(t_fund),
        },
    }

