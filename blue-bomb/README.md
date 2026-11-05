# Blue Bomb — the in-house AI agency

Blue Bomb is a small AI agency made of Claude Code agents. It does the marketing for
two clients: **Goodbye Coffee** (the primary brand since May 5, 2026) and **Goodbye Cycle**
(the leaner dropship brand).

## How to use it

In Claude Code, from the root of this repo, type:

```
/blue-bomb <your brief>
```

Examples:

- `/blue-bomb 3 Instagram posts announcing the new Featured Roaster`
- `/blue-bomb Facebook ad set for Goodbye Cycle's winter sale, $300 budget`
- `/blue-bomb Coffee Mug Stories script set at a cyclocross race`
- `/blue-bomb how did last month's ads do?`

The Account Lead reads the brief, picks the brand, and hands the work down the team.
Everything the team makes lands in `blue-bomb/work/<date>-<slug>/`. **Nothing gets posted
or spent until you approve it.**

## The team

```
                    You (Andy)
                        │  brief / approve
                        ▼
              ┌──────────────────────┐
              │   Account Lead       │  /blue-bomb skill
              │   routes + assembles │
              └─────────┬────────────┘
     ┌─────────────┬────┴────────┬──────────────┬──────────────┐
     ▼             ▼             ▼              ▼              ▼
 Strategist    Copywriter   Art Director    Brand Guard     Analyst
 the angle,    hooks, posts, image/video     checks every   reads ad,
 audience,     ads, emails,  prompts, Canva  piece against  shop + social
 channel mix   scripts       designs         brand rules    numbers
```

| Agent | File | Job |
|---|---|---|
| Account Lead | `.claude/skills/blue-bomb/SKILL.md` | Takes your brief, picks the brand, runs the team, hands you one package |
| Strategist | `.claude/agents/bluebomb-strategist.md` | One-page creative brief: goal, audience, angle, channels, KPI |
| Copywriter | `.claude/agents/bluebomb-copywriter.md` | Writes the words — 3 variants of everything |
| Art Director | `.claude/agents/bluebomb-art-director.md` | Visual direction, generation prompts, Canva designs |
| Brand Guard | `.claude/agents/bluebomb-brand-guard.md` | Pass/fail check against the brand rules before you see it |
| Analyst | `.claude/agents/bluebomb-analyst.md` | Pulls performance numbers and says what to do next |

## Client files

- `brands/goodbye-coffee.md` — brand rules (voice, palette, Coffee Mug Stories, Featured Roaster)
- `brands/goodbye-cycle.md` — brand rules for the dropship store (**has blanks to fill in**)

Edit those files to teach the agency. Every agent reads them before working.

## Tools the team can use (when connected)

Canva (designs), Shopify (products, sales), Facebook Ads (performance — needs authorizing
in claude.ai connector settings), Postiz (scheduling drafts), Gmail (drafts only).
