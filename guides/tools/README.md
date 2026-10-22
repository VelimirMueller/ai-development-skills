# 🧰 Tool guides

**Picture-first guides for the SaaS tools teams use every day, outside the code.**
Each guide fits on one screen: pictures first, few words, links for the deep dive.

| Tool | What it does | Guide |
|---|---|---|
| 📮 Brevo | Sends newsletters and app mails | [brevo/](brevo/README.md) |
| 🗃️ Airtable | A database that looks like a spreadsheet | [airtable/](airtable/README.md) |
| 📞 Aircall | A phone system in the cloud | [aircall/](aircall/README.md) |

## How every guide reads

1. **The parts** — one picture of everything in the tool.
2. **In one minute** — three bullets.
3. **Before → after** — what changes for you.
4. **How it works** — one or two flow pictures, then short steps.
5. **Words you will hear** — hard words in plain words.
6. **Watch out** — the traps that cost people hours.
7. **Do it** — "I want to …" → where to click or which API call.
8. **Go deeper** — links to the official docs.

## Add a tool

1. Copy [_TEMPLATE.md](_TEMPLATE.md) to `<tool>/README.md`.
2. Add the pictures to [_build/specs.json](_build/specs.json): one `hub`, one `before_after`, one or two `flow`.
3. Draw them: `python3 _build/gen_svg.py _build/specs.json .`
4. Check every link opens. Keep each bullet under about 15 words.

Pictures are plain SVG with a light and a dark theme. GitHub, VS Code and Obsidian show them.

## Company notes stay local

Put company-specific pages in `_private/<company>/`. Git ignores `_private/` (see `.gitignore`),
so company names, ids and decisions never reach this public repo. Give the folder its own
`specs.json` and draw its pictures with `python3 _build/gen_svg.py _private/<company>/specs.json _private/<company>`.

## Related skills

- [operate-airtable](../../skills/ops/operate-airtable/SKILL.md) — the Airtable skill for agents.
- [set-up-alerting](../../skills/ops/set-up-alerting/SKILL.md) — alerts for the tools above.
