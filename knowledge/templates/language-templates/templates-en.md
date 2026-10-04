# Language Templates – English (EN)

> **Scope:** All KM-HR-Agent outputs in English  
> **Version:** September 2026

---

## Match Report

### Header
```
MATCH REPORT
Date: {DATUM}
Candidate: {NAME}
Position: {POSITION} at {UNTERNEHMEN}
```

### Score
```
Overall Rating: {SCORE}/100 ({KATEGORIE})

Rating by Category:
- Core Competencies: {SCORE_K}/30
- Work Experience: {SCORE_E}/25
- Education: {SCORE_B}/15
- Location: {SCORE_S}/10
- Industry Knowledge: {SCORE_BR}/10
- Soft Skills: {SCORE_SS}/10
```

### Recommendation
| Score | Recommendation |
|---|---|
| 90–100 | Invite immediately |
| 75–89 | Invite |
| 60–74 | Conditional invite – Clarify interview questions |
| 40–59 | Do not invite – Document reason |
| 0–39 | Do not invite |

---

## Onboarding Checklist

### Welcome Email
```
Subject: Welcome to the team, {NAME}!

Hi {NAME},

We're excited to have you join the {ABTEILUNG} team starting {EINTRITTSDATUM}.

Please find all important information for your first weeks below.

Your point of contact: {MENTOR}
```

### IT Equipment
```
IT Equipment for {NAME}:
☐ Laptop ordered
☐ Email account created
☐ VPN access configured
☐ Software licenses ordered
☐ Hardware (mouse, keyboard) ordered
```

### Onboarding Plan
```
Week 1: Getting Started
- [ ] Day 1: Welcome, IT handover
- [ ] Day 2: Tool introduction, team introduction
- [ ] Day 3: Process overview
- [ ] Day 4: First small task
- [ ] Day 5: Questions, first feedback

Week 2–4: Integration
- [ ] Independent tasks
- [ ] 1:1s with team lead
- [ ] Sprint participation
- [ ] Goal setting
```

---

## Feedback Questions

```
How would you rate the match for {KANDIDAT} × {STELLE}?

1. Was the match technically correct? (1–5)
2. Were the key skills correctly identified? (1–5)
3. Was the location assessment accurate? (1–5)
4. Was the recommendation helpful? (1–5)
5. Was the candidate invited? (Yes/No/Shortlisted)
6. Were there any compliance issues? (Yes/No)
7. Other comments (free text)
```

---

## Error Messages

```
⚠️ Error: {FEHLERBESCHREIBUNG}

What happened: {TECHNISCHE_ERKLÄRUNG}
What you can do: {LÖSUNG}
Alternative: {WORKAROUND}
```

---

## Compliance Report

```
COMPLIANCE REPORT
Countries checked: {LÄNDER}
Status: {STATUS}

Results:
| Check Point | Country | Status | Details |
|---|---|---|---|
| {PRÜFPUNKT} | {LAND} | {STATUS} | {DETAILS} |

Recommendation: {EMPFEHLUNG}
```
