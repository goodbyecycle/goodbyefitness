# Blue Bomb — the in-house AI agency

Blue Bomb is an AI marketing team built from Claude Code agents. It has two clients:
**Goodbye Coffee** (the primary brand since May 5, 2026) and **Goodbye Cycle** (the leaner
dropship brand).

It follows the same shape as ReStructure AI's "41-agent marketing team": a Brain,
departments, a knowledge layer, alarms, a Monday one-pager, and a human approval desk.
Blue Bomb uses **10 agents instead of 41**. Each department is one agent covering several
roles.

## How to use it

```
/blue-bomb <brief>     make something   e.g. /blue-bomb Meta ad set for the new Featured Roaster, $300
/blue-bomb monday      weekly loop      numbers + insights → one-page plan for the week
/blue-bomb check       alarm sweep      anything over budget, missing, or on fire?
```

Work lands in `blue-bomb/work/<date>-<slug>/`, with `package.md` as the final hand-off.
**Nothing is posted, sent or paid for until Andy says yes.**

## The org chart

```
 KNOWLEDGE LAYER                       ┌─────────────────────────────┐        ALARMS (owner.md)
 brands/  goodbye-coffee.md            │  THE BRAIN — /blue-bomb      │        spend over cap
          goodbye-cycle.md   ────────▶ │  Triage → Decide →           │ ◀───── campaign missing
 knowledge/ owner.md (goals, caps)     │  Create → Check              │        competitor move
            offers.md                  │  "Every Monday ends in       │        channel stalled
            channels.md                │   one page."                 │        bad reviews
            campaigns.md (memory)      └──────────────┬──────────────┘        creative running low
                                                      │
   ┌───────────────┬───────────────┬──────────────────┼──────────────────┬───────────────┬───────────────┐
   ▼               ▼               ▼                  ▼                  ▼               ▼               ▼
 MARKET         POSITIONING     CAMPAIGN ENGINE     PAID ADS          CONTENT &        EMAIL &        ANALYTICS
 INTELLIGENCE   & MESSAGING     copywriter          media-buyer       SOCIAL           LIFECYCLE      & BUDGET
 intel          strategist      art-director                          social           email          analyst
                                producer
                                      │
                                      ▼
                              BRAND GUARD (checks everything)
                                      │
                                      ▼
                       APPROVAL DESK → Andy says yes / no / revise
```

| Department (ReStructure's name) | Blue Bomb agent | Roles it covers |
|---|---|---|
| The Brain / AI CMO | `/blue-bomb` skill | triage, decide, create, check, Monday planner, approval desk |
| Market Intelligence | `bluebomb-intel` | competitor watcher, review miner, comment reader, trend spotter, insight brief |
| Positioning & Messaging | `bluebomb-strategist` | positioning, message picker, offer builder, audience mapper |
| Campaign Engine | `bluebomb-copywriter` | copywriter, campaign scripts |
| | `bluebomb-art-director` | creative studio (stills, Canva) |
| | `bluebomb-producer` | video, voiceover (ElevenLabs), Mugsy/Hedra |
| Paid Ads | `bluebomb-media-buyer` | Meta, Google & YouTube, TikTok, retargeting, ad tester |
| Content & Social | `bluebomb-social` | scheduler, short- and long-form poster, SEO writer, community replies |
| Email & Lifecycle | `bluebomb-email` | campaign emails, welcome, follow-ups, segmenter, win-back |
| Budget + Analytics | `bluebomb-analyst` | revenue, attribution, cost, channel scorer, budget mover, cut list, forecaster |
| (Brand Guard) | `bluebomb-brand-guard` | quality check on every piece |

## Fill these in first (they have `TBD`s)
1. `knowledge/owner.md` — goals, budget caps, the Slack channel for approvals
2. `knowledge/offers.md` — subscription price, Cycle→Coffee threshold
3. `knowledge/channels.md` — confirmed Goodbye Coffee handles, competitors to watch
4. `brands/goodbye-cycle.md` — what Goodbye Cycle sells, hero products, buyers

## Connected tools
Canva (designs), Shopify (sales, products), Gmail (drafts), Slack (approvals), Postiz
(scheduling drafts). The Facebook Ads connector needs authorizing in claude.ai connector
settings. The Higgsfield (AI video) connector is currently failing to connect.
