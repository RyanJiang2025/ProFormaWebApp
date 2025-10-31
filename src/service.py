from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, conint, create_model
from typing import Dict, Any
import pandas as pd
import numpy as np
import os
import json
from openai import OpenAI

from proforma import (
    generate_gpt_tables,
    get_item_accounting_table,
    get_input_table,
    get_MRU_Add_table,
    get_Final_Build_Table,
    get_Master_Financial_Table,
    get_Final_Display,
    MRU_count_initial,
    get_amenity_name,
    AMENITY_NAME_LIST,
    to_snake_case,
)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # choose / override via env
client = OpenAI()


def df_to_compact_csv(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = [",".join(["metric"] + cols)]
    for r in df.index:
        vals = [f"{df.loc[r, c]:.6g}" for c in df.columns]
        lines.append(",".join([r] + vals))
    return "\n".join(lines)


def call_gpt_decider(city: str, eagerness: float, gpt_tables: dict) -> dict:
    # Get amenity names dynamically
    amenity_names = [get_amenity_name(i) for i in range(1, 6)]
    tables_csv = [df_to_compact_csv(gpt_tables[name]) for name in amenity_names]

    # Build decision JSON structure dynamically
    decision_keys = ", ".join([f'"{name}": <int>' for name in amenity_names])
    
    # Build table sections
    table_sections = "\n\n".join([f"[{name}]\n{tbl}" for name, tbl in zip(amenity_names, tables_csv)])

    system_msg = (
        f"You are a real estate developer working in San Francisco. "
        f"Below are financial tables for five different amenities ({', '.join(amenity_names)}), showing IRR, NPV, and investment cost. "
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
    {decision_keys}
  }},
  "rationale": "<short explanation>"
}}

Tables (CSV):

{table_sections}
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
    plan keys: uses amenity names from proforma.AMENITY_NAMES
    Apply quantities, adjust Market Rate Housing via MRU-add, compute financials.
    """
    amenity_names = [get_amenity_name(i) for i in range(1, 6)]
    fb = pd.DataFrame(
        {"Number": [MRU_count_initial, 0, 0, 0, 0, 0], "Size": 0.0},
        index=["Market Rate Housing"] + amenity_names,
    )
    # Set GPT quantities (default to 0 if missing)
    for name in amenity_names:
        fb.loc[name, "Number"] = int(plan.get(name, 0))

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


# Dynamically create Rankings model based on AMENITY_NAMES
# This allows the model to use whatever amenity names are defined in proforma
_rankings_fields = {}
for i in range(1, 6):
    name = get_amenity_name(i)
    snake_name = to_snake_case(name)
    _rankings_fields[snake_name] = conint(ge=1, le=10)

# Use create_model for proper Pydantic model creation
Rankings = create_model('Rankings', **_rankings_fields)


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
    
    # Build rankings_map dynamically using amenity names
    rankings_map = {}
    for i in range(1, 6):
        display_name = get_amenity_name(i)
        snake_name = to_snake_case(display_name)
        rankings_map[display_name] = int(getattr(payload.rankings, snake_name))
    
    inp = get_input_table(item, rankings_map)
    mr = get_MRU_Add_table(item, inp)

    # 2) Precompute GPT charts (always useful for frontend plots)
    gpt = generate_gpt_tables(item, mr)
    irr_series = {name: first6(gpt[name], "IRR") for name in AMENITY_NAME_LIST}
    npv_series = {name: first6(gpt[name], "NPV") for name in AMENITY_NAME_LIST}

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
