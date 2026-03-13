# YouTube Batch Candidates — English Seed Set (20 targets)

Purpose: starter batch inputs for `youtube_intelligence_orchestrator.py --wedge-mode`.

Important: this file is intentionally built as a **curated target brief**, not a claim that every item below is the best current public video. Use it as the first overnight hunt list and replace with exact URLs you choose.

## Selection rule

Prioritize videos where the creator is:
- showing a real workflow,
- explaining a pain point,
- showing a monetization or operating system,
- discussing a specific buyer group,
- revealing process changes caused by AI, Etsy, ads, content, or creator ops.

Avoid videos that are mostly:
- motivation,
- vague productivity talk,
- broad news recap,
- generic "top 10 AI tools" without workflow depth.

## 20 target wedges to hunt in English YouTube

1. Etsy Meta Ads testing workflow
   - Search phrase: `etsy meta ads scaling workflow creative testing`
   - Goal: ad testing dashboards, KPI sheets, audit kits, mini-courses

2. Etsy SEO operating system
   - Search phrase: `etsy seo system 2026 ranking workflow`
   - Goal: seller dashboard, keyword tracker, checklist kit

3. Etsy listing optimization with AI
   - Search phrase: `etsy listing optimization ai prompts workflow`
   - Goal: prompt packs, listing OS, checklist + mini-course

4. Freelancer client CRM in Notion
   - Search phrase: `freelancer crm notion workflow client dashboard`
   - Goal: CRM workspace, SOP bundle, onboarding kit

5. Freelancer finance workflow
   - Search phrase: `freelancer finance tracker notion profit workflow`
   - Goal: finance OS, calculator, tax checklist bundle

6. ADHD execution workflow in Notion
   - Search phrase: `adhd notion workflow weekly reset execution`
   - Goal: execution systems, wellness tracker, reset workflow

7. GoodNotes digital planning workflow
   - Search phrase: `goodnotes digital planning workflow 2026`
   - Goal: planning bundles, use-case-specific systems, guided kits

8. Creator brand consistency with Canva + AI
   - Search phrase: `canva brand kit ai brand consistency workflow`
   - Goal: brand kits, prompt libraries, creator OS

9. Midjourney consistency workflow
   - Search phrase: `midjourney consistency prompts commercial workflow`
   - Goal: consistency systems, commercial-use bundles, prompt libraries

10. AI art commercial use workflow
    - Search phrase: `ai art commercial use prompts bundle licensing`
    - Goal: commercial-use kits, style guides, legal-safe bundles

11. Legal AI prompt workflow for professionals
    - Search phrase: `legal ai prompts workflow lawyers solopreneurs`
    - Goal: legal prompt packs, compliance checklists, workflow kits

12. Coach / consultant delivery workspace
    - Search phrase: `coach notion client delivery system workflow`
    - Goal: delivery OS, workbook + mini-course, client portal templates

13. Course portal / membership workflow
    - Search phrase: `course portal system workflow creator membership`
    - Goal: course portal templates, community OS, onboarding kits

14. Content creator operating system
    - Search phrase: `content creator operating system notion workflow`
    - Goal: content engine, calendar systems, brand workflow packs

15. AI prompt library workflow for creators
    - Search phrase: `prompt library workflow creators ai prompts`
    - Goal: prompt library bundles, swipe files, implementation kits

16. Digital product launch workflow
    - Search phrase: `digital product launch workflow etsy gumroad`
    - Goal: launch kits, checklist bundles, KPI dashboards

17. Small business dashboard workflow
    - Search phrase: `small business dashboard workflow template automation`
    - Goal: operations dashboard, KPI systems, client tracker bundles

18. Automation workflow in Notion
    - Search phrase: `automation notion workflow templates systems`
    - Goal: workflow kits, automation templates, workspace bundles

19. Creator monetization workflow
    - Search phrase: `creator monetization system digital products workflow`
    - Goal: monetization OS, offer kits, pricing calculators

20. Client onboarding + sales page workflow
    - Search phrase: `client onboarding sales page template workflow`
    - Goal: sales kits, onboarding workbooks, DFY offer bundles

## Recommended first overnight cluster strategy

Do not mix 20 random videos.

Run the first overnight batch as one of these clusters:

### Cluster A — Etsy growth
- items 1, 2, 3, 16, 17, 19

### Cluster B — Freelancer ops
- items 4, 5, 12, 18, 20

### Cluster C — Creator / AI content
- items 8, 9, 10, 14, 15, 19

### Cluster D — ADHD / planning systems
- items 6, 7, 14, 18

## Practical recommendation

First overnight run:
- pick one cluster only,
- use 10–20 videos from one theme,
- prefer one or two creators with repeated workflow language,
- avoid broad mixed batches until transcript reliability is confirmed.

## Input file reminder

The actual batch runner still needs exact URLs in a plain text file.
Create a file like:

`batch_urls.txt`

with one YouTube URL per line, then run:

`python3 youtube_intelligence_orchestrator.py --videos batch_urls.txt --wedge-mode`
