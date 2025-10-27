#To run: streamlit run [filename].py in terminal

#Changes: scaling, making sliders more sensitive (20 --> 30% max)
#Compared to current version of Proforma_WebApp_V1.0.py: added incentive on/off buttons

import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as nf
import altair as alt

st.set_page_config(layout="wide")

# Custom CSS to widen the page
# st.markdown("""
#     <style>
#         .main {
#             max-width: 1400px;
#         }
#         .block-container {
#             max-width: 1400px;
#         }
#     </style>
# """, unsafe_allow_html=True)

# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================


#Scaling Values
Scaling_Grocery_Rent = 0.1
Scaling_ParkPlaza_MRUAdd = 2.15
Scaling_AffordableHousing_MRUAdd = 0.75
Scaling_CommunityCenter_MRUAdd = 0.75
Scaling_Fund_MRUAdd = 1 #needs to be fixed later on, formerly at 0.75

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
    return rank*0.2 #We changed it here from a quadratic to a linear function. Also, right now, a ranking under 5 means that the developer gets less MRU to "break even" (based on our back of envelope calculations). A 10 is 100% extra profit, 1 is almost 0.

def get_ranking_functions():
    """Returns all ranking functions as a tuple for assignment to variables outside the function."""
    # if st.session_state.toggle:
    st.subheader("Affordable Housing")
    ranking_Housing_Affordable = st.slider("Subsidized Rent by 50%. Otherwise the same as a Market Rate Unit", min_value=1, max_value=10, value=5)
    st.write("Developer Compensation Rate: ", round(rank_to_profit(ranking_Housing_Affordable)*100, 2), "%")

    st.subheader("Grocery Store")
    ranking_InBuilding_Grocery = st.slider("On-Site Grocery Store", min_value=1, max_value=10, value=5)
    st.write("Developer Compensation Rate: ", round(rank_to_profit(ranking_InBuilding_Grocery)*100, 2), "%")

    st.subheader("Community Center")
    ranking_InBuilding_CommunityCenter = st.slider("Multipurpose rooms for community events: think cultural activities, workshops, etc.", min_value=1, max_value=10, value=5)
    st.write("Developer Compensation Rate: ", round(rank_to_profit(ranking_InBuilding_CommunityCenter)*100, 2), "%")

    st.subheader("Park/Plaza")
    ranking_OffSite_ParkPlaza = st.slider("Off-site Public Area, Open Air Space", min_value=1, max_value=10, value=5)
    st.write("Developer Compensation Rate: ", round(rank_to_profit(ranking_OffSite_ParkPlaza)*100, 2), "%")

    st.subheader("CommunityFund ($100,000 Increment)")
    ranking_Fund = st.slider("Fund for community improvements. ", min_value=1, max_value=10, value=5)
    st.write("Developer Compensation Rate: ", round(rank_to_profit(ranking_Fund)*100, 2), "%")
    
    return (ranking_Housing_Affordable, ranking_InBuilding_Grocery, ranking_InBuilding_CommunityCenter, ranking_OffSite_ParkPlaza, ranking_Fund)

# Call the function and assign the returned values to variables


def get_item_accounting_table():
    """Creates and returns the Item Accounting Table with all calculations and scaling applied."""
    #Item Accounting Table of Excel Sheet
    Item_Accounting_table = {
        "Size": [9000, 750, 750, 7500, 20000, 0, 0],
        "Rent_yearly": [0, 36000, 18000, 300000, 0, 0, 0],
        "Construction_cost": [-900, -375000, -375000, -2750000, -10000000, -4500000, 0],
        "Soft_Costs": [0, 0, 0, 0, 0, 0, 0],
        "Upkeep_yearly": [0, -6000, -6000, -82500, -472000, -125000, -100000], #The fund increment has to be significant (i.e. at least 50,000) because of the way MRU add is calculated. Without it, for each increment of funding, it adds 1 MRU, whether that is $10,000 or $1, which creates a very high IRR.
        "MRU_add_per_unit": [0, 0, 0, 0, 0, 0, 0]
    }
    Item_Accounting_table = pd.DataFrame(Item_Accounting_table)
    Item_Accounting_table.index = ["Land", "MRU", "Affordable Housing", "Grocery Store", "Community Center", "Park/Plaza", "Fund"]
    for i in Item_Accounting_table.index:
        Item_Accounting_table.loc[i, "Soft_Costs"] = Item_Accounting_table.loc[i, "Construction_cost"] * soft_costs

    #Scaling
    Item_Accounting_table.loc["Grocery Store", "Rent_yearly"] = Item_Accounting_table.loc["Grocery Store", "Rent_yearly"]*Scaling_Grocery_Rent
    
    return Item_Accounting_table

#Input Table of Excel Sheet: to be revised
def get_input_table(Item_Accounting_table):
    """Creates and returns the Input Table with all calculations applied."""
    # Get rankings from session state
    rankings = st.session_state.current_rankings['rankings']
    Input_table = {
        "Units/Rank": [MRU_count_initial, rankings['Affordable Housing'], rankings['Grocery Store'], rankings['Community Center'], rankings['Park/Plaza'], rankings['Fund']],
        "Net Profit/Year/SqFt": [0, 0, 0, 0, 0, 0]
    }
    Input_table = pd.DataFrame(Input_table)
    Input_table.index = ["MRU", "Affordable Housing", "Grocery Store", "Community Center", "Park/Plaza", "Fund"]
    for i in Item_Accounting_table.index[1:]:
        if Item_Accounting_table.loc[i, "Size"] != 0:
            Input_table.loc[i, "Net Profit/Year/SqFt"] = (Item_Accounting_table.loc[i, "Rent_yearly"]+Item_Accounting_table.loc[i, "Upkeep_yearly"])/Item_Accounting_table.loc[i, "Size"]
        else:
            Input_table.loc[i, "Net Profit/Year/SqFt"] = 0
    return Input_table

#NOI Tables. This function returns the 
def NOI_table_builder (Item_Accounting_table, item_type, return_type):
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
def get_MRU_Add_table(Item_Accounting_table, Input_table):
    MRU_Add_Table = np.zeros((6, 4), dtype=float) #Make the Table
    MRU_Add_Table = pd.DataFrame(MRU_Add_Table, columns = ["NPV/SqFt", "MRU Break Even", "Scaled for Size", "Extra MRU From Rankings"])
    MRU_Add_Table.index = Input_table.index
    # if st.session_state.toggle: #this measures if we have our amenity button on or off
    for i in MRU_Add_Table.index:
        if Item_Accounting_table.loc [i, "Size"] != 0: #This is for all calculations except for off-site items
            MRU_Add_Table.loc[i, "NPV/SqFt"] = nf.npv(Discount_rate, NOI_table_builder(Item_Accounting_table, i, "NOI"))/Item_Accounting_table.loc [i, "Size"] #calculates NPV/sqft
            if i == "MRU": #All MRU equivalent values for MRU is 0
                MRU_Add_Table.loc[i, "MRU Break Even"] = 0
                MRU_Add_Table.loc[i, "Scaled for Size"] = 0
                MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = 0
            else: #for each row, fill out horizontally, left to right
                MRU_Add_Table.loc[i, "MRU Break Even"] = (MRU_Add_Table.loc["MRU", "NPV/SqFt"] - MRU_Add_Table.loc[i, "NPV/SqFt"])/MRU_Add_Table.loc["MRU", "NPV/SqFt"] #this calculates MRUs to break even/sqft
                MRU_Add_Table.loc[i, "Scaled for Size"] = MRU_Add_Table.loc[i, "MRU Break Even"]*Item_Accounting_table.loc[i, "Size"]/Item_Accounting_table.loc["MRU", "Size"]
                MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = MRU_Add_Table.loc[i, "Scaled for Size"]*(rank_to_profit(Input_table.loc[i, "Units/Rank"]))
        else: #for off site locations, since we don't calculate per sqft, only absolute. Similarly, calculate left to right
            MRU_Add_Table.loc[i, "NPV/SqFt"] = 0
            MRU_Add_Table.loc[i, "MRU Break Even"] = (nf.npv(Discount_rate, NOI_table_builder(Item_Accounting_table, "MRU", "NOI"))-nf.npv(Discount_rate, NOI_table_builder(Item_Accounting_table, i, "NOI")))/nf.npv(Discount_rate, NOI_table_builder(Item_Accounting_table, "MRU", "NOI")) #here is the problem: since funds have an NOI of 0????
            MRU_Add_Table.loc[i, "Scaled for Size"] = MRU_Add_Table.loc[i, "MRU Break Even"]
            MRU_Add_Table.loc[i, "Extra MRU From Rankings"] = MRU_Add_Table.loc[i, "Scaled for Size"]*(rank_to_profit(Input_table.loc[i, "Units/Rank"])) #this is the same as "Base Extra MRU Percent" in MSPF 4.2 "Natural Log Testing Stuff" sheet

    #Scaling
    MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Park/Plaza", "Extra MRU From Rankings"] * Scaling_ParkPlaza_MRUAdd
    MRU_Add_Table.loc["Affordable Housing", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Affordable Housing", "Extra MRU From Rankings"] * Scaling_AffordableHousing_MRUAdd
    MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Community Center", "Extra MRU From Rankings"] * Scaling_CommunityCenter_MRUAdd
    MRU_Add_Table.loc["Fund", "Extra MRU From Rankings"] = MRU_Add_Table.loc["Fund", "Extra MRU From Rankings"] * Scaling_Fund_MRUAdd
    #Update older tables with MRU add numbers
    for i in MRU_Add_Table.index:
        Item_Accounting_table.loc[i, "MRU_add_per_unit"] = MRU_Add_Table.loc[i, "Extra MRU From Rankings"]
    return MRU_Add_Table

#This section builds the output formulas for ChatGPT. For each amenity type, it builds a chart that shows for this many items of each community benefit, here is the IRR, NPV, and cost associated with that item PLUS the MRU add.
def GPTOutputTable_Builder(Item_Accounting_table, MRU_Add_Table, min_units, max_units, step, item):
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

        NOITable = NOI_table_builder(Item_Accounting_table, "MRU", "NOI") * MRUAdd + NOI_table_builder(Item_Accounting_table, item, "NOI") * i

        GPTOutputTable.at["IRR", i]   = nf.irr(NOITable)
        GPTOutputTable.at["NPV", i]   = nf.npv(Discount_rate, NOITable)
        GPTOutputTable.at["Costs", i] = (
            (Item_Accounting_table.loc["MRU", "Construction_cost"] + Item_Accounting_table.loc["MRU", "Soft_Costs"]) * MRUAdd
            + (Item_Accounting_table.loc[item, "Construction_cost"] + Item_Accounting_table.loc[item, "Soft_Costs"]) * i
        )

    return GPTOutputTable


#These four tables should be exported to Alan's ChatGPT API, along with a prompt of something along the following:
#"You are a real estate developer in [city]. In addition to what you already have approved, you can add the following community amenities (affordable housing, grocery store, community center, or funding for an off-site plaza), with the quantities and resulting IRR, NPV, and initial costs in the charts below.
#With this information, return a chart of how many of each amenity you would build. The first column should be labeled 'Affordable Housing', 'Grocery Store', 'Community Center', and 'Park/Plaza', and the second column should list how many of each amenity you decide to build.
#Balance between using NPV and IRR as metrics, and lean towards building a mix of different items, if they have similar profitability.""

def generate_gpt_tables(Item_Accounting_table, MRU_Add_Table): #Generated here as a dictionary for simplicity
    """Generates all GPT output tables with their specific configurations."""
    return {
        "Affordable Housing": GPTOutputTable_Builder(Item_Accounting_table, MRU_Add_Table, 5, 51, 5, "Affordable Housing"),
        "Grocery Store": GPTOutputTable_Builder(Item_Accounting_table, MRU_Add_Table, 0, 6, 1, "Grocery Store"),
        "Community Center": GPTOutputTable_Builder(Item_Accounting_table, MRU_Add_Table, 0, 6, 1, "Community Center"),
        "Park/Plaza": GPTOutputTable_Builder(Item_Accounting_table, MRU_Add_Table, 0, 6, 1, "Park/Plaza"),
        "Fund": GPTOutputTable_Builder(Item_Accounting_table, MRU_Add_Table, 0, 6, 1, "Fund")
    }


def _first_six_irrs(df: pd.DataFrame) -> list[float]: #captures the first 6 values (i.e. 0-5 of an amenity) for charting purposes
    # ensure columns are sorted numerically, then take first six
    cols = sorted(df.columns)[:6]
    return df.loc['IRR', cols].tolist()

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
        index=['Affordable Housing', 'Grocery Store', 'Community Center', 'Park/Plaza', 'Fund'],
        columns=[str(i) for i in range(6)]
    )
    IRR_first6_long = ( #chart is reformatted
        IRR_first6
        .reset_index()
        .melt(id_vars='index', var_name='Period', value_name='IRR')
        .rename(columns={'index': 'Amenity'})
    )
    chart = (
        alt.Chart(IRR_first6_long)
        .mark_line(point=True)
        .encode(
            x=alt.X('Period:Q', title='Units Built'),         # if your columns are unit counts, use ':Q' and title='Units'
            y=alt.Y('IRR:Q', title='IRR', axis=alt.Axis(format='%')),
            color=alt.Color('Amenity:N', title='Amenity'),
            tooltip=['Amenity', 'Period', alt.Tooltip('IRR:Q', format='.2%')]
        )
        .properties(height=380)
        .interactive()
    )
    return chart


# Helper: extract first 6 NPV values from a GPTOutputTable
def _first_six_npvs(df: pd.DataFrame) -> list[float]:
    cols = sorted(df.columns)[:6]  # first 6 columns (periods)
    return df.loc['NPV', cols].tolist()

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
        index=['Affordable Housing', 'Grocery Store', 'Community Center', 'Park/Plaza', 'Fund'],
        columns=[str(i) for i in range(6)]
    )
    NPV_first6_long = (
        NPV_first6
        .reset_index()
        .melt(id_vars='index', var_name='Period', value_name='NPV')
        .rename(columns={'index': 'Amenity'})
    )
    chart = (
        alt.Chart(NPV_first6_long)
        .mark_line(point=True)
        .encode(
            x=alt.X('Period:Q', title='Units Built'),
            y=alt.Y('NPV:Q', title='Net Present Value', axis=alt.Axis(format='$,.0f')),
            color=alt.Color('Amenity:N', title='Amenity'),
            tooltip=['Amenity', 'Period', alt.Tooltip('NPV:Q', format='$,.0f')]
        )
        .properties(height=380)
        .interactive()
    )
    return chart


#The results from ChatGPT then need to be re-inputted into the pro forma, here.
#Here we would have the API return
#Without the API, simply just change the "number" list manually

def get_Final_Build_Table(Item_Accounting_table, Input_table, MRU_Add_Table):
    """Creates and returns the Final Build Table with all calculations applied."""
    Final_Build_Table = pd.DataFrame({
        "Number": [MRU_count_initial, 0, 0, 0, 0, 0],
        "Size": [0, 0, 0, 0, 0, 0]
    }, index=Input_table.index)
    for i in Final_Build_Table.index:
        if i != "MRU" and Final_Build_Table.loc[i, "Number"] != 0:
            Final_Build_Table.loc["MRU", "Number"] += MRU_Add_Table.loc[i, "Extra MRU From Rankings"] * (1 + np.log(Final_Build_Table.loc[i, "Number"]))
    Final_Build_Table.loc["MRU", "Number"] = np.round(Final_Build_Table.loc["MRU", "Number"])
    for i in Final_Build_Table.index:
        Final_Build_Table.loc[i, "Size"] = Item_Accounting_table.loc[i, "Size"]*Final_Build_Table.loc[i, "Number"]
    return Final_Build_Table

# Call the function and assign the returned value to the variable

#Here, sum up the "height" column and divide by our land size (9000, maybe should be set as a variable?) to get final floor number, and then round up.
#The final build table, plus the height, should be sent to Adrian for the 3d visualization.



#This code writes the final financial table, which calculates overall revenue, upkeep, NOI, etc, culminating in pre-tax cash flow.
#We then use pre-tax cash flor to calculate various financial metrics in our final display table.
def get_Master_Financial_Table(Item_Accounting_table, Final_Build_Table):
    """Creates and returns the Master Financial Table with all calculations applied."""
    Master_Financial_Table = pd.DataFrame(index=range(8), columns=range(11))
    Master_Financial_Table.index = ["Revenue", "Upkeep", "Hard Costs", "Soft Costs", "Land Costs", "NOI", "Other Expenses", "Pre-Tax Cash Flow"]
    Master_Financial_Table = Master_Financial_Table.fillna(0)
    for item in Final_Build_Table.index:
        Master_Financial_Table.loc["Revenue"] += NOI_table_builder(Item_Accounting_table, item, "Rent")*Final_Build_Table.loc[item, "Number"]
        Master_Financial_Table.loc["Upkeep"] += NOI_table_builder(Item_Accounting_table, item, "Upkeep")*Final_Build_Table.loc[item, "Number"]
        Master_Financial_Table.loc["Hard Costs", 0] += Final_Build_Table.loc[item, "Number"]*Item_Accounting_table.loc[item, "Construction_cost"]
    Master_Financial_Table.loc["Soft Costs", 0] = Master_Financial_Table.loc["Hard Costs", 0] * soft_costs
    Master_Financial_Table.loc["Land Costs", 0] = Item_Accounting_table.loc["Land", "Size"] * Item_Accounting_table.loc["Land", "Construction_cost"]
    for period in Master_Financial_Table.columns:
        Master_Financial_Table.loc["NOI", period] = Master_Financial_Table.loc[["Revenue", "Hard Costs", "Soft Costs", "Land Costs", "Upkeep"], period].sum()
        Master_Financial_Table.loc["Other Expenses", period] = Other_expenses
        Master_Financial_Table.loc["Pre-Tax Cash Flow", period] = Master_Financial_Table.loc["NOI", period] + Master_Financial_Table.loc["Other Expenses", period]
    return Master_Financial_Table

# st.write(Master_Financial_Table)

def get_Final_Display(Item_Accounting_table, Final_Build_Table, Master_Financial_Table):
    """Creates and returns the Final Display Table with all calculations applied."""
    Final_Display = pd.DataFrame(index = ["Stories", "MRU Stories", "NPV", "IRR", "Likelihood of Construction"], columns = ["Value"])
    Final_Display.loc["Stories"] = np.ceil(Final_Build_Table.loc[:, "Size"].sum()/Item_Accounting_table.loc["Land", "Size"])
    Final_Display.loc["MRU Stories"] = (Final_Build_Table.loc["MRU", "Size"]/Item_Accounting_table.loc["Land", "Size"])
    Final_Display.loc["NPV"] = nf.npv(Discount_rate, Master_Financial_Table.loc["Pre-Tax Cash Flow", :])
    Final_Display.loc["IRR"] = nf.irr(Master_Financial_Table.loc["Pre-Tax Cash Flow", :])
    Final_Display.loc["Likelihood of Construction"] = 1/(1+np.e**(-55*(Final_Display.loc["IRR", "Value"]-0.135)))
    return Final_Display



# =============================================================================
# GAME FRAMEWORK
# =============================================================================

# Initialize session state for game progression
if 'game_state' not in st.session_state:
    st.session_state.game_state = 'start'
if 'current_round' not in st.session_state:
    st.session_state.current_round = 1
if 'game_results' not in st.session_state:
    st.session_state.game_results = []

def start_screen():
    """Display the game start screen."""
    st.title("🏗️ Real Estate Development Game")
    st.markdown("### Welcome to the Dynamic Zoning Simulation!")
    st.markdown("""
    **Game Overview:**
    - You'll play 5 rounds as a member of the community
    - Each round, you'll set priorities for community benefits
    - Your decisions will affect what gets built and the financial outcomes
    - See what happens to the project over time!
    """)
    
    if st.button("🚀 Start Game", type="primary", use_container_width=True):
        st.session_state.game_state = 'input'
        st.rerun()

def input_stage():
    """Display the input stage for setting priorities."""
    st.title(f"Round {st.session_state.current_round} - Set Your Priorities")
    st.markdown("Set your priorities and see how they affect financial outcomes (1=low, 10=high).")
    st.markdown("100% = developer breaks even on building the (first) amenity, <100% = loss, >100% = profit. Subsidy decreases with each additional amenity built.")
    
    # Display cumulative progress from previous rounds
    if len(st.session_state.game_results) > 0:
        st.subheader("📊 Cumulative Progress So Far")
        
        # Aggregate built items from all previous rounds
        cumulative_built = {
            'MRU': 0,
            'Affordable Housing': 0,
            'Grocery Store': 0,
            'Community Center': 0,
            'Park/Plaza': 0,
            'Fund': 0
        }
        
        for result in st.session_state.game_results:
            for amenity, count in result['built_items'].items():
                cumulative_built[amenity] += count
        
        # Create a DataFrame for the chart
        progress_data = []
        for amenity, count in cumulative_built.items():
            progress_data.append({'Amenity': amenity, 'Quantity': count})
        progress_df = pd.DataFrame(progress_data)
        
        # Create a bar chart
        progress_chart = alt.Chart(progress_df).mark_bar().encode(
            x=alt.X('Amenity:N', title='Amenity Type', axis=alt.Axis(labelAngle=-45)),
            y=alt.Y('Quantity:Q', title='Cumulative Quantity Built'),
            color=alt.Color('Amenity:N', title='Amenity'),
            tooltip=['Amenity', 'Quantity']
        ).properties(height=200, width=600)
        
        st.altair_chart(progress_chart, use_container_width=True)
    
    # Create two columns: left for sliders, right for charts
    col_sliders, col_charts = st.columns([1, 1])
    
    with col_sliders:
        # Call the ranking functions to get the sliders - all sliders render here
        ranking_Housing_Affordable, ranking_InBuilding_Grocery, ranking_InBuilding_CommunityCenter, ranking_OffSite_ParkPlaza, ranking_Fund = get_ranking_functions()
    
    # Store the rankings for this round (outside columns so accessible later)
    round_rankings = {
        'round': st.session_state.current_round,
        'rankings': {
            'Affordable Housing': ranking_Housing_Affordable,
            'Grocery Store': ranking_InBuilding_Grocery,
            'Community Center': ranking_InBuilding_CommunityCenter,
            'Park/Plaza': ranking_OffSite_ParkPlaza,
            'Fund': ranking_Fund
        }
    }
    
    st.session_state.current_rankings = round_rankings
    
    # Generate tables and charts for preview (using the slider values from session state)
    Item_Accounting_table = get_item_accounting_table()
    Input_table = get_input_table(Item_Accounting_table)
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
    
    if st.button("📊 View Results", type="primary", use_container_width=True):
        # Generate final build results
        Final_Build_Table = get_Final_Build_Table(Item_Accounting_table, Input_table, MRU_Add_Table)
        Master_Financial_Table = get_Master_Financial_Table(Item_Accounting_table, Final_Build_Table)
        Final_Display = get_Final_Display(Item_Accounting_table, Final_Build_Table, Master_Financial_Table)
        
        # Extract what was built in this round
        built_items = {
            'MRU': int(Final_Build_Table.loc['MRU', 'Number']),
            'Affordable Housing': int(Final_Build_Table.loc['Affordable Housing', 'Number']),
            'Grocery Store': int(Final_Build_Table.loc['Grocery Store', 'Number']),
            'Community Center': int(Final_Build_Table.loc['Community Center', 'Number']),
            'Park/Plaza': int(Final_Build_Table.loc['Park/Plaza', 'Number']),
            'Fund': int(Final_Build_Table.loc['Fund', 'Number'])
        }
        
        # Store the generated results for the current round
        round_result = {
            'round': st.session_state.current_round,
            'rankings': round_rankings['rankings'],
            'final_display': Final_Display,
            'final_build': Final_Build_Table,
            'built_items': built_items
        }
        st.session_state.game_results.append(round_result)
        
        # Store the computed tables for display in output_stage
        st.session_state.current_output = {
            'Item_Accounting_table': Item_Accounting_table,
            'Input_table': Input_table,
            'MRU_Add_Table': MRU_Add_Table,
            'Final_Build_Table': Final_Build_Table,
            'Final_Display': Final_Display,
            'gpt_tables': gpt_tables
        }
        
        st.session_state.game_state = 'output'
        st.rerun()

def output_stage():
    """Display the output stage showing results for the current round."""
    st.title(f"Round {st.session_state.current_round} - Results")
    
    # Get the cached output data
    output_data = st.session_state.current_output
    Final_Build_Table = output_data['Final_Build_Table']
    Final_Display = output_data['Final_Display']
    
    # Display final results
    st.subheader("🏢 Final Project Results")
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("IRR", f"{float(Final_Display.loc['IRR', 'Value']):.1%}")
    
    with col2:
        st.metric("NPV", f"${float(Final_Display.loc['NPV', 'Value']):,.0f}")
    
    with col3:
        st.metric("Stories", f"{float(Final_Display.loc['Stories', 'Value']):.1f}")
    
    with col4:
        likelihood = float(Final_Display.loc['Likelihood of Construction', 'Value'])
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
                st.session_state.game_state = 'input'
                st.rerun()
    else:
        with col1:
            if st.button("🏁 Finish Game", type="primary", use_container_width=True):
                st.session_state.game_state = 'end'
                st.rerun()
    
    with col3:
        if st.button("🏠 Back to Start", use_container_width=True):
            st.session_state.game_state = 'start'
            st.session_state.current_round = 1
            st.session_state.game_results = []
            if 'current_output' in st.session_state:
                del st.session_state.current_output
            st.rerun()

def end_screen():
    """Display the final end screen with game summary."""
    st.title("🎉 Game Complete!")
    st.markdown("### Your Development Journey Results")
    
    # Calculate summary statistics
    total_rounds = len(st.session_state.game_results)
    avg_irr = sum([float(result['final_display'].loc['IRR', 'Value']) for result in st.session_state.game_results]) / total_rounds
    avg_npv = sum([float(result['final_display'].loc['NPV', 'Value']) for result in st.session_state.game_results]) / total_rounds
    avg_stories = sum([float(result['final_display'].loc['Stories', 'Value']) for result in st.session_state.game_results]) / total_rounds
    
    # Calculate average likelihood
    avg_likelihood = sum([float(result['final_display'].loc['Likelihood of Construction', 'Value']) for result in st.session_state.game_results]) / total_rounds
    
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
        round_num = result['round']
        for amenity, ranking in result['rankings'].items():
            rankings_data.append({'Round': round_num, 'Amenity': amenity, 'Ranking': ranking})
    
    # Built items data (cumulative across rounds)
    built_data = []
    cumulative_totals = {}  # Track running totals for each amenity
    
    for result in st.session_state.game_results:
        round_num = result['round']
        for amenity, count in result['built_items'].items():
            # Add to cumulative total
            if amenity not in cumulative_totals:
                cumulative_totals[amenity] = 0
            cumulative_totals[amenity] += count
            built_data.append({'Round': round_num, 'Amenity': amenity, 'Number Built': cumulative_totals[amenity]})
    
    # Financial metrics data
    irr_data = []
    npv_data = []
    likelihood_data = []
    for result in st.session_state.game_results:
        round_num = result['round']
        irr_value = float(result['final_display'].loc['IRR', 'Value'])
        npv_value = float(result['final_display'].loc['NPV', 'Value'])
        likelihood_value = float(result['final_display'].loc['Likelihood of Construction', 'Value'])
        irr_data.append({'Round': round_num, 'IRR': irr_value})
        npv_data.append({'Round': round_num, 'NPV': npv_value})
        likelihood_data.append({'Round': round_num, 'Construction Likelihood': likelihood_value})
    
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
            chart_rankings = alt.Chart(rankings_df).mark_line(point=True).encode(
                x=alt.X('Round:O', title='Round', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Ranking:Q', title='Ranking (1-10)'),
                color=alt.Color('Amenity:N', title='Amenity'),
                tooltip=['Round', 'Amenity', 'Ranking']
            ).properties(height=300)
            st.altair_chart(chart_rankings, use_container_width=True)
    
    with col2:
        if not built_df.empty:
            st.markdown("**Cumulative Items Built Over Time**")
            chart_built = alt.Chart(built_df).mark_line(point=True).encode(
                x=alt.X('Round:O', title='Round', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Number Built:Q', title='Cumulative Quantity'),
                color=alt.Color('Amenity:N', title='Amenity'),
                tooltip=['Round', 'Amenity', 'Number Built']
            ).properties(height=300)
            st.altair_chart(chart_built, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not irr_df.empty:
            st.markdown("**Developer IRR Over Time**")
            chart_irr = alt.Chart(irr_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Round:O', title='Round', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('IRR:Q', title='IRR', axis=alt.Axis(format='%')),
                tooltip=['Round', alt.Tooltip('IRR:Q', format='.2%')]
            ).properties(height=300)
            st.altair_chart(chart_irr, use_container_width=True)
    
    with col2:
        if not npv_df.empty:
            st.markdown("**Developer NPV Over Time**")
            chart_npv = alt.Chart(npv_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Round:O', title='Round', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('NPV:Q', title='NPV', axis=alt.Axis(format='$,.0f')),
                tooltip=['Round', alt.Tooltip('NPV:Q', format='$,.0f')]
            ).properties(height=300)
            st.altair_chart(chart_npv, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not likelihood_df.empty:
            st.markdown("**Construction Likelihood Over Time**")
            chart_likelihood = alt.Chart(likelihood_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Round:O', title='Round', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Construction Likelihood:Q', title='Construction Likelihood', axis=alt.Axis(format='%')),
                tooltip=['Round', alt.Tooltip('Construction Likelihood:Q', format='.1%')]
            ).properties(height=300)
            st.altair_chart(chart_likelihood, use_container_width=True)
    
    # Display round-by-round results
    st.subheader("📊 Round-by-Round Results")
    
    for i, result in enumerate(st.session_state.game_results, 1):
        with st.expander(f"Round {i} Details"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Your Priorities:**")
                for amenity, ranking in result['rankings'].items():
                    st.write(f"• {amenity}: {ranking}/10")
            
            with col2:
                st.markdown("**Results:**")
                st.dataframe(result['final_display'])
    
    # Final message
    st.success("🎊 Congratulations! You've completed all 5 rounds of the Real Estate Development Game!")
    
    if st.button("🔄 Play Again", type="primary", use_container_width=True):
        st.session_state.game_state = 'start'
        st.session_state.current_round = 1
        st.session_state.game_results = []
        if 'current_output' in st.session_state:
            del st.session_state.current_output
        st.rerun()

# Main game logic
if st.session_state.game_state == 'start':
    start_screen()
elif st.session_state.game_state == 'input':
    input_stage()
elif st.session_state.game_state == 'output':
    output_stage()
elif st.session_state.game_state == 'end':
    end_screen()

