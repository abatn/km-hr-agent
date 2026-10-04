# Sprachtemplates – Französisch (FR)

> **Geltungsbereich:** Alle Ausgaben des KM-HR-Agenten auf Französisch  
> **Stand:** September 2026

---

## Rapport de Matching

### En-tête
```
RAPPORT DE MATCHING
Date: {DATUM}
Candidat: {NAME}
Poste: {POSITION} chez {UNTERNEHMEN}
```

### Score
```
Évaluation globale: {SCORE}/100 ({KATEGORIE})

Évaluation par catégorie:
- Compétences clés: {SCORE_K}/30
- Expérience professionnelle: {SCORE_E}/25
- Formation: {SCORE_B}/15
- Localisation: {SCORE_S}/10
- Connaissance du secteur: {SCORE_BR}/10
- Compétences sociales: {SCORE_SS}/10
```

### Recommandation
| Score | Recommandation |
|---|---|
| 90–100 | Inviter immédiatement |
| 75–89 | Inviter |
| 60–74 | Inviter sous réserve – Questions d'entretien à clarifier |
| 40–59 | Ne pas inviter – Documenter la raison |
| 0–39 | Ne pas inviter |

---

## Liste de formation (Onboarding)

### E-mail de bienvenue
```
Objet: Bienvenue dans l'équipe, {NAME}!

Bonjour {NAME},

Nous sommes ravis de vous accueillir dans l'équipe {ABTEILUNG} à partir du {EINTRITTSDATUM}.

Vous trouverez ci-dessous toutes les informations importantes pour vos premières semaines.

Votre contact: {MENTOR}
```

### Équipement informatique
```
Équipement pour {NAME}:
☐ Ordinateur commandé
☐ Compte e-mail créé
☐ Accès VPN configuré
☐ Licences logicielles commandées
☐ Matériel (souris, clavier) commandé
```

### Plan d'intégration
```
Semaine 1: Prise de connaissance
- [ ] Jour 1: Accueil, remise IT
- [ ] Jour 2: Présentation des outils, de l'équipe
- [ ] Jour 3: Vue d'ensemble des processus
- [ ] Jour 4: Première tâche
- [ ] Jour 5: Questions, premier feedback

Semaine 2–4: Formation
- [ ] Tâches autonomes
- [ ] 1:1 avec le manager
- [ ] Participation aux sprints
- [ ] Fixation d'objectifs
```

---

## Questions de feedback

```
Comment évaluez-vous le matching pour {KANDIDAT} × {STELLE}?

1. Le matching était-il techniquement correct? (1–5)
2. Les compétences clés ont-elles été correctement identifiées? (1–5)
3. L'évaluation de la localisation était-elle pertinente? (1–5)
4. La recommandation était-elle utile? (1–5)
5. Le candidat a-t-il été invité? (Oui/Non/A prévoir)
6. Y a-t-il eu des problèmes de conformité? (Oui/Non)
7. Autres remarques (texte libre)
```

---

## Messages d'erreur

```
⚠️ Erreur: {FEHLERBESCHREIBUNG}

Ce qui s'est passé: {TECHNISCHE_ERKLÄRUNG}
Ce que vous pouvez faire: {LÖSUNG}
Alternative: {WORKAROUND}
```

---

## Rapport de conformité

```
RAPPORT DE CONFORMITÉ
Pays vérifiés: {LÄNDER}
Statut: {STATUS}

Résultats:
| Point de contrôle | Pays | Statut | Détails |
|---|---|---|---|
| {PRÜFPUNKT} | {LAND} | {STATUS} | {DETAILS} |

Recommandation: {EMPFEHLUNG}
```
