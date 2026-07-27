from app.ai.nutrition import (
    NutritionFacts,
    clean_nutrition_facts,
    is_plausible_nutrition,
)


class TestNutritionFactsCoercion:
    def test_accepts_numbers(self):
        facts = NutritionFacts(calories_kcal=100, protein=5.5)
        assert facts.calories_kcal == 100
        assert facts.protein == 5.5

    def test_coerces_comma_decimal_strings(self):
        facts = NutritionFacts(protein="12,5")
        assert facts.protein == 12.5

    def test_coerces_strings_with_units(self):
        facts = NutritionFacts(total_fat="1.2 g")
        assert facts.total_fat == 1.2

    def test_invalid_strings_become_none(self):
        facts = NutritionFacts(protein="n/a", salt="traces")
        assert facts.protein is None
        assert facts.salt is None

    def test_missing_fields_default_to_none(self):
        facts = NutritionFacts()
        assert facts.calories_kcal is None
        assert facts.protein is None


class TestCleanNutritionFacts:
    def test_regular_values_pass_through(self):
        facts = NutritionFacts(
            calories_kcal=250, total_fat=10, total_carbohydrate=30, protein=8
        )
        values = clean_nutrition_facts(facts)
        assert values is not None
        assert values["calories"] == 250
        assert values["total_fat"] == 10
        assert values["total_carbohydrate"] == 30
        assert values["protein"] == 8

    def test_kcal_derived_from_kj_when_missing(self):
        facts = NutritionFacts(calories_kj=418.4)
        values = clean_nutrition_facts(facts)
        assert values is not None
        assert values["calories"] == 100

    def test_kj_reported_as_kcal_is_converted(self):
        # 2000 "kcal" per 100 g is impossible; it is really kJ.
        facts = NutritionFacts(calories_kcal=2000)
        values = clean_nutrition_facts(facts)
        assert values is not None
        assert values["calories"] == round(2000 / 4.184, 1)

    def test_absurd_calories_dropped(self):
        facts = NutritionFacts(calories_kcal=50000, protein=5)
        values = clean_nutrition_facts(facts)
        assert values is not None
        assert values["calories"] is None
        assert values["protein"] == 5

    def test_out_of_range_macros_dropped(self):
        facts = NutritionFacts(calories_kcal=100, salt=120, protein=-3)
        values = clean_nutrition_facts(facts)
        assert values is not None
        assert values["salt"] is None
        assert values["protein"] is None

    def test_all_none_returns_none(self):
        assert clean_nutrition_facts(NutritionFacts()) is None


class TestIsPlausibleNutrition:
    def test_regular_product_is_plausible(self):
        assert is_plausible_nutrition(
            {
                "calories": 250,
                "total_fat": 10,
                "total_carbohydrate": 30,
                "protein": 8,
                "salt": 1.2,
            }
        )

    def test_salt_product_is_plausible(self):
        # Table salt legitimately has ~98 g of salt per 100 g.
        assert is_plausible_nutrition(
            {
                "calories": 0,
                "total_fat": 0,
                "total_carbohydrate": 0,
                "protein": 0,
                "salt": 98,
            }
        )

    def test_salt_above_100g_is_implausible(self):
        assert not is_plausible_nutrition({"calories": 82, "salt": 120})

    def test_calories_in_kj_range_is_implausible(self):
        assert not is_plausible_nutrition({"calories": 2000})

    def test_macros_exceeding_100g_is_implausible(self):
        assert not is_plausible_nutrition(
            {"calories": 500, "total_fat": 60, "total_carbohydrate": 60, "protein": 20}
        )

    def test_calories_far_below_macros_is_implausible(self):
        # 50 g fat alone is 450 kcal; 30 kcal reported cannot be right.
        assert not is_plausible_nutrition(
            {
                "calories": 30,
                "total_fat": 50,
                "total_carbohydrate": 30,
                "protein": 10,
            }
        )

    def test_calories_far_above_macros_is_implausible(self):
        assert not is_plausible_nutrition(
            {
                "calories": 800,
                "total_fat": 1,
                "total_carbohydrate": 5,
                "protein": 2,
            }
        )

    def test_missing_values_are_plausible(self):
        assert is_plausible_nutrition({"calories": None})
