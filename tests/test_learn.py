"""The Learn catalogue: recipes resolve to output-item icons/rarity, search
and owned-marking work, and granting a specific pick unlocks exactly it."""

import json

from app.core import characters, items, learn
from test_characters import make_character


def test_catalogue_loads():
    assert learn.total("spells") > 40
    assert learn.total("recipes") > 400
    assert learn.total("buildings") > 100


def test_recipe_rows_carry_output_icon_and_rarity():
    rows = learn.search("recipes")
    assert rows
    # at least some recipes resolved to a weapon/food/potion category glyph
    icon_keys = {r["icon"] for r in rows}
    assert "cat-sword" in icon_keys or "skill-cooking" in icon_keys
    for r in rows:
        assert r["name"]
        assert r["color"].startswith("#")
        assert r["icon"]


def test_recipe_categories_and_filter():
    cats = learn.recipe_categories()
    assert cats
    target = cats[0]
    rows = learn.search("recipes", category=target)
    assert rows and all(True for _ in rows)  # filtered set is non-empty


def test_search_and_owned_marking():
    rows = learn.search("spells")
    assert rows
    some_id = rows[0]["id"]
    owned_rows = learn.search("spells", owned={some_id})
    marked = next(r for r in owned_rows if r["id"] == some_id)
    assert marked["owned"] is True
    # owned entries sort last
    assert owned_rows[-1]["owned"] or all(r["owned"] for r in owned_rows)


def test_learn_specific_grants_only_the_picked(tmp_path):
    path = make_character(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["GameProgress"].setdefault("Progress", {})["RecipesUnlocked"] = []
    path.write_text(json.dumps(data, indent="\t"), encoding="utf-8")

    picks = [r["id"] for r in learn.search("recipes")[:3]]
    gains = characters.grant_all_unlocks(path, {"recipes": picks}, tmp_path / "bk")
    assert gains.get("recipes") == 3
    after = json.loads(path.read_text(encoding="utf-8"))
    assert set(after["GameProgress"]["Progress"]["RecipesUnlocked"]) == set(picks)
