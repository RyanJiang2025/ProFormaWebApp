from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, conint
from typing import Dict, Any
import pandas as pd
import numpy as np
import numpy_financial as nf
import os
import json
from openai import OpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # choose / override via env
client = OpenAI()

from proforma import (
    generate_gpt_tables,
    get_item_accounting_table,
    get_input_table,
    get_MRU_Add_table,
    get_Final_Build_Table,
    get_Master_Financial_Table,
    get_Final_Display,
    MRU_count_initial,
)

def df_to_compact_csv(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = [",".join(["metric"] + cols)]
    for r in df.index:
        vals = [f"{df.loc[r, c]:.6g}" for c in df.columns]
        lines.append(",".join([r] + vals))
    return "\n".join(lines)


def call_gpt_decider(city: str, eagerness: float, gpt_tables: dict) -> dict:
    t_aff = df_to_compact_csv(gpt_tables["Affordable Housing"])
    t_gro = df_to_compact_csv(gpt_tables["Grocery Store"])
    t_cc = df_to_compact_csv(gpt_tables["Community Center"])
    t_park = df_to_compact_csv(gpt_tables["Park/Plaza"])
    t_fund = df_to_compact_csv(gpt_tables["Fund"])

    system_msg = (
        f"You are a real estate developer working in San Francisco. "
        f"Below are financial tables for affordable housing, grocery stores, community centers, park/plazas, and neighborhood funds, showing IRR, NPV, and investment cost. "
        f"You are provided with a community eagerness score of {eagerness} (1 is low, 10 is high). "
        f"If the score is 1, do not build any amenities. If the score is 10, focus purely on financial profit. "
        f"For intermediate values, balance profit with community sentiment. "
        f"Do not exceed the quantities in the tables. Choose integer quantities (matching one of the column headers) for each amenity."
    )
    user_msg = f"""
City: {city}
Eagerness: {eagerness}

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
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def apply_plan(
    item_df: pd.DataFrame, mr_add: pd.DataFrame, plan: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    plan keys: 'Affordable Housing', 'Grocery Store', 'Community Center', 'Park/Plaza', 'Fund'
    Apply quantities, adjust Market Rate Housing via MRU-add, compute financials.
    """
    fb = pd.DataFrame(
        {"Number": [MRU_count_initial, 0, 0, 0, 0, 0], "Size": 0.0},
        index=[
            "Market Rate Housing",
            "Affordable Housing",
            "Grocery Store",
            "Community Center",
            "Park/Plaza",
            "Fund",
        ],
    )
    # Set GPT quantities (default to 0 if missing)
    fb.loc["Affordable Housing", "Number"] = int(plan.get("Affordable Housing", 0))
    fb.loc["Grocery Store", "Number"] = int(plan.get("Grocery Store", 0))
    fb.loc["Community Center", "Number"] = int(plan.get("Community Center", 0))
    fb.loc["Park/Plaza", "Number"] = int(plan.get("Park/Plaza", 0))
    fb.loc["Fund", "Number"] = int(plan.get("Fund", 0))

    # MRU-add → adjust MRH
    for idx in fb.index:
        if idx != "Market Rate Housing" and fb.loc[idx, "Number"] > 0:
            fb.loc["Market Rate Housing", "Number"] += mr_add.loc[
                idx, "Extra MRU From Rankings"
            ] * (1 + np.log(fb.loc[idx, "Number"]))

    fb.loc["Market Rate Housing", "Number"] = np.round(
        fb.loc["Market Rate Housing", "Number"]
    )

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
    grocery_store: conint(ge=1, le=10)
    community_center: conint(ge=1, le=10)
    park_plaza: conint(ge=1, le=10)
    fund: conint(ge=1, le=10)


class SimulationRequest(BaseModel):
    rankings: Rankings
    gpt_decide: bool = False
    city: str = "San Francisco"
    eagerness: float = 5  # Community eagerness score (1 = low, 10 = high)


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


def first6(df: pd.DataFrame, metric: str) -> list[float]:
    cols = sorted(df.columns)[:6]
    return [float(df.loc[metric, c]) for c in cols]

@app.post("/simulate")
def simulate(payload: SimulationRequest):
    # 1) Build core tables
    item = get_item_accounting_table()
    rankings_map = {
        "Affordable Housing": int(payload.rankings.affordable_housing),
        "Grocery Store": int(payload.rankings.grocery_store),
        "Community Center": int(payload.rankings.community_center),
        "Park/Plaza": int(payload.rankings.park_plaza),
        "Fund": int(payload.rankings.fund),
    }
    inp = get_input_table(item, rankings_map)
    mr = get_MRU_Add_table(item, inp)

    # 2) Precompute GPT charts (always useful for frontend plots)
    gpt = generate_gpt_tables(item, mr)
    irr_series = {
        "Affordable Housing": first6(gpt["Affordable Housing"], "IRR"),
        "Grocery Store": first6(gpt["Grocery Store"], "IRR"),
        "Community Center": first6(gpt["Community Center"], "IRR"),
        "Park/Plaza": first6(gpt["Park/Plaza"], "IRR"),
        "Fund": first6(gpt["Fund"], "IRR"),
    }
    npv_series = {
        "Affordable Housing": first6(gpt["Affordable Housing"], "NPV"),
        "Grocery Store": first6(gpt["Grocery Store"], "NPV"),
        "Community Center": first6(gpt["Community Center"], "NPV"),
        "Park/Plaza": first6(gpt["Park/Plaza"], "NPV"),
        "Fund": first6(gpt["Fund"], "NPV"),
    }

    gpt_decision = None
    gpt_rationale = None
    fb = get_Final_Build_Table(item, inp, mr)  # default baseline (amenities zero)
    mf = get_Master_Financial_Table(item, fb)
    fd = get_Final_Display(item, fb, mf)

    # 3) If GPT-decide, replace baseline with GPT plan
    if payload.gpt_decide:
        gpt_out = call_gpt_decider(
            payload.city, payload.eagerness, gpt
        )  # actual open api call
        gpt_decision = gpt_out.get("decision", {})
        gpt_rationale = gpt_out.get("rationale", "")

        fb, mf, fd = apply_plan(item, mr, gpt_decision)

    # 4) Return one response
    return {
        "item_accounting_table": df_split(item),
        "input_table": df_split(inp),
        "mru_add_table": df_split(mr),
        "irr_series_first6": irr_series,
        "npv_series_first6": npv_series,
        "gpt_decision": gpt_decision,  # null if gpt_decide=False
        "gpt_rationale": gpt_rationale,  # null if gpt_decide=False
        "final_build_table": df_split(fb),
        "master_financial_table": df_split(mf),
        "final_display": df_split(fd),
    }
