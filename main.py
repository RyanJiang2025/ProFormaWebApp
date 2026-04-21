import streamlit as st

from Proforma_WebApp_preapi import compute_developer_decision, rank_to_profit


st.set_page_config(page_title="Pro Forma Planner", layout="wide")
st.title("Pro Forma Planner")
st.caption("The planner now uses a local mathematical developer engine to choose the build program deterministically.")

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Micro Units")
    ranking_Housing_Micro = st.slider("For Young Professionals", min_value=1, max_value=10, value=5)
    st.write("Additional Profit:", f"{rank_to_profit(ranking_Housing_Micro) * 100:.2f}%")

    st.subheader("Grocery Store")
    ranking_InBuilding_Grocery = st.slider("On-Site Grocery Store", min_value=1, max_value=10, value=5)
    st.write("Additional Profit:", f"{rank_to_profit(ranking_InBuilding_Grocery) * 100:.2f}%")

with right_col:
    st.subheader("Community Center")
    ranking_InBuilding_CommunityCenter = st.slider("Gathering Place for Community", min_value=1, max_value=10, value=5)
    st.write("Additional Profit:", f"{rank_to_profit(ranking_InBuilding_CommunityCenter) * 100:.2f}%")

    st.subheader("Park/Plaza")
    ranking_OffSite_ParkPlaza = st.slider("Off-site Public Area", min_value=1, max_value=10, value=5)
    st.write("Additional Profit:", f"{rank_to_profit(ranking_OffSite_ParkPlaza) * 100:.2f}%")

decision = compute_developer_decision(
    ranking_Housing_Micro=ranking_Housing_Micro,
    ranking_InBuilding_Grocery=ranking_InBuilding_Grocery,
    ranking_InBuilding_CommunityCenter=ranking_InBuilding_CommunityCenter,
    ranking_OffSite_ParkPlaza=ranking_OffSite_ParkPlaza,
)
results = decision["proforma_results"]

st.subheader("Recommended Program")
st.caption(decision["reason"])

summary_df = decision["intermediate_tables"]["final_display"]
program_df = decision["intermediate_tables"]["final_build_table"]

summary_col, program_col = st.columns(2)

with summary_col:
    st.markdown("**Summary Metrics**")
    st.dataframe(summary_df, use_container_width=True)

with program_col:
    st.markdown("**Build Program**")
    st.dataframe(program_df, use_container_width=True)

with st.expander("Decision Diagnostics"):
    st.write("Objective:", decision["diagnostics"]["objective"])
    st.write("Evaluated combinations:", decision["diagnostics"]["evaluated_combinations"])
    st.json(decision["diagnostics"]["top_candidates"])

with st.expander("Amenity Tradeoff Tables"):
    source_tables = {
        "Micro Units": results["GPTOutputTable_Housing_Micro"],
        "Grocery Store": results["GPTOutputTable_InBuilding_Grocery"],
        "Community Center": results["GPTOutputTable_InBuilding_CommunityCenter"],
        "Park/Plaza": results["GPTOutputTable_OffSite_ParkPlaza"],
    }
    for item_name, table in source_tables.items():
        st.markdown(f"**{item_name}**")
        st.dataframe(table, use_container_width=True)

with st.expander("Intermediate Tables"):
    st.markdown("**Item Accounting Table**")
    st.dataframe(results["Item_Accounting_table"], use_container_width=True)

    st.markdown("**Input Table**")
    st.dataframe(results["Input_table"], use_container_width=True)

    st.markdown("**MRU Add Table**")
    st.dataframe(results["MRU_Add_Table"], use_container_width=True)
