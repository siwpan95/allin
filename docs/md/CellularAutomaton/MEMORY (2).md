# Cellular Automaton Project Memory

## 2026-07-02: Major refactoring — JSON/Python separation + rule expansion + auto-cycle

### What was done
1. **JSON/Python separation**: Created `rules/json/` directory with 8 JSON files containing all rule definitions (names, parameters, presets, descriptions). Created `rules/rule_manager.py` (RuleManager class) that reads JSON and dynamically creates Python rule instances. Each JSON has a `rule_family` field for correct dispatching.
2. **Rule expansion**: From 38 → 141 rules. Life-like rules expanded from 10 → 63 (from ConwayLife wiki). Gray-Scott from 5 → 23 presets (Pearson parameters). Lenia from 2 → 6 species. LtL from 6 → 9 presets. Wolfram from 4 → 15. Added new SandpileRule.
3. **Auto-cycle**: Added AutoCycleState class in `ui/input_handler.py`. Config fields: auto_cycle_rules, auto_cycle_interval, auto_cycle_theme_interval, auto_cycle_pause_after_manual. CLI flags: `--auto-cycle`, `--cycle-interval`. Key binding: A toggles auto-cycle in main.py mode. Manual TAB/T overrides pause auto-cycling for 5 min.
4. **Testing**: All 141 rules pass step tests. All 5 test suites pass. LtL bug fixed (was detected as GrayScott due to missing rule_family field).
5. **Docs**: README.md and requirements.txt updated.

### Architecture
- `rules/json/*.json` → rule definitions (data)
- `rules/rule_manager.py` → RuleManager reads JSON, creates rule objects
- `rules/base.py`, `multi_state_rules.py`, etc. → Python computation logic only
- `rules/__init__.py` → exports RULES registry, total_count, helper functions
- Key: `rule_family` field in JSON distinguishes gray_scott vs lenia vs ltl vs elementary_1d

### File map
- rules/json/life_rules.json (63 rules)
- rules/json/multi_state_rules.json (9 rules)
- rules/json/complex_rules.json (11 rules)
- rules/json/gray_scott_rules.json (23 presets)
- rules/json/lenia_rules.json (6 species)
- rules/json/ltl_rules.json (9 presets)
- rules/json/elementary_1d_rules.json (15 rules)
- rules/json/other_continuous_rules.json (5 rules)
