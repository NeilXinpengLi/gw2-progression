# GW2Radar Lovable-inspired Player Intent Builder — Codex Development Spec

```text
Document ID: GW2RADAR_LOVABLE_INSPIRED_PLAYER_INTENT_BUILDER_CODEX_SPEC
Project: GW2Radar
Version: v0.1
Status: Codex-ready Development Specification
Target Platform: Codex
Purpose:
  Transform GW2Radar from a tool/dashboard system into an intent-driven Player OS,
  inspired by Lovable.dev's natural-language-to-product workflow.
```

---

## 0. Executive Summary

Lovable.dev 的核心启发不是“AI 写代码”，而是：

```text
用户表达目标
→ 系统自动组织复杂工程模块
→ 生成可用结果
→ 用户继续自然语言迭代
```

GW2Radar 应借鉴这种模式，从：

```text
Account / Legendary / Build / Market / KB / Graph / Report / Diagnostic
```

升级为：

```text
Player Intent
→ Account State
→ Decision
→ Plan
→ Report
→ Iteration
```

最终产品体验应从“玩家操作功能模块”变成“玩家表达目标，由系统生成成长计划”。

一句话目标：

> Lovable 是“用自然语言构建应用”；GW2Radar 应该是“用自然语言构建 GW2 成长计划”。

---

## 1. Product Transformation Goal

### 1.1 Current State

GW2Radar 当前偏向：

```text
功能入口驱动：
- Account Value
- Legendary Planner
- Build Fit
- Market Radar
- Diagnostic
- Debug Bundle
- KB / Evidence / Graph / Report
```

这种设计对开发者和运营人员清晰，但对普通玩家仍有认知负担。

### 1.2 Target State

GW2Radar 应升级为：

```text
目标入口驱动：
- 我很久没玩了，先做什么？
- 我想做 Aurora，今天该做什么？
- 我想玩 Power Reaper，我现在能不能玩？
- 我有哪些东西不能卖？
- 我每天只有 30 分钟，应该怎么安排？
- 我不想打 WvW，有没有替代路线？
```

系统自动将玩家意图路由到：

```text
Returner Engine
Legendary Engine
Build Fit Engine
Account Intelligence Dashboard
Report Engine
Evidence / KB / Rule / Graph Layer
```

---

## 2. Core Design Principle

```text
Do not make the player operate system modules.
Let the player express a goal.
The system selects modules, checks data, generates a plan, and explains it.
```

GW2Radar 新主链：

```text
Player Intent
    ↓
Intent Parser
    ↓
Constraint Extractor
    ↓
Intent Router
    ↓
Engine Orchestration
    ↓
Plan / Action / Report
    ↓
User Revision
    ↓
Replan / Report Revision
```

---

## 3. Target User Experience

### 3.1 Old Experience

```text
1. User opens dashboard.
2. User finds Account / Legendary / Build / Market modules.
3. User manually figures out which module to use.
4. User reads API-heavy output.
5. User must understand diagnostic if no result appears.
```

### 3.2 New Experience

```text
1. User opens /start or /now.
2. User selects a template or types a goal.
3. System checks account data and permissions.
4. System routes to the correct wizard.
5. System generates today / this week actions.
6. User can revise constraints in natural language.
7. System updates plan and report.
```

---

## 4. Main User Journeys

### 4.1 Returner Journey

User intent:

```text
我三年没玩了，想重新开始玩死灵，还想慢慢做 Aurora。
```

Parsed intent:

```yaml
PlayerIntent:
  intent_type: returner
  preferred_profession: Necromancer
  goal: Aurora
  pace: casual
  constraints:
    play_style: casual
```

System flow:

```text
1. Check API key connection.
2. Check account snapshot freshness.
3. Check Necromancer characters.
4. Check open-world playable build.
5. Check Aurora gap.
6. Generate top 3 actions today.
7. Generate 7-day recovery plan.
8. Generate Returner + Aurora mixed report.
```

Output:

```text
- What to do first
- Best character to restart with
- Systems to recover
- Goals to delay
- Aurora-safe actions
- Do-not-sell materials
- 7-day plan
```

---

### 4.2 Legendary Journey

User intent:

```text
我想做 Aurora，尽量少花金币，不想打 WvW。
```

Parsed intent:

```yaml
PlayerIntent:
  intent_type: legendary
  goal: Aurora
  constraints:
    spending_mode: cheap
    avoid_modes:
      - wvw
```

System flow:

```text
1. Create or load Aurora goal.
2. Check account materials, wallet, bank, achievements.
3. Check do-not-sell requirements.
4. Build cheap path.
5. Exclude WvW-heavy route if possible.
6. Generate missing requirements.
7. Generate daily and weekly actions.
8. Generate Legendary Planner report.
```

Output:

```text
- Missing requirements
- Do-not-sell list
- Cheap path
- Alternative route without WvW if feasible
- Assumptions and unsupported constraints
- Evidence and freshness
```

---

### 4.3 Build Fit Journey

User intent:

```text
我想玩 Open World Power Reaper，最多花 50 gold。
```

Parsed intent:

```yaml
PlayerIntent:
  intent_type: build_fit
  profession: Necromancer
  specialization: Reaper
  game_mode: open_world
  budget_gold_limit: 50
```

System flow:

```text
1. Identify target build template or ask user to choose source.
2. Load reviewed BuildMetadata.
3. Check character gear snapshot.
4. Calculate fit score.
5. Estimate transition cost.
6. If cost > 50g, generate budget alternative.
7. Generate Build Fit report.
```

Output:

```text
- Fit Score
- Playable now?
- Reusable gear
- Missing gear
- Rune / Sigil / Relic gap
- Estimated cost
- Budget alternative
- Patch freshness warning
```

---

## 5. New System Modules

Create new package:

```text
src/gw2radar/player_os/
├── intent/
│   ├── models.py
│   ├── intent_parser.py
│   ├── intent_templates.py
│   ├── constraint_extractor.py
│   ├── intent_validator.py
│   └── intent_router.py
├── workflows/
│   ├── returner_wizard.py
│   ├── legendary_wizard.py
│   ├── build_fit_wizard.py
│   └── what_should_i_do_now_wizard.py
├── iteration/
│   ├── plan_revision.py
│   ├── constraint_update.py
│   ├── what_if_engine.py
│   └── report_revision.py
├── governance/
│   ├── source_review_gate.py
│   ├── privacy_gate.py
│   ├── recommendation_safety_gate.py
│   ├── report_publication_gate.py
│   └── quota_budget_gate.py
└── orchestration/
    ├── player_os_orchestrator.py
    ├── engine_router.py
    └── workflow_state_machine.py
```

---

## 6. Data Models

### 6.1 PlayerIntent

```python
class PlayerIntent(BaseModel):
    intent_id: str
    account_id: str | None
    raw_text: str | None
    template_id: str | None
    intent_type: Literal[
        "returner",
        "legendary",
        "build_fit",
        "account_overview",
        "what_should_i_do_now",
        "market_watch",
        "unknown"
    ]
    goal_id: str | None
    profession: str | None
    specialization: str | None
    game_mode: str | None
    urgency: Literal["low", "medium", "high"]
    constraints: dict
    created_at: datetime
```

### 6.2 IntentTemplate

```python
class IntentTemplate(BaseModel):
    template_id: str
    name: str
    domain: Literal["returner", "legendary", "build_fit", "account", "market"]
    description: str
    default_intent_type: str
    default_constraints: dict
    required_permissions: list[str]
    recommended_next_questions: list[str]
    enabled: bool
```

### 6.3 PlayerConstraint

```python
class PlayerConstraint(BaseModel):
    constraint_id: str
    intent_id: str
    key: str
    value: Any
    source: Literal["template", "user_text", "ui_selection", "system_default"]
    confidence: float
```

Common constraints:

```yaml
daily_time_limit:
spending_mode:
budget_gold_limit:
avoid_modes:
preferred_modes:
pace:
risk_tolerance:
prefer_farming:
conservative_sell_policy:
preferred_profession:
preferred_role:
```

### 6.4 WorkflowState

```python
class WorkflowState(BaseModel):
    workflow_id: str
    intent_id: str
    workflow_type: str
    status: Literal[
        "created",
        "checking_account",
        "needs_api_key",
        "needs_permission",
        "syncing",
        "analyzing",
        "needs_user_choice",
        "planning",
        "ready",
        "failed"
    ]
    current_step: str
    required_user_actions: list[str]
    warnings: list[str]
    evidence_refs: list[str]
```

### 6.5 PlanRevisionRequest

```python
class PlanRevisionRequest(BaseModel):
    plan_id: str
    raw_revision_text: str
    constraints_delta: dict
    requested_by: str
```

Example:

```text
我每天只有 30 分钟，重新安排计划。
```

Parsed delta:

```yaml
daily_time_limit: 30m
```

---

## 7. Intent Layer

### 7.1 IntentParser

Responsibility:

```text
Convert raw player text into structured PlayerIntent.
```

Inputs:

```text
raw_text
account context
available templates
known goals
known builds
```

Outputs:

```text
PlayerIntent
PlayerConstraint list
Clarifying questions if needed
```

Rules:

```text
1. Parser may use LLM for classification.
2. Parser must not invent account facts.
3. Parser must not infer missing private data.
4. Parser must produce confidence.
5. Low confidence intent must ask clarification.
```

### 7.2 IntentRouter

Routes intent to workflow:

```text
returner → ReturnerWizard
legendary → LegendaryWizard
build_fit → BuildFitWizard
what_should_i_do_now → WhatShouldIDoNowWizard
```

### 7.3 IntentValidator

Checks:

```text
1. Required API permissions.
2. Account sync freshness.
3. Required KB review status.
4. Source freshness.
5. Whether strong recommendation is allowed.
```

---

## 8. Template Layer

Create template directory:

```text
docs/templates/
├── returner/
│   ├── long_break_open_world.yaml
│   ├── return_to_fractals.yaml
│   └── casual_legendary_start.yaml
├── legendary/
│   ├── aurora_fast_path.yaml
│   ├── aurora_cheap_path.yaml
│   ├── aurora_balanced_path.yaml
│   └── vision_balanced_path.yaml
├── build/
│   ├── open_world_low_budget.yaml
│   ├── fractal_entry.yaml
│   ├── strike_ready.yaml
│   └── wvw_zerg_check.yaml
└── account/
    ├── what_should_i_do_now.yaml
    └── do_not_sell_check.yaml
```

### 8.1 Template Example: Returner

```yaml
template_id: returner.long_break_open_world
name: "I am returning after a long break"
domain: returner
description: "Recover your account and get a safe 7-day plan."
default_intent_type: returner
default_constraints:
  pace: casual
  preferred_modes:
    - open_world
  conservative_sell_policy: true
required_permissions:
  - account
  - characters
  - inventories
  - wallet
  - progression
recommended_next_questions:
  - "How long have you been away?"
  - "Which game mode do you want to return to?"
  - "Do you have a preferred profession?"
enabled: true
```

### 8.2 Template Example: Legendary

```yaml
template_id: legendary.aurora_cheap_path
name: "Aurora Cheap Path"
domain: legendary
description: "Plan Aurora with minimum gold spending."
default_intent_type: legendary
default_constraints:
  goal_id: gw2:goal:aurora
  spending_mode: cheap
  prefer_farming: true
  conservative_sell_policy: true
required_permissions:
  - account
  - inventories
  - wallet
  - progression
recommended_next_questions:
  - "How much gold are you willing to spend?"
  - "Do you want to avoid WvW or group content?"
enabled: true
```

### 8.3 Template Example: Build

```yaml
template_id: build.open_world_low_budget
name: "Open World Low Budget Build"
domain: build_fit
description: "Check whether your account can play a low-cost open-world build."
default_intent_type: build_fit
default_constraints:
  game_mode: open_world
  budget_gold_limit: 50
  prefer_budget_alternative: true
required_permissions:
  - characters
  - inventories
  - builds
recommended_next_questions:
  - "Which profession do you want to play?"
  - "Do you want a low-cost or optimized build?"
enabled: true
```

---

## 9. Guided Workflows

### 9.1 ReturnerWizard

Responsibilities:

```text
1. Check account connection.
2. Check account freshness.
3. Ask returner questions.
4. Build AccountReadiness.
5. Recommend strongest playable character.
6. Generate 7-day recovery plan.
7. Generate Returner report.
```

Workflow states:

```text
start
→ check_account
→ ask_returner_questions
→ analyze_readiness
→ generate_plan
→ report_preview
→ full_report
```

### 9.2 LegendaryWizard

Responsibilities:

```text
1. Select or create legendary goal.
2. Apply constraints.
3. Resolve owned/missing.
4. Generate do-not-sell.
5. Generate cheap / fast / balanced routes.
6. Generate Legendary report.
```

Workflow states:

```text
start
→ select_goal
→ choose_route_mode
→ analyze_gap
→ generate_do_not_sell
→ generate_plan
→ report_preview
→ full_report
```

### 9.3 BuildFitWizard

Responsibilities:

```text
1. Select reviewed build or import structured build.
2. Select character.
3. Check account gear.
4. Calculate fit score.
5. Generate transition plan.
6. Generate budget alternative.
7. Generate Build Fit report.
```

Workflow states:

```text
start
→ select_build
→ select_character
→ analyze_fit
→ transition_plan
→ report_preview
→ full_report
```

### 9.4 WhatShouldIDoNowWizard

Responsibilities:

```text
1. Load account state.
2. Load active goals.
3. Load current readiness.
4. Generate top 3 actions.
5. Explain why.
6. Link to detailed workflows.
```

Output:

```yaml
NowResult:
  focus:
  top_actions:
    - title
    - reason
    - linked_goal
    - urgency
    - evidence_refs
  warnings:
  stale_data_notes:
```

---

## 10. Iteration Layer

### 10.1 PlanRevisionService

User can revise a plan:

```text
我每天只有 30 分钟。
我不想打 WvW。
我不想花金币。
我只想玩 Open World。
我想更快完成。
```

System behavior:

```text
1. Parse revision text.
2. Extract constraint changes.
3. Validate feasibility.
4. Re-run planner.
5. Show difference from previous plan.
6. Update report assumptions.
```

### 10.2 WhatIfEngine

Examples:

```text
What if I spend 100g?
What if I avoid WvW?
What if I switch to Reaper?
What if I only play weekends?
```

Output:

```yaml
WhatIfResult:
  changed_constraints:
  plan_delta:
  cost_delta:
  time_delta:
  feasibility:
  warnings:
```

### 10.3 ReportRevisionService

Report can be revised without regenerating everything:

```text
1. Preserve evidence.
2. Update constraints.
3. Re-render affected sections.
4. Increment report version.
5. Keep audit trail.
```

---

## 11. Governance Gates

### 11.1 SourceReviewGate

```text
Blocks strong recommendations if source is unreviewed or expired.
```

### 11.2 PrivacyGate

```text
Blocks private account data from entering public KB, public reports, or shared URLs.
```

### 11.3 RecommendationSafetyGate

```text
Blocks:
- automated trading
- guaranteed profit language
- gameplay automation
- unsupported facts
- unreviewed build as strong recommendation
```

### 11.4 ReportPublicationGate

Paid/full report can be generated only when:

```text
1. account data is fresh or explicitly marked stale;
2. private data is protected;
3. required KB/rules are reviewed;
4. evidence coverage meets minimum threshold;
5. report clearly states assumptions.
```

### 11.5 QuotaBudgetGate

Controls:

```text
GW2 API refresh budget
LLM explanation budget
PDF extraction budget
Market price refresh budget
Report generation quota
```

Example plans:

```text
Free:
- one account sync per day
- one free preview
- low-frequency market refresh

Pro:
- more frequent sync
- multiple goal portfolios
- full reports
- weekly plans
```

---

## 12. API Design

### 12.1 Intent APIs

```http
POST /api/v1/intents/parse
POST /api/v1/intents/start
GET  /api/v1/intents/{intent_id}
POST /api/v1/intents/{intent_id}/constraints
POST /api/v1/intents/{intent_id}/clarify
```

### 12.2 Template APIs

```http
GET  /api/v1/templates
GET  /api/v1/templates/{template_id}
POST /api/v1/templates/{template_id}/start
```

### 12.3 Workflow APIs

```http
GET  /api/v1/workflows/{workflow_id}
POST /api/v1/workflows/{workflow_id}/next
POST /api/v1/workflows/{workflow_id}/answer
POST /api/v1/workflows/{workflow_id}/cancel
```

### 12.4 Plan APIs

```http
GET  /api/v1/plans/{plan_id}
POST /api/v1/plans/{plan_id}/revise
POST /api/v1/plans/{plan_id}/what-if
GET  /api/v1/plans/{plan_id}/diff/{previous_version}
```

### 12.5 Report APIs

```http
GET  /api/v1/reports/{report_id}
POST /api/v1/reports/{report_id}/revise
GET  /api/v1/reports/{report_id}/versions
```

### 12.6 Now APIs

```http
GET  /api/v1/now
POST /api/v1/now/recompute
```

---

## 13. UI Pages

Create player-facing pages:

```text
/start
/now
/wizard/returner
/wizard/legendary
/wizard/build
/plan/revise
/report/revise
/templates
/help
```

### 13.1 /start

Purpose:

```text
Let player start from a goal or template.
```

UI cards:

```text
[ I am returning after a long break ]
[ I want to craft Aurora ]
[ I want to check my build ]
[ I want a 7-day progression plan ]
[ I want to know what not to sell ]
```

### 13.2 /now

Purpose:

```text
Show current best actions.
```

Main UI:

```text
What should I do now?

Top 3 Actions:
1. ...
2. ...
3. ...

Why:
- uses account snapshot synced X minutes ago
- uses reviewed KB/rules
- market data freshness: ...
```

### 13.3 Wizard Pages

Each wizard must include:

```text
1. Clear step indicator.
2. Player-facing questions.
3. Auto-detected account state.
4. Missing permissions warning.
5. Data freshness.
6. Preview result.
7. Full report CTA.
```

### 13.4 Plan Revision Page

Allows player to type:

```text
I only have 30 minutes per day.
Avoid WvW.
Use cheaper route.
```

System shows:

```text
Old plan
New plan
What changed
Assumptions
Warnings
```

### 13.5 Help Page

Player sees:

```text
Something not working?

[ Auto Diagnose ]
[ Contact Support ]
[ Delete API Key ]
[ Delete Account Data ]
```

Backend may call diagnostic/debug bundle internally, but user should not need to know endpoint names.

---

## 14. UI Components

```text
components/player_os/
├── IntentInputBox.tsx
├── IntentTemplateCard.tsx
├── ConstraintEditor.tsx
├── WorkflowStepper.tsx
├── NowActionCard.tsx
├── PlanDiffView.tsx
├── ReportRevisionPanel.tsx
├── EvidenceFreshnessBadge.tsx
├── SafetyWarningCard.tsx
├── PermissionMissingCard.tsx
├── TemplateGallery.tsx
└── SupportAssistantPanel.tsx
```

---

## 15. Codex Implementation Task

```text
PROJECT: GW2Radar

TASK:
Implement Lovable-inspired Player Intent Builder and Guided Workflow system.

GOAL:
Transform GW2Radar from a module/tool dashboard into an intent-driven Player OS.

IMPLEMENT:

1. Intent Layer
- PlayerIntent model
- PlayerConstraint model
- IntentTemplate model
- WorkflowState model
- IntentParser
- ConstraintExtractor
- IntentValidator
- IntentRouter

2. Template Layer
- Returner templates
- Legendary templates
- Build Fit templates
- Account / Do-not-sell templates
- Template loader
- Template API

3. Guided Workflow
- ReturnerWizard
- LegendaryWizard
- BuildFitWizard
- WhatShouldIDoNowWizard
- Workflow state machine

4. Iteration Layer
- PlanRevisionService
- ConstraintUpdateService
- WhatIfEngine
- ReportRevisionService
- Plan diff output

5. Governance
- SourceReviewGate
- PrivacyGate
- RecommendationSafetyGate
- ReportPublicationGate
- QuotaBudgetGate

6. UI Pages
- /start
- /now
- /wizard/returner
- /wizard/legendary
- /wizard/build
- /plan/revise
- /report/revise
- /templates
- /help

7. API
- POST /api/v1/intents/parse
- POST /api/v1/intents/start
- GET  /api/v1/intents/{intent_id}
- POST /api/v1/intents/{intent_id}/constraints
- GET  /api/v1/templates
- GET  /api/v1/templates/{template_id}
- POST /api/v1/templates/{template_id}/start
- GET  /api/v1/workflows/{workflow_id}
- POST /api/v1/workflows/{workflow_id}/next
- POST /api/v1/workflows/{workflow_id}/answer
- GET  /api/v1/plans/{plan_id}
- POST /api/v1/plans/{plan_id}/revise
- POST /api/v1/plans/{plan_id}/what-if
- GET  /api/v1/now
- POST /api/v1/now/recompute

HARD CONSTRAINTS:
- No gameplay automation.
- No automated trading.
- No API key exposure.
- No private data in public KB.
- No unreviewed source driving strong recommendation.
- No expired source driving paid-report strong recommendation.
- No guaranteed profit language.
- LLM may explain but must not invent facts.
- All generated plans are advisory only.

ACCEPTANCE:
- Player can start from natural language intent.
- Player can start from template.
- System routes intent to Returner / Legendary / Build Fit / Now workflow.
- Player can revise plan with constraints.
- System displays old plan vs new plan.
- Reports preserve evidence, assumptions, and freshness.
- Non-technical player can complete flow without seeing API endpoints.
- Help page hides diagnostic endpoints and shows friendly support actions.
```

---

## 16. Test Plan

Create tests:

```text
tests/player_os/test_intent_parser.py
tests/player_os/test_intent_router.py
tests/player_os/test_constraint_extractor.py
tests/player_os/test_intent_templates.py
tests/player_os/test_workflow_state_machine.py
tests/player_os/test_returner_wizard.py
tests/player_os/test_legendary_wizard.py
tests/player_os/test_build_fit_wizard.py
tests/player_os/test_now_wizard.py
tests/player_os/test_plan_revision.py
tests/player_os/test_what_if_engine.py
tests/player_os/test_report_revision.py
tests/player_os/test_governance_gates.py
tests/player_os/test_privacy_no_private_public_leak.py
tests/player_os/test_no_unreviewed_strong_recommendation.py
```

Test cases:

```text
1. "I have not played for 3 years" routes to ReturnerWizard.
2. "I want to craft Aurora cheaply" routes to LegendaryWizard with spending_mode=cheap.
3. "Can I play Power Reaper with 50 gold?" routes to BuildFitWizard.
4. "What should I do now?" routes to NowWizard.
5. Missing API permission produces friendly workflow state.
6. Player can revise plan with "30 minutes per day".
7. Avoid WvW modifies constraints.
8. Unreviewed build source blocks strong Build Fit recommendation.
9. Expired market source blocks strong buy/sell language.
10. Private account data never appears in public KB or template output.
11. API key never appears in intent, workflow, evidence, or report response.
```

---

## 17. Implementation Phases

### Phase 1 — Intent + Template MVP

```text
- PlayerIntent
- IntentParser
- IntentTemplate
- IntentRouter
- /start
- /api/v1/intents/parse
- /api/v1/templates
```

### Phase 2 — Guided Workflows

```text
- ReturnerWizard
- LegendaryWizard
- BuildFitWizard
- WhatShouldIDoNowWizard
- WorkflowStateMachine
```

### Phase 3 — Plan Revision

```text
- ConstraintExtractor
- PlanRevisionService
- WhatIfEngine
- PlanDiffView
```

### Phase 4 — Governance Gates

```text
- SourceReviewGate
- PrivacyGate
- RecommendationSafetyGate
- ReportPublicationGate
- QuotaBudgetGate
```

### Phase 5 — Player-facing UI

```text
- /start
- /now
- /wizard/*
- /plan/revise
- /report/revise
- /help
```

### Phase 6 — Commercial Integration

```text
- Free preview
- Full report CTA
- Entitlement check
- Quota budget
- Weekly plan subscription hook
```

---

## 18. Final Product Definition

GW2Radar should become:

```text
A Lovable-inspired Player OS for Guild Wars 2 progression planning.
```

Not:

```text
A dashboard with many tools.
```

But:

```text
A guided system where the player says what they want,
and the system generates the right plan, actions, and report.
```

Final product sentence:

> Lovable.dev lets users build apps from intent. GW2Radar should let GW2 players build progression plans from intent.
