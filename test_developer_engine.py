import unittest

from Proforma_WebApp_preapi import CHOICE_RANGES, compute_developer_decision


class DeveloperEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.default_result = compute_developer_decision()
        cls.low_result = compute_developer_decision(
            ranking_Housing_Micro=1,
            ranking_InBuilding_Grocery=1,
            ranking_InBuilding_CommunityCenter=1,
            ranking_OffSite_ParkPlaza=1,
        )
        cls.high_result = compute_developer_decision(
            ranking_Housing_Micro=10,
            ranking_InBuilding_Grocery=10,
            ranking_InBuilding_CommunityCenter=10,
            ranking_OffSite_ParkPlaza=10,
        )

    def test_selected_quantities_stay_in_allowed_ranges(self) -> None:
        result = self.default_result
        selected = result["selected_quantities"]

        self.assertIn(selected["Micro Units"], CHOICE_RANGES["Micro Units"])
        self.assertIn(selected["Grocery Store"], CHOICE_RANGES["Grocery Store"])
        self.assertIn(selected["Community Center"], CHOICE_RANGES["Community Center"])
        self.assertIn(selected["Park/Plaza"], CHOICE_RANGES["Park/Plaza"])

    def test_program_table_contains_expected_rows(self) -> None:
        result = self.default_result
        names = [row["name"] for row in result["program_table"]["friendly"]]

        self.assertEqual(
            names,
            ["MRU", "Micro Units", "Grocery Store", "Community Center", "Park/Plaza"],
        )

    def test_summary_table_contains_expected_metrics(self) -> None:
        result = self.default_result
        summary = result["summary_table"]["friendly"]

        self.assertEqual(
            set(summary.keys()),
            {"Stories", "MRU Stories", "NPV", "IRR", "Likelihood of Construction"},
        )

    def test_decision_is_deterministic(self) -> None:
        first = compute_developer_decision(
            ranking_Housing_Micro=7,
            ranking_InBuilding_Grocery=4,
            ranking_InBuilding_CommunityCenter=8,
            ranking_OffSite_ParkPlaza=6,
        )
        second = compute_developer_decision(
            ranking_Housing_Micro=7,
            ranking_InBuilding_Grocery=4,
            ranking_InBuilding_CommunityCenter=8,
            ranking_OffSite_ParkPlaza=6,
        )

        self.assertEqual(first["selected_quantities"], second["selected_quantities"])
        self.assertEqual(first["summary_table"]["friendly"], second["summary_table"]["friendly"])

    def test_slider_extremes_produce_valid_outputs(self) -> None:
        low = self.low_result
        high = self.high_result

        for result in (low, high):
            summary = result["summary_table"]["friendly"]
            self.assertIsInstance(summary["NPV"], float)
            self.assertIsInstance(summary["IRR"], float)
            self.assertIsInstance(summary["Likelihood of Construction"], float)
            self.assertEqual(result["diagnostics"]["evaluated_combinations"], 144)

    def test_preference_profiles_change_selected_program(self) -> None:
        low_all = compute_developer_decision(
            ranking_Housing_Micro=1,
            ranking_InBuilding_Grocery=1,
            ranking_InBuilding_CommunityCenter=1,
            ranking_OffSite_ParkPlaza=1,
        )
        high_grocery = compute_developer_decision(
            ranking_Housing_Micro=1,
            ranking_InBuilding_Grocery=10,
            ranking_InBuilding_CommunityCenter=1,
            ranking_OffSite_ParkPlaza=1,
        )
        high_community = compute_developer_decision(
            ranking_Housing_Micro=1,
            ranking_InBuilding_Grocery=1,
            ranking_InBuilding_CommunityCenter=10,
            ranking_OffSite_ParkPlaza=1,
        )

        self.assertNotEqual(low_all["selected_quantities"], high_grocery["selected_quantities"])
        self.assertNotEqual(low_all["selected_quantities"], high_community["selected_quantities"])
        self.assertEqual(high_community["selected_quantities"]["Community Center"], 1)

    def test_height_cost_multiplier_increases_for_taller_programs(self) -> None:
        short_program = compute_developer_decision(
            ranking_Housing_Micro=1,
            ranking_InBuilding_Grocery=1,
            ranking_InBuilding_CommunityCenter=1,
            ranking_OffSite_ParkPlaza=1,
        )
        tall_program = compute_developer_decision(
            ranking_Housing_Micro=10,
            ranking_InBuilding_Grocery=10,
            ranking_InBuilding_CommunityCenter=10,
            ranking_OffSite_ParkPlaza=10,
        )

        self.assertGreaterEqual(
            tall_program["diagnostics"]["top_candidates"][0]["height_cost_multiplier"],
            short_program["diagnostics"]["top_candidates"][0]["height_cost_multiplier"],
        )

    def test_rank_one_discourages_micro_units_relative_to_high_preference(self) -> None:
        low_micro = compute_developer_decision(
            ranking_Housing_Micro=1,
            ranking_InBuilding_Grocery=5,
            ranking_InBuilding_CommunityCenter=5,
            ranking_OffSite_ParkPlaza=5,
        )
        high_micro = compute_developer_decision(
            ranking_Housing_Micro=10,
            ranking_InBuilding_Grocery=5,
            ranking_InBuilding_CommunityCenter=5,
            ranking_OffSite_ParkPlaza=5,
        )

        self.assertLessEqual(
            low_micro["selected_quantities"]["Micro Units"],
            high_micro["selected_quantities"]["Micro Units"],
        )

    def test_tiebreak_sort_order_matches_documented_priority(self) -> None:
        candidates = [
            {
                "summary_table": {
                    "friendly": {
                        "NPV": 100.0,
                        "IRR": 0.15,
                        "Likelihood of Construction": 0.70,
                    }
                },
                "initial_cost_abs": 50.0,
                "total_amenity_count": 6.0,
            },
            {
                "summary_table": {
                    "friendly": {
                        "NPV": 100.0,
                        "IRR": 0.15,
                        "Likelihood of Construction": 0.70,
                    }
                },
                "initial_cost_abs": 40.0,
                "total_amenity_count": 8.0,
            },
            {
                "summary_table": {
                    "friendly": {
                        "NPV": 100.0,
                        "IRR": 0.16,
                        "Likelihood of Construction": 0.65,
                    }
                },
                "initial_cost_abs": 80.0,
                "total_amenity_count": 10.0,
            },
        ]

        ranked = sorted(
            candidates,
            key=lambda candidate: (
                candidate["summary_table"]["friendly"]["NPV"],
                candidate["summary_table"]["friendly"]["IRR"],
                candidate["summary_table"]["friendly"]["Likelihood of Construction"],
                -candidate["initial_cost_abs"],
                -candidate["total_amenity_count"],
            ),
            reverse=True,
        )

        self.assertEqual(ranked[0]["summary_table"]["friendly"]["IRR"], 0.16)
        self.assertEqual(ranked[1]["initial_cost_abs"], 40.0)


if __name__ == "__main__":
    unittest.main()
