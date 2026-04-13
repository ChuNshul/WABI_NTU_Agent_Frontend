"""
components.py — Component registry, single source of truth.

Replaces ui_components.json entirely.

Why Python over JSON
──────────────────────────────────────────────────────────────────────────────
                     ui_components.json          this module
  I/O on every boot  disk read + lru_cache       none (import-time constant)
  Catalog generation _compact_prop() regex       to_prompt_catalog() — pure Python
  Type safety        none                        NamedTuple fields
  IDE autocomplete   no                          yes
  Edit-time error    JSON linter only            mypy / Pyright
  Prop format        English prose string        compact inline notation
──────────────────────────────────────────────────────────────────────────────

Notation used in `props`:
  name        required field
  name?       optional field
  [a|b|c]     enum choices
  [{f1,f2}]   list of objects with those fields
  f?          optional within an object
"""
from __future__ import annotations
from typing import Dict, List, NamedTuple


class Spec(NamedTuple):
    """
    when  — ≤100-char rule for when the LLM should emit this component
    props — compact props signature already using KEY_ALIASES short keys
    """
    when:  str
    props: str


# ---------------------------------------------------------------------------
# Registry — ordered so the generated prompt reads most-used first
# ---------------------------------------------------------------------------

REGISTRY: Dict[str, Spec] = {

    # ── Alerts & text ────────────────────────────────────────────────────────
    "text": Spec(
        when="Fallback for any narrative; prefer richer components when structured data exists",
        props="ttl?,c,tn?:[neutral|positive|warning|error]",
    ),
    "highlight_box": Spec(
        when="safety_passed=false→var=error; intent=exit→var=success; any top-level critical alert",
        props="c,var:[success|warning|info|error]",
    ),

    # ── Number grids ─────────────────────────────────────────────────────────
    "statistic_grid": Spec(
        when="2–4 headline numbers: total kcal, protein, carbs, fat, restaurant count, score",
        props="ttl?,cols:[2|3],i:[{lbl,val,u?,var?:[default|success|warning|error]}]",
    ),
    "key_value_list": Spec(
        when="Labelled fact rows: per-food nutrients, restaurant address/hours/cuisine",
        props="ttl?,i:[{lbl,val,hl?}]",
    ),
    "comparison_table": Spec(
        when=">=3 foods side-by-side with columns=[Food,Calories,Protein,Fat,Sugar]",
        props="ttl?,cols:[str],rows:[[str|num]],footnote?",
    ),

    # ── Charts ───────────────────────────────────────────────────────────────
    "bar_chart": Spec(
        when="Horizontal bar comparison: calorie or nutrient breakdown across foods/restaurants",
        props="ttl?,u,i:[{lbl,val}],clr?:[css_colors]",
    ),
    "macro_chart": Spec(
        when="recognition with protein_g+carb_g+fat_g data: donut ring + per-macro bars",
        props="ttl?,prot,carb,fat,kcal?",
    ),
    "calorie_ring": Spec(
        when="recognition/meal-tracking when consumed+target known: full-circle progress ring",
        props="ttl?,con,tgt?,bkd?:[{lbl,val,clr}]",
    ),
    "health_score_card": Spec(
        when="Overall health score 0-100 with grade; score=100*(healthy/total) if absent",
        props="ttl?,sc,dims?:[{lbl,val,mx,var?:[success|warning|error]}]",
    ),
    "nutrient_gauge": Spec(
        when="Risky nutrients sodium/sugar/sat-fat - mini semicircle gauges vs daily limit",
        props="ttl?,gs:[{lbl,val,lim,u,var?}]",
    ),
    "progress_bar": Spec(
        when="Single goal bar: calorie intake vs daily goal; sugar vs limit",
        props="lbl,val,mx,u?,var?:[primary|success|warning|error]",
    ),

    # ── Nutrition ────────────────────────────────────────────────────────────
    "nutrition_label": Spec(
        when="Single food FDA/HPB-style panel; or user asks for label-style breakdown",
        props="ttl?,name,srv,cal,fat,sat?,sod?,carb,sug?,fib?,prot",
    ),
    "food_health_list": Spec(
        when="recognition: one row per detected food with health badge and macros",
        props="ttl?,i:[{name,cal,is_healthy,reasons?,prot?,fat?,carb?}]",
    ),

    # ── Restaurant ───────────────────────────────────────────────────────────
    "restaurant_list": Spec(
        when="recommendation: one card per restaurant with rating/price/distance/dishes",
        props="ttl?,i:[{name,rating?,price?,distance?,is_veg?,cuisine?,dishes?:[{name,cal?,is_healthy?}]}]",
    ),
    "ranking_list": Spec(
        when="recommendation: rank restaurants by rating or healthiest dishes by score",
        props="ttl?,i:[{name,val?,u?,sub?,badge_text?}]",
    ),

    # ── Meal planning ────────────────────────────────────────────────────────
    "meal_summary_row": Spec(
        when="Per-meal calorie breakdown (Breakfast/Lunch/Dinner/Snack) with mini bars",
        props="ttl?,daily_target,meals:[{name,icon,cal,clr?}]",
    ),

    # ── Misc ─────────────────────────────────────────────────────────────────
    "tip_card": Spec(
        when="1-2 personalised tips at END of recognition/recommendation layout",
        props="icon,ttl,c,tn?:[positive|caution|warning]",
    ),
    "tabs": Spec(
        when="Multi-day meal plans or categorised info benefiting from tabbed sections",
        props="ttl?,tabs:[{lbl,c}]",
    ),
    "tag_list": Spec(
        when="Cuisine tags, dietary flags (vegan/low-sugar), food category pills",
        props="ttl?,tags:[str]",
    ),

    # ── Layout ───────────────────────────────────────────────────────────────
    "columns": Spec(
        when="Two complementary visuals side-by-side: calorie_ring+macro_chart, score+gauge",
        props="secs:[section_objects],gap?",
    ),
    "divider": Spec(
        when="Thin rule separating logically distinct blocks in a long layout",
        props="",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_prompt_catalog() -> str:
    """
    One line per component, injected into the LLM prompt.
    Format:  name(props)  # when_to_use
    """
    lines: List[str] = []
    for name, spec in REGISTRY.items():
        line = f"{name}({spec.props})" if spec.props else name
        lines.append(f"{line}  # {spec.when[:95]}")
    return "\n".join(lines)


def component_names() -> List[str]:
    return list(REGISTRY.keys())


# Backward-compat shim for any code that still calls _load_components()
def as_legacy_dict() -> Dict[str, Dict[str, str]]:
    return {
        name: {"when": spec.when, "props": spec.props}
        for name, spec in REGISTRY.items()
    }
