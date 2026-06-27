# GW2 Progression — Icon System Specification

> Version: 1.1  
> Status: Delivered  
> Audience: Icon Designer / Frontend Engineer  
> Scope: Complete icon set for GW2 Progression OS UI

---

## 1. Design Principles

| Principle | Description |
|-----------|-------------|
| **GW2 Native** | Icons should feel native to the Guild Wars 2 UI language — clean, fantasy-crafted, silhouette-driven |
| **Semantic Clarity** | Each icon must communicate its function at a glance (scanability < 1s) |
| **Consistent Weight** | All icons use 2px stroke width with round caps / joins, balanced by angular Tyrian silhouettes |
| **Color Agnostic** | Icons are single-color (`currentColor`) and adapt to UI context via CSS |
| **Grid Based** | All icons sit on a 24×24px viewBox with 2px padding |

### Guild Wars 2 Style Direction

The delivered icons use an original GW2-inspired visual language without copying official game marks or art assets:

- **Tyrian geometry**: compass points, hexagonal crests, legendary starbursts, mystic crystals, vaults, coin stacks, parchment, and weapon silhouettes.
- **Readable fantasy craft**: simple line icons with a slightly ceremonial profile, avoiding generic app-only shapes when a GW2-adjacent metaphor is clearer.
- **Single-color production SVG**: every icon inherits `currentColor`, so the same SVG can read as gold, mystic purple, legendary orange, blue, red, or muted UI text.
- **UI-ready restraint**: no raster textures, gradients, shadows, or official logos; the GW2 flavor comes from silhouette and motif.

---

## 2. Grid & Technical Specs

```
ViewBox:     24 × 24px
Padding:     2px (live area: 20 × 20px)
Stroke:      2px
Cap:         round
Join:        round
Fill:        none (except status dots = fill)
Format:      SVG sprite (symbols) or individual .svg files
CSS:         `width: 1em; height: 1em; vertical-align: middle;`
Color:       `currentColor` via `fill="none" stroke="currentColor"`
```

Delivered files:

```text
docs/icons/gw2/icons.svg
docs/icons/gw2/ic-{icon-id}.svg
```

---

## 3. Complete Icon Inventory

### 3.1 Navigation Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `nav-account` | Account | Account overview / data dashboard | Compass rose or data grid with stylized GW2 compass needle | Top nav bar |
| `nav-insight` | Insight | AI intelligence / analysis | Crystal ball with inner glow lines or all-seeing eye with mystic aura | Top nav bar |
| `nav-plan` | Plan | Decision / action plan | Target reticle or legendary star marker | Top nav bar |

### 3.2 KPI / Metric Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `kpi-account-value` | Account Value | Total account wealth | Stack of coins with a gem at top, or an open treasure chest | KPI cards |
| `kpi-liquid-sell` | Liquid Gold (Sell) | Sell-side liquidity | Single coin with upward arrow or trading post scale | KPI cards |
| `kpi-liquid-buy` | Liquid Gold (Buy) | Buy-side liquidity | Single coin with downward arrow or buying hand | KPI cards |
| `kpi-hidden-wealth` | Hidden Wealth | Unpriced / dormant value | Mystic forge glow with question mark, or dormant volcano | KPI cards |
| `kpi-legendary` | Legendary Progress | Active legendary goals | Legendary precursor weapon outline or star fragment | KPI cards |
| `kpi-build-ready` | Build Readiness | Characters ready for builds | Armor stand with weapon, or crossed weapons | KPI cards |

### 3.3 Asset Category Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `asset-wallet` | Wallet | Liquid gold & currencies | Coin pouch or purse with GW2 emblem | Asset breakdown table |
| `asset-materials` | Material Storage | Crafting materials | Potion flask or stacked ore/crystals | Asset breakdown table |
| `asset-bank` | Bank | Bank storage | Treasure chest or vault door | Asset breakdown table |
| `asset-equipment` | Equipment | Equipped gear | Crossed sword + shield, or armor chestpiece | Asset breakdown table |
| `asset-inventory` | Character Inventory | Bag items | Backpack or bag with items | Asset breakdown table |
| `asset-shared` | Shared Inventory | Shared inventory slots | Shared chest with two arrows | Asset breakdown table |
| `asset-trading` | Trading Post | TP buy/sell orders | Auction house gavel or trading scale | Asset breakdown table |

### 3.4 AI Insight Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `insight-hidden-wealth` | Hidden Wealth | AI-detected dormant value | Crystal ball with sparkle or magnifying glass over treasure | Insight cards |
| `insight-build-ready` | Build Readiness | Character build analysis | Shield with checkmark or helmet on pedestal | Insight cards |
| `insight-legendary` | Legendary Progress | Goal tracking progress | Legendary star with progress ring | Insight cards |
| `insight-recommendation` | Recommendation | AI suggestion item | Scroll / parchment with quill | Insight recommendations |

### 3.5 Action / Control Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `action-key` | API Key | API key input | Key with GW2-style bow (ornamental head) | Key input section |
| `action-refresh` | Refresh | Sync / reload data | Circular arrow or GW2 update icon | Header actions |
| `action-export` | Export | Download / share | Download arrow into tray, or document with arrow | Header actions |
| `action-search` | Search | Item search | Magnifying glass with gear cog | Tool sections |
| `action-settings` | Settings | Configuration | Gear / cogwheel | Tool sections |
| `action-close` | Close | Dismiss panel | X mark | Modals / overlays |
| `action-chevron-right` | Chevron Right | Expand / next | Right-pointing chevron | Collapsible sections |

### 3.6 Status Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `status-active` | Active | Connected / healthy | Filled circle (small, 6px) | Status badge |
| `status-stale` | Stale | Data needs refresh | Filled circle, amber variant | Status badge |
| `status-error` | Error | Connection failed | Filled circle, red variant | Status badge |
| `status-check` | Check | Completed / done | Checkmark | Quest list / completed items |
| `status-unchecked` | Pending | Not yet done | Empty square outline | Quest list / pending items |
| `status-spinner` | Loading | In progress | Animated circle arc | Loading states |

### 3.7 Strategy Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `strategy-balanced` | Balanced | Equal priorities | Scales / balance | Strategy selector |
| `strategy-gold` | Gold | Gold focus | Coin stack with glow | Strategy selector |
| `strategy-build` | Build | Build focus | Anvil / crafting hammer | Strategy selector |
| `strategy-legendary` | Legendary | Legendary focus | Legendary star burst | Strategy selector |

### 3.8 Empty State Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `empty-account` | No Account Data | Awaiting analysis | Compass with no needle, or empty data sheet | Account page empty |
| `empty-insight` | No Insights | AI inactive | Dormant crystal ball | Insight page empty |
| `empty-plan` | No Plan | No plan generated | Blank scroll / empty map | Plan page empty |
| `empty-quest` | No Quests | No weekly quests | Empty checklist | Quest section |

### 3.9 Brand / Misc Icons

| ID | Name | Meaning | Visual Description | Used In |
|----|------|---------|-------------------|---------|
| `brand-mark` | Progression Mark | Brand identity icon | Interlocking G+P shape or stylized compass star | Header / favicon |
| `brand-ai-sparkle` | AI Sparkle | AI intelligence indicator | Tiny sparkle / star (used alongside AI labels) | Insight / AI sections |
| `external-link` | External Link | Opens new tab | Box with arrow | Documentation links |

---

## 4. Color Mapping

Icons inherit `currentColor` and adapt based on context:

```css
/* Default: dim text */
.icon { color: var(--gw2-text-dim); }

/* Active nav */
.nav button.active .icon { color: var(--gw2-gold); }

/* KPI per-metric colors */
.kpi-card[data-metric="account_value"] .icon { color: var(--gw2-gold-light); }
.kpi-card[data-metric="hidden_wealth"] .icon { color: var(--gw2-mystic); }
.kpi-card[data-metric="legendary_progress"] .icon { color: var(--gw2-legendary); }
.kpi-card[data-metric="build_ready"] .icon { color: var(--gw2-blue); }

/* Status dots — filled, not stroked */
.status-active { fill: var(--gw2-green); stroke: none; }
.status-stale  { fill: var(--gw2-gold); stroke: none; }
.status-error  { fill: var(--gw2-red); stroke: none; }

/* Insight cards */
.insight-card .icon { color: inherit; }  /* card header color */
```

### CSS Variable Reference

```css
--gw2-gold:       #c8956c
--gw2-gold-light: #dfb48c
--gw2-mystic:     #9060b0
--gw2-legendary:  #e89830
--gw2-blue:       #5080a0
--gw2-green:      #5a8a5a
--gw2-red:        #c04040
--gw2-text-dim:   #88837a
--gw2-text:       #d0cdc8
--gw2-text-bright:#e8e5e0
```

---

## 5. Usage Examples

### HTML (SVG symbol)

```html
<!-- Define in sprite -->
<svg style="display:none">
  <symbol id="nav-account" viewBox="0 0 24 24">
    <!-- SVG paths here -->
  </symbol>
</svg>

<!-- Use anywhere -->
<svg class="icon" width="24" height="24">
  <use href="#nav-account" />
</svg>
```

### CSS

```css
.icon {
  width: 1em;
  height: 1em;
  vertical-align: middle;
  display: inline-block;
}
```

### Inline use

```html
<button class="nav-btn">
  <svg class="icon" width="20" height="20"><use href="#nav-account"/></svg>
  Account
</button>
```

---

## 6. Delivery Format

| Deliverable | Format | Quantity |
|-------------|--------|----------|
| SVG sprite | [`docs/icons/gw2/icons.svg`](icons/gw2/icons.svg) (single file with `<symbol>` elements) | 1 file, 44 icons |
| Individual SVGs | `docs/icons/gw2/ic-{icon-id}.svg` (one per icon) | 44 files |
| React components | `{Name}Icon.tsx` (optional, for future frontend) | ~40 files |
| Figma / Sketch library | Shared icon component set | 1 library |

---

## 7. Priority for Implementation

| Priority | Icons | Quantity |
|----------|-------|----------|
| **P0 — Launch critical** | nav-*, kpi-*, action-key, action-refresh, status-* | 14 |
| **P1 — Core experience** | asset-*, insight-*, strategy-* | 14 |
| **P2 — Empty states** | empty-* | 4 |
| **P3 — Brand & polish** | brand-*, misc | ~8 |

---

## 8. Delivered SVG Index

### Navigation

| Icon | ID | SVG |
|------|----|-----|
| ![nav-account](icons/gw2/ic-nav-account.svg) | `nav-account` | [`ic-nav-account.svg`](icons/gw2/ic-nav-account.svg) |
| ![nav-insight](icons/gw2/ic-nav-insight.svg) | `nav-insight` | [`ic-nav-insight.svg`](icons/gw2/ic-nav-insight.svg) |
| ![nav-plan](icons/gw2/ic-nav-plan.svg) | `nav-plan` | [`ic-nav-plan.svg`](icons/gw2/ic-nav-plan.svg) |

### KPI / Metric

| Icon | ID | SVG |
|------|----|-----|
| ![kpi-account-value](icons/gw2/ic-kpi-account-value.svg) | `kpi-account-value` | [`ic-kpi-account-value.svg`](icons/gw2/ic-kpi-account-value.svg) |
| ![kpi-liquid-sell](icons/gw2/ic-kpi-liquid-sell.svg) | `kpi-liquid-sell` | [`ic-kpi-liquid-sell.svg`](icons/gw2/ic-kpi-liquid-sell.svg) |
| ![kpi-liquid-buy](icons/gw2/ic-kpi-liquid-buy.svg) | `kpi-liquid-buy` | [`ic-kpi-liquid-buy.svg`](icons/gw2/ic-kpi-liquid-buy.svg) |
| ![kpi-hidden-wealth](icons/gw2/ic-kpi-hidden-wealth.svg) | `kpi-hidden-wealth` | [`ic-kpi-hidden-wealth.svg`](icons/gw2/ic-kpi-hidden-wealth.svg) |
| ![kpi-legendary](icons/gw2/ic-kpi-legendary.svg) | `kpi-legendary` | [`ic-kpi-legendary.svg`](icons/gw2/ic-kpi-legendary.svg) |
| ![kpi-build-ready](icons/gw2/ic-kpi-build-ready.svg) | `kpi-build-ready` | [`ic-kpi-build-ready.svg`](icons/gw2/ic-kpi-build-ready.svg) |

### Assets

| Icon | ID | SVG |
|------|----|-----|
| ![asset-wallet](icons/gw2/ic-asset-wallet.svg) | `asset-wallet` | [`ic-asset-wallet.svg`](icons/gw2/ic-asset-wallet.svg) |
| ![asset-materials](icons/gw2/ic-asset-materials.svg) | `asset-materials` | [`ic-asset-materials.svg`](icons/gw2/ic-asset-materials.svg) |
| ![asset-bank](icons/gw2/ic-asset-bank.svg) | `asset-bank` | [`ic-asset-bank.svg`](icons/gw2/ic-asset-bank.svg) |
| ![asset-equipment](icons/gw2/ic-asset-equipment.svg) | `asset-equipment` | [`ic-asset-equipment.svg`](icons/gw2/ic-asset-equipment.svg) |
| ![asset-inventory](icons/gw2/ic-asset-inventory.svg) | `asset-inventory` | [`ic-asset-inventory.svg`](icons/gw2/ic-asset-inventory.svg) |
| ![asset-shared](icons/gw2/ic-asset-shared.svg) | `asset-shared` | [`ic-asset-shared.svg`](icons/gw2/ic-asset-shared.svg) |
| ![asset-trading](icons/gw2/ic-asset-trading.svg) | `asset-trading` | [`ic-asset-trading.svg`](icons/gw2/ic-asset-trading.svg) |

### Insights

| Icon | ID | SVG |
|------|----|-----|
| ![insight-hidden-wealth](icons/gw2/ic-insight-hidden-wealth.svg) | `insight-hidden-wealth` | [`ic-insight-hidden-wealth.svg`](icons/gw2/ic-insight-hidden-wealth.svg) |
| ![insight-build-ready](icons/gw2/ic-insight-build-ready.svg) | `insight-build-ready` | [`ic-insight-build-ready.svg`](icons/gw2/ic-insight-build-ready.svg) |
| ![insight-legendary](icons/gw2/ic-insight-legendary.svg) | `insight-legendary` | [`ic-insight-legendary.svg`](icons/gw2/ic-insight-legendary.svg) |
| ![insight-recommendation](icons/gw2/ic-insight-recommendation.svg) | `insight-recommendation` | [`ic-insight-recommendation.svg`](icons/gw2/ic-insight-recommendation.svg) |

### Actions / Controls

| Icon | ID | SVG |
|------|----|-----|
| ![action-key](icons/gw2/ic-action-key.svg) | `action-key` | [`ic-action-key.svg`](icons/gw2/ic-action-key.svg) |
| ![action-refresh](icons/gw2/ic-action-refresh.svg) | `action-refresh` | [`ic-action-refresh.svg`](icons/gw2/ic-action-refresh.svg) |
| ![action-export](icons/gw2/ic-action-export.svg) | `action-export` | [`ic-action-export.svg`](icons/gw2/ic-action-export.svg) |
| ![action-search](icons/gw2/ic-action-search.svg) | `action-search` | [`ic-action-search.svg`](icons/gw2/ic-action-search.svg) |
| ![action-settings](icons/gw2/ic-action-settings.svg) | `action-settings` | [`ic-action-settings.svg`](icons/gw2/ic-action-settings.svg) |
| ![action-close](icons/gw2/ic-action-close.svg) | `action-close` | [`ic-action-close.svg`](icons/gw2/ic-action-close.svg) |
| ![action-chevron-right](icons/gw2/ic-action-chevron-right.svg) | `action-chevron-right` | [`ic-action-chevron-right.svg`](icons/gw2/ic-action-chevron-right.svg) |

### Status

| Icon | ID | SVG |
|------|----|-----|
| ![status-active](icons/gw2/ic-status-active.svg) | `status-active` | [`ic-status-active.svg`](icons/gw2/ic-status-active.svg) |
| ![status-stale](icons/gw2/ic-status-stale.svg) | `status-stale` | [`ic-status-stale.svg`](icons/gw2/ic-status-stale.svg) |
| ![status-error](icons/gw2/ic-status-error.svg) | `status-error` | [`ic-status-error.svg`](icons/gw2/ic-status-error.svg) |
| ![status-check](icons/gw2/ic-status-check.svg) | `status-check` | [`ic-status-check.svg`](icons/gw2/ic-status-check.svg) |
| ![status-unchecked](icons/gw2/ic-status-unchecked.svg) | `status-unchecked` | [`ic-status-unchecked.svg`](icons/gw2/ic-status-unchecked.svg) |
| ![status-spinner](icons/gw2/ic-status-spinner.svg) | `status-spinner` | [`ic-status-spinner.svg`](icons/gw2/ic-status-spinner.svg) |

### Strategy

| Icon | ID | SVG |
|------|----|-----|
| ![strategy-balanced](icons/gw2/ic-strategy-balanced.svg) | `strategy-balanced` | [`ic-strategy-balanced.svg`](icons/gw2/ic-strategy-balanced.svg) |
| ![strategy-gold](icons/gw2/ic-strategy-gold.svg) | `strategy-gold` | [`ic-strategy-gold.svg`](icons/gw2/ic-strategy-gold.svg) |
| ![strategy-build](icons/gw2/ic-strategy-build.svg) | `strategy-build` | [`ic-strategy-build.svg`](icons/gw2/ic-strategy-build.svg) |
| ![strategy-legendary](icons/gw2/ic-strategy-legendary.svg) | `strategy-legendary` | [`ic-strategy-legendary.svg`](icons/gw2/ic-strategy-legendary.svg) |

### Empty States

| Icon | ID | SVG |
|------|----|-----|
| ![empty-account](icons/gw2/ic-empty-account.svg) | `empty-account` | [`ic-empty-account.svg`](icons/gw2/ic-empty-account.svg) |
| ![empty-insight](icons/gw2/ic-empty-insight.svg) | `empty-insight` | [`ic-empty-insight.svg`](icons/gw2/ic-empty-insight.svg) |
| ![empty-plan](icons/gw2/ic-empty-plan.svg) | `empty-plan` | [`ic-empty-plan.svg`](icons/gw2/ic-empty-plan.svg) |
| ![empty-quest](icons/gw2/ic-empty-quest.svg) | `empty-quest` | [`ic-empty-quest.svg`](icons/gw2/ic-empty-quest.svg) |

### Brand / Misc

| Icon | ID | SVG |
|------|----|-----|
| ![brand-mark](icons/gw2/ic-brand-mark.svg) | `brand-mark` | [`ic-brand-mark.svg`](icons/gw2/ic-brand-mark.svg) |
| ![brand-ai-sparkle](icons/gw2/ic-brand-ai-sparkle.svg) | `brand-ai-sparkle` | [`ic-brand-ai-sparkle.svg`](icons/gw2/ic-brand-ai-sparkle.svg) |
| ![external-link](icons/gw2/ic-external-link.svg) | `external-link` | [`ic-external-link.svg`](icons/gw2/ic-external-link.svg) |

---

## 9. Visual References

For the icon designer, please reference:

1. **Guild Wars 2 in-game UI** — skill icons, buff bars, inventory icons (linear, high-contrast)
2. **GW2 official website** — footer social icons, navigation markers
3. **gw2efficiency** — clean functional icons for data categories
4. **Material Design Icons** — grid discipline and stroke consistency
5. **Feather Icons** — 24×24 grid, 2px stroke, round caps — this is the closest production reference

---

## 10. Review Checklist

Before final delivery, each icon should pass:

- [x] Fits within 24×24 viewBox with 2px padding
- [x] 2px stroke width throughout
- [x] Round caps and joins
- [ ] Recognizable at 16×16px size
- [ ] Recognizable at 32×32px size
- [ ] No overlapping stroke artifacts
- [ ] Consistent visual weight with sibling icons
- [x] Works in `currentColor` on dark backgrounds
- [ ] Passes accessibility contrast check
- [ ] Approved by product team
