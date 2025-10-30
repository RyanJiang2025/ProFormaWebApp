def generate_gpt_tables( Item_Accounting_table, MRU_Add_Table):  
    # Generated here as a dictionary for simplicity
    """Generates all GPT output tables with their specific configurations."""
    return {
        "Affordable Housing": GPTOutputTable_Builder(
            Item_Accounting_table, MRU_Add_Table, 5, 51, 5, "Affordable Housing"
        ),
        "Grocery Store": GPTOutputTable_Builder(
            Item_Accounting_table, MRU_Add_Table, 0, 6, 1, "Grocery Store"
        ),
        "Community Center": GPTOutputTable_Builder(
            Item_Accounting_table, MRU_Add_Table, 0, 6, 1, "Community Center"
        ),
        "Park/Plaza": GPTOutputTable_Builder(
            Item_Accounting_table, MRU_Add_Table, 0, 6, 1, "Park/Plaza"
        ),
        "Fund": GPTOutputTable_Builder(
            Item_Accounting_table, MRU_Add_Table, 0, 21, 1, "Fund"
        ),
    }

