# To run: streamlit run [filename].py in terminal

# Changes: scaling, making sliders more sensitive (20 --> 30% max)
# Compared to current version of Proforma_WebApp_V1.0.py: added incentive on/off buttons

import streamlit as st
import pandas as pd
import altair as alt
import requests

from proforma import generate_gpt_tables

st.set_page_config(layout="wide")

import os

# this script assumes that the proforma is working
API_URL = os.getenv("API_URL", "http://proforma.media.mit.edu:50053")
ENDPOINT = "simulate"
# or your container/remote URL

# Sliders. Change code here (specifically st.slider) when using the physical slider.

from proforma import rank_to_profit


def get_ranking_functions():
    """Returns all ranking functions as a tuple for assignment to variables outside the function."""
    # if st.session_state.toggle:
    st.subheader("Affordable Housing (1 unit = 5 housing units)")
    ranking_Housing_Affordable = st.slider(
        "Subsidized Rent by 50%. Otherwise the same as a Market Rate Unit",
        min_value=1,
        max_value=10,
        value=5,
    )
    st.write(
        "Developer Compensation Rate: ",
        round(rank_to_profit(ranking_Housing_Affordable) * 100, 2),
        "%",
    )

    st.subheader("Grocery Store")
    ranking_InBuilding_Grocery = st.slider(
        "On-Site Grocery Store", min_value=1, max_value=10, value=5
    )
    st.write(
        "Developer Compensation Rate: ",
        round(rank_to_profit(ranking_InBuilding_Grocery) * 100, 2),
        "%",
    )

    st.subheader("Community Center")
    ranking_InBuilding_CommunityCenter = st.slider(
        "Multipurpose rooms for community events: think cultural activities, workshops, etc.",
        min_value=1,
        max_value=10,
        value=5,
    )
    st.write(
        "Developer Compensation Rate: ",
        round(rank_to_profit(ranking_InBuilding_CommunityCenter) * 100, 2),
        "%",
    )

    st.subheader("Park/Plaza")
    ranking_OffSite_ParkPlaza = st.slider(
        "Off-site Public Area, Open Air Space", min_value=1, max_value=10, value=5
    )
    st.write(
        "Developer Compensation Rate: ",
        round(rank_to_profit(ranking_OffSite_ParkPlaza) * 100, 2),
        "%",
    )

    st.subheader("Community Fund (1 unit = $100,000)")
    ranking_Fund = st.slider(
        "Fund for community improvements. Paid for in incremenets of $100,000.",
        min_value=1,
        max_value=10,
        value=5,
    )
    st.write(
        "Developer Compensation Rate: ",
        round(rank_to_profit(ranking_Fund) * 100, 2),
        "%",
    )

    return (
        ranking_Housing_Affordable,
        ranking_InBuilding_Grocery,
        ranking_InBuilding_CommunityCenter,
        ranking_OffSite_ParkPlaza,
        ranking_Fund,
    )


from proforma import (  # is this needed?
    get_item_accounting_table,
    get_input_table,
    get_MRU_Add_table,
)


def _first_six_irrs(
    df: pd.DataFrame,
) -> list[
    float
]:  # captures the first 6 values (i.e. 0-5 of an amenity) for charting purposes
    # ensure columns are sorted numerically, then take first six
    cols = sorted(df.columns)[:6]
    return df.loc["IRR", cols].tolist()


def create_irr_chart(gpt_tables):
    """Creates and returns the IRR chart for all amenities."""
    IRR_first6 = pd.DataFrame(
        [
            _first_six_irrs(gpt_tables["Affordable Housing"]),
            _first_six_irrs(gpt_tables["Grocery Store"]),
            _first_six_irrs(gpt_tables["Community Center"]),
            _first_six_irrs(gpt_tables["Park/Plaza"]),
            _first_six_irrs(gpt_tables["Fund"]),
        ],
        index=[
            "Affordable Housing",
            "Grocery Store",
            "Community Center",
            "Park/Plaza",
            "Fund",
        ],
        columns=[str(i) for i in range(6)],
    )
    IRR_first6_long = (  # chart is reformatted
        IRR_first6.reset_index()
        .melt(id_vars="index", var_name="Period", value_name="IRR")
        .rename(columns={"index": "Amenity"})
    )
    chart = (
        alt.Chart(IRR_first6_long)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "Period:Q", title="Quantity Built"
            ),  # if your columns are unit counts, use ':Q' and title='Units'
            y=alt.Y(
                "IRR:Q", title="Internal Rate of Return", axis=alt.Axis(format="%")
            ),
            color=alt.Color("Amenity:N", title="Amenity"),
            tooltip=["Amenity", "Period", alt.Tooltip("IRR:Q", format=".2%")],
        )
        .properties(height=380)
        .interactive()
    )
    return chart


# Helper: extract first 6 NPV values from a GPTOutputTable
def _first_six_npvs(df: pd.DataFrame) -> list[float]:
    cols = sorted(df.columns)[:6]  # first 6 columns (periods)
    return df.loc["NPV", cols].tolist()


def create_npv_chart(gpt_tables):
    """Creates and returns the NPV chart for all amenities."""
    NPV_first6 = pd.DataFrame(
        [
            _first_six_npvs(gpt_tables["Affordable Housing"]),
            _first_six_npvs(gpt_tables["Grocery Store"]),
            _first_six_npvs(gpt_tables["Community Center"]),
            _first_six_npvs(gpt_tables["Park/Plaza"]),
            _first_six_npvs(gpt_tables["Fund"]),
        ],
        index=[
            "Affordable Housing",
            "Grocery Store",
            "Community Center",
            "Park/Plaza",
            "Fund",
        ],
        columns=[str(i) for i in range(6)],
    )
    NPV_first6_long = (
        NPV_first6.reset_index()
        .melt(id_vars="index", var_name="Period", value_name="NPV")
        .rename(columns={"index": "Amenity"})
    )
    chart = (
        alt.Chart(NPV_first6_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("Period:Q", title="Quantity Built"),
            y=alt.Y("NPV:Q", title="Net Present Value", axis=alt.Axis(format="$,.0f")),
            color=alt.Color("Amenity:N", title="Amenity"),
            tooltip=["Amenity", "Period", alt.Tooltip("NPV:Q", format="$,.0f")],
        )
        .properties(height=380)
        .interactive()
    )
    return chart


# =============================================================================
# GAME FRAMEWORK
# =============================================================================

# Initialize session state for game progression
if "game_state" not in st.session_state:
    st.session_state.game_state = "start"
if "current_round" not in st.session_state:
    st.session_state.current_round = 1
if "game_results" not in st.session_state:
    st.session_state.game_results = []


def start_screen():
    """Display the game start screen."""
    st.title("🏗️ Dynamic Zoning Simulation")
    st.markdown("### Welcome to the Dynamic Zoning Simulation!")

    # Get player name
    player_name = st.text_input("Enter your name (optional):", value="")

    st.markdown("""
    **Game Overview:**
    - You'll play 5 rounds as a member of the community. Each round is a new project in your neighborhood.
    - For each project, you'll set priorities for community benefits, deciding on a scale of 1 (low) to 10 (high) how much you prioritize each amenity.
    - Your decisions will determine financial incentives for developers, affecting what gets built.
    - See what happens to the project over time!
    """)

    if st.button("🚀 Start Game", type="primary", use_container_width=True):
        if player_name:
            st.session_state.player_name = player_name
        else:
            st.session_state.player_name = "Player"
        st.session_state.game_state = "input"
        st.rerun()


def input_stage():
    """Decide the Community Priorities for this Round."""
    st.title(f"Round {st.session_state.current_round} - Set Your Priorities")
    st.markdown(
        "Set your priorities and see how they affect financial outcomes (1=low, 10=high)."
    )
    st.markdown(
        "100% = developer breaks even on building the (first) amenity, <100% = loss, >100% = profit. Subsidy decreases with each additional amenity built."
    )

    # Display cumulative progress from previous rounds
    if len(st.session_state.game_results) > 0:
        st.subheader("📊 Cumulative Progress So Far")

        # Aggregate built items from all previous rounds
        cumulative_built = {
            "Market Rate Housing": 0,
            "Affordable Housing": 0,
            "Grocery Store": 0,
            "Community Center": 0,
            "Park/Plaza": 0,
            "Fund": 0,
        }

        for result in st.session_state.game_results:
            for amenity, count in result["built_items"].items():
                cumulative_built[amenity] += count

        # Create a DataFrame for the chart
        progress_data = []
        for amenity, count in cumulative_built.items():
            progress_data.append({"Amenity": amenity, "Quantity": count})
        progress_df = pd.DataFrame(progress_data)

        # Display dataframe instead of chart
        st.dataframe(progress_df)

    # Create two columns: left for sliders, right for charts
    col_sliders, col_charts = st.columns([1, 1])

    with col_sliders:
        # Call the ranking functions to get the sliders - all sliders render here
        (
            ranking_Housing_Affordable,
            ranking_InBuilding_Grocery,
            ranking_InBuilding_CommunityCenter,
            ranking_OffSite_ParkPlaza,
            ranking_Fund,
        ) = get_ranking_functions()

    # Store the rankings for this round (outside columns so accessible later)
    round_rankings = {
        "round": st.session_state.current_round,
        "rankings": {
            "Affordable Housing": ranking_Housing_Affordable,
            "Grocery Store": ranking_InBuilding_Grocery,
            "Community Center": ranking_InBuilding_CommunityCenter,
            "Park/Plaza": ranking_OffSite_ParkPlaza,
            "Fund": ranking_Fund,
        },
    }

    st.session_state.current_rankings = round_rankings

    # Generate tables and charts for preview (using the slider values from session state)
    Item_Accounting_table = get_item_accounting_table()
    Input_table = get_input_table(
        Item_Accounting_table, st.session_state.current_rankings["rankings"]
    )
    MRU_Add_Table = get_MRU_Add_table(Item_Accounting_table, Input_table)
    gpt_tables = generate_gpt_tables(Item_Accounting_table, MRU_Add_Table)

    with col_charts:
        st.subheader("📈 Financial Analysis")
        st.markdown("**Internal Rate of Return (IRR)**")
        st.altair_chart(create_irr_chart(gpt_tables), use_container_width=True)

        st.markdown("**Net Present Value (NPV)**")
        st.altair_chart(create_npv_chart(gpt_tables), use_container_width=True)

    # Display item accounting table at the bottom
    with st.expander("Item Accounting Details"):
        st.dataframe(Item_Accounting_table)

    # ================================
    # API Call Here
    # ================================

    # API should take in variable "gpt_tables" and the following prompt:
    # "You are a real estate developer in San Francisco. Under a new zoning framework, you are permitted some market rate housing, but can increase the number of units by building community amenities (affordable housing, grocery store, community center, off-site plaza, or paying into a community fund).
    # With this information, return a chart of how many of each amenity you would build/fund. The index should be labeled 'Affordable Housing', 'Grocery Store', 'Community Center', 'Park/Plaza', and 'Fund', and the second column should list how many of each amenity you decide to build/fund.
    # Balance between using NPV and IRR as profitabilitymetrics."

    # ================================
    # API Call Here
    # ================================

    if st.button("📊 View Results", type="primary", use_container_width=True):
        mean_slider_value = (
            ranking_Housing_Affordable
            + ranking_InBuilding_Grocery
            + ranking_InBuilding_CommunityCenter
            + ranking_OffSite_ParkPlaza
            + ranking_Fund
        )

        mean_slider_value /= 5.0
        payload = {
            "rankings": {
                "affordable_housing": ranking_Housing_Affordable,
                "grocery_store": ranking_InBuilding_Grocery,
                "community_center": ranking_InBuilding_CommunityCenter,
                "park_plaza": ranking_OffSite_ParkPlaza,
                "fund": ranking_Fund,
            },
            "eagerness": mean_slider_value,
            "gpt_decide": True,  # <— ask backend to have GPT decide
            "city": "San Francisco",
        }
        resp = requests.post(f"{API_URL}/{ENDPOINT}", json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        Item_Accounting_table = pd.DataFrame(**data["item_accounting_table"])
        Input_table = pd.DataFrame(**data["input_table"])
        MRU_Add_Table = pd.DataFrame(**data["mru_add_table"])

        Final_Build_Table = pd.DataFrame(**data["final_build_table"])
        Master_Financial_Table = pd.DataFrame(**data["master_financial_table"])
        Final_Display = pd.DataFrame(**data["final_display"])

        # Optional chart series:
        irr_first6 = data["irr_series_first6"]
        npv_first6 = data["npv_series_first6"]

        # GPT outputs:
        gpt_decision = data.get("gpt_decision") or {}
        gpt_rationale = data.get("gpt_rationale") or ""

        # built_items now reflect GPT plan already applied server-side
        built_items = {
            "Market Rate Housing": int(
                Final_Build_Table.loc["Market Rate Housing", "Number"]
            ),
            "Affordable Housing": int(
                Final_Build_Table.loc["Affordable Housing", "Number"]
            ),
            "Grocery Store": int(Final_Build_Table.loc["Grocery Store", "Number"]),
            "Community Center": int(
                Final_Build_Table.loc["Community Center", "Number"]
            ),
            "Park/Plaza": int(Final_Build_Table.loc["Park/Plaza", "Number"]),
            "Fund": int(Final_Build_Table.loc["Fund", "Number"]),
        }

        round_result = {
            "round": st.session_state.current_round,
            "rankings": st.session_state.current_rankings["rankings"],
            "final_display": Final_Display,
            "final_build": Final_Build_Table,
            "built_items": built_items,
            "gpt_decision": gpt_decision,
            "gpt_rationale": gpt_rationale,
        }
        st.session_state.game_results.append(round_result)

        st.session_state.current_output = {
            "Item_Accounting_table": Item_Accounting_table,
            "Input_table": Input_table,
            "MRU_Add_Table": MRU_Add_Table,
            "Final_Build_Table": Final_Build_Table,
            "Final_Display": Final_Display,
            "gpt_decision": gpt_decision,
            "gpt_rationale": gpt_rationale,
        }

        st.session_state.game_state = "output"
        st.rerun()


def output_stage():
    """Display the output stage showing results for the current round."""
    st.title(f"Round {st.session_state.current_round} - Results")

    # Get the cached output data
    output_data = st.session_state.current_output
    Final_Build_Table = output_data["Final_Build_Table"]
    Final_Display = output_data["Final_Display"]

    # Display final results
    st.subheader("🏢 Final Project Results")

    # Display key metrics
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Stories", f"{float(Final_Display.loc['Stories', 'Value']):.1f}")

    with col2:
        likelihood = float(Final_Display.loc["Likelihood of Construction", "Value"])
        st.metric("Construction Likelihood", f"{likelihood:.1%}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**What Gets Built**")
        st.dataframe(Final_Build_Table)

    with col2:
        st.markdown("**Additional Details**")
        st.dataframe(Final_Display)

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])

    if st.session_state.current_round < 5:
        with col1:
            if st.button("🔄 Next Round", use_container_width=True):
                st.session_state.current_round += 1
                st.session_state.game_state = "input"
                st.rerun()
    else:
        with col1:
            if st.button("🏁 Finish Game", type="primary", use_container_width=True):
                st.session_state.game_state = "end"
                st.rerun()

    with col3:
        if st.button("🏠 Back to Start", use_container_width=True):
            st.session_state.game_state = "start"
            st.session_state.current_round = 1
            st.session_state.game_results = []
            if "current_output" in st.session_state:
                del st.session_state.current_output
            st.rerun()


def end_screen():
    """Display the final end screen with game summary."""
    st.title("🎉 Game Complete!")
    st.markdown("### Your Development Journey Results")

    # Calculate summary statistics
    total_rounds = len(st.session_state.game_results)
    if total_rounds == 0:
        st.warning(
            "No completed rounds found. Please play at least one round before finishing."
        )
        if st.button("🏠 Back to Start", use_container_width=True):
            st.session_state.game_state = "start"
            st.session_state.current_round = 1
            st.session_state.game_results = []
            if "current_output" in st.session_state:
                del st.session_state.current_output
            st.rerun()
        return

    avg_irr = (
        sum(
            [
                float(result["final_display"].loc["IRR", "Value"])
                for result in st.session_state.game_results
            ]
        )
        / total_rounds
    )
    avg_npv = (
        sum(
            [
                float(result["final_display"].loc["NPV", "Value"])
                for result in st.session_state.game_results
            ]
        )
        / total_rounds
    )
    avg_stories = (
        sum(
            [
                float(result["final_display"].loc["Stories", "Value"])
                for result in st.session_state.game_results
            ]
        )
        / total_rounds
    )

    # Calculate average likelihood
    avg_likelihood = (
        sum(
            [
                float(
                    result["final_display"].loc["Likelihood of Construction", "Value"]
                )
                for result in st.session_state.game_results
            ]
        )
        / total_rounds
    )

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Average IRR (Percent Return)", f"{avg_irr:.1%}")

    with col2:
        st.metric("Average NPV (Gross Return)", f"${avg_npv:,.0f}")

    with col3:
        st.metric("Average Stories", f"{avg_stories:.1f}")

    with col4:
        st.metric("Average Construction Likelihood", f"{avg_likelihood:.1%}")

    # Display status quo values
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("Status Quo IRR")
        st.markdown("<h5 style='margin-top: 0;'>6.0%</h5>", unsafe_allow_html=True)

    with col2:
        st.markdown("Status Quo NPV")
        st.markdown("<h5 style='margin-top: 0;'>$760,877</h5>", unsafe_allow_html=True)

    with col3:
        st.markdown("Status Quo Stories")
        st.markdown("<h5 style='margin-top: 0;'>4.0</h5>", unsafe_allow_html=True)

    with col4:
        st.markdown("Status Quo Construction Likelihood")
        st.markdown("<h5 style='margin-top: 0;'>18.0%</h5>", unsafe_allow_html=True)

    # Prepare data for charts
    rounds = list(range(1, total_rounds + 1))

    # Rankings data
    rankings_data = []
    for result in st.session_state.game_results:
        round_num = result["round"]
        for amenity, ranking in result["rankings"].items():
            rankings_data.append(
                {"Round": round_num, "Amenity": amenity, "Ranking": ranking}
            )

    # Built items data (cumulative across rounds)
    built_data = []
    cumulative_totals = {}  # Track running totals for each amenity

    for result in st.session_state.game_results:
        round_num = result["round"]
        for amenity, count in result["built_items"].items():
            # Add to cumulative total
            if amenity not in cumulative_totals:
                cumulative_totals[amenity] = 0
            cumulative_totals[amenity] += count
            built_data.append(
                {
                    "Round": round_num,
                    "Amenity": amenity,
                    "Number Built": cumulative_totals[amenity],
                }
            )

    # Financial metrics data
    irr_data = []
    npv_data = []
    likelihood_data = []
    for result in st.session_state.game_results:
        round_num = result["round"]
        irr_value = float(result["final_display"].loc["IRR", "Value"])
        npv_value = float(result["final_display"].loc["NPV", "Value"])
        likelihood_value = float(
            result["final_display"].loc["Likelihood of Construction", "Value"]
        )
        irr_data.append({"Round": round_num, "IRR": irr_value})
        npv_data.append({"Round": round_num, "NPV": npv_value})
        likelihood_data.append(
            {"Round": round_num, "Construction Likelihood": likelihood_value}
        )

    # Create DataFrames
    rankings_df = pd.DataFrame(rankings_data)
    built_df = pd.DataFrame(built_data)
    irr_df = pd.DataFrame(irr_data)
    npv_df = pd.DataFrame(npv_data)
    likelihood_df = pd.DataFrame(likelihood_data)

    # Display charts
    st.subheader("📈 Trends Over Rounds")

    col1, col2 = st.columns(2)

    with col1:
        if not rankings_df.empty:
            st.markdown("**Rankings Over Time**")
            chart_rankings = (
                alt.Chart(rankings_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Round:O", title="Round", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Ranking:Q", title="Ranking (1-10)"),
                    color=alt.Color("Amenity:N", title="Amenity"),
                    tooltip=["Round", "Amenity", "Ranking"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart_rankings, use_container_width=True)

    with col2:
        if not built_df.empty:
            st.markdown("**Cumulative Items Built Over Time**")
            # Dual-axis chart: housing (MRU, Affordable) on right axis; others on left
            housing_items = ["Market Rate Housing", "Affordable Housing"]
            other_items = ["Grocery Store", "Community Center", "Park/Plaza", "Fund"]

            left_layer = (
                alt.Chart(built_df)
                .transform_filter(
                    alt.FieldOneOfPredicate(field="Amenity", oneOf=other_items)
                )
                .mark_line(point=True)
                .encode(
                    x=alt.X("Round:O", title="Round", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Number Built:Q", title="Cumulative Quantity"),
                    color=alt.Color("Amenity:N", title="Amenity"),
                    tooltip=["Round", "Amenity", "Number Built"],
                )
            )

            right_layer = (
                alt.Chart(built_df)
                .transform_filter(
                    alt.FieldOneOfPredicate(field="Amenity", oneOf=housing_items)
                )
                .mark_line(point=True)
                .encode(
                    x=alt.X("Round:O", title="Round", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(
                        "Number Built:Q",
                        title="Cumulative Quantity (Housing)",
                        axis=alt.Axis(orient="right"),
                    ),
                    color=alt.Color("Amenity:N", title="Amenity"),
                    tooltip=["Round", "Amenity", "Number Built"],
                )
            )

            chart_built_dual = (
                alt.layer(left_layer, right_layer)
                .resolve_scale(y="independent")
                .properties(height=300)
            )

            st.altair_chart(chart_built_dual, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if not irr_df.empty:
            st.markdown("**Developer IRR Over Time**")
            chart_irr = (
                alt.Chart(irr_df)
                .mark_line(point=True, strokeWidth=3)
                .encode(
                    x=alt.X("Round:O", title="Round", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("IRR:Q", title="IRR", axis=alt.Axis(format="%")),
                    tooltip=["Round", alt.Tooltip("IRR:Q", format=".2%")],
                )
                .properties(height=300)
            )
            st.altair_chart(chart_irr, use_container_width=True)

    with col2:
        if not npv_df.empty:
            st.markdown("**Developer NPV Over Time**")
            chart_npv = (
                alt.Chart(npv_df)
                .mark_line(point=True, strokeWidth=3)
                .encode(
                    x=alt.X("Round:O", title="Round", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("NPV:Q", title="NPV", axis=alt.Axis(format="$,.0f")),
                    tooltip=["Round", alt.Tooltip("NPV:Q", format="$,.0f")],
                )
                .properties(height=300)
            )
            st.altair_chart(chart_npv, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if not likelihood_df.empty:
            st.markdown("**Construction Likelihood Over Time**")
            chart_likelihood = (
                alt.Chart(likelihood_df)
                .mark_line(point=True, strokeWidth=3)
                .encode(
                    x=alt.X("Round:O", title="Round", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(
                        "Construction Likelihood:Q",
                        title="Construction Likelihood",
                        axis=alt.Axis(format="%"),
                    ),
                    tooltip=[
                        "Round",
                        alt.Tooltip("Construction Likelihood:Q", format=".1%"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(chart_likelihood, use_container_width=True)

    # Display round-by-round results
    st.subheader("📊 Round-by-Round Results")

    for i, result in enumerate(st.session_state.game_results, 1):
        with st.expander(f"Round {i} Details"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Your Priorities:**")
                for amenity, ranking in result["rankings"].items():
                    st.write(f"• {amenity}: {ranking}/10")

            with col2:
                st.markdown("**Results:**")
                st.dataframe(result["final_display"])

    # Final message
    st.success(
        "🎊 Congratulations! You've completed all 5 rounds of the Dynamic Zoning Simulation! Thanks for playing!"
    )

    if st.button("🔄 Play Again", type="primary", use_container_width=True):
        st.session_state.game_state = "start"
        st.session_state.current_round = 1
        st.session_state.game_results = []
        if "current_output" in st.session_state:
            del st.session_state.current_output
        st.rerun()


# Main game logic
if st.session_state.game_state == "start":
    start_screen()
elif st.session_state.game_state == "input":
    input_stage()
elif st.session_state.game_state == "output":
    output_stage()
elif st.session_state.game_state == "end":
    end_screen()
