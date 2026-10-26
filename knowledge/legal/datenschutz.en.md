# Privacy Policy

> **Status: DRAFT (as of 26.10.2026)** — legal text, **to be reviewed by a lawyer**. Not legal advice.
> Structure follows **Art. 13 GDPR** (information duty when collecting personal data), extended by
> **Art. 27 GDPR** (EU representative) and **Art. 14 revFADP** (Swiss representative).
> **EN = translation of the German original** (not legally binding; the German version prevails).
> Missing details are marked **"[to be added]"** (lab principle: no inventions).

## 1. Controller and representatives

**Agic Tunisie GmbH**
13 rue des Usines, ZI Sidi Rezig, 2033 Ben Arous, Tunisia
Email: **batniniabdelkader@yahoo.com**
Phone: **+216 52 369 325**
Website: **https://jobs.hanibal-ai.com**
Authorised representative: **Mohamed Larbi Nakti**
Registration number (matricule fiscal): **1096754W**
RNE number (Registre National des Entreprises): **[to be added]**

**EU representative under Art. 27 GDPR:** Batnini Abdelkader, phone **+49 1577 7774764**,
email **batniniabdelkader@yahoo.com**. Address in an EU Member State:
**[to be added — Art. 27(3) GDPR requires an establishment in a Member State in which data subjects
are located]**. Written appointment under Art. 27(2) GDPR: **[to be added]**.

**Swiss representative under Art. 14 revFADP:** being set up; address to follow. **[Open item.]**

**Data Protection Officer (DPO):** not appointed. Short assessment (as of 26.10.2026): the core
activities are neither large-scale regular and systematic monitoring nor large-scale processing of
special categories (Art. 37(1)(b)/(c) GDPR); the threshold of **20 persons** constantly engaged in
automated processing (**§ 38(1) BDSG**) is currently not reached. The assessment is reviewed if the
scope or activities change (Art. 37(4) GDPR). **[To be confirmed by management.]**

## 2. Purposes and legal bases of processing

We process personal data of users (candidates, employers, admin) to handle the application
process between North Africa and Germany, France and Switzerland. Legal bases (Art. 6 GDPR):

| Processing | Purpose | Legal basis |
|---|---|---|
| Registration / account | Provision of the portal | Art. 6(1)(b) — pre-contractual |
| CV upload + extraction | Profile creation, matching | Art. 6(1)(b); for special categories Art. 9(2)(a) — consent |
| Matching / scoring (AI-assisted) | Assignment candidate ↔ job | Art. 6(1)(b) — see section 3 |
| Compliance check (DE/FR/CH) | Legal admissibility | Art. 6(1)(c) — legal obligation |
| Language test | Level classification | Art. 6(1)(a) — consent |
| Pre-screen / video meeting | Job interview | Art. 6(1)(b) |
| Recording of video interviews (optional) | only with separate consent | Art. 6(1)(a), § 26(2) BDSG |
| Onboarding | Support after hiring | Art. 6(1)(b) |
| Notifications / emails | Handling, information | Art. 6(1)(b), Art. 6(1)(f) — legitimate interest |
| Operation and security of the website | Delivery, abuse defence | Art. 6(1)(f) — legitimate interest |

## 3. AI-assisted matching and human decision

3.1 For matching and scoring we use an AI-assisted language model via the **NVIDIA API**. Input is
the material you submit (e.g. CV, references) and the information you provide; output is a score or
an assignment to jobs.

3.2 **No automated decision within the meaning of Art. 22 GDPR:** the score is a decision aid.
Decisions on invitation, rejection and hiring are taken exclusively by staff (human-in-the-loop).
Automatic sending of invitations or rejections is not intended.

3.3 Legal basis: Art. 6(1)(b) GDPR (application process); for special categories you submit
voluntarily, Art. 9(2)(a) GDPR.

3.4 Transparency: you may request an explanation of the logic involved (Art. 15(1)(h) GDPR).
Whether and how a review without AI support can be requested must be defined internally.
**[Process path: to be added.]**

3.5 The use is labelled as an AI system. Classification under the **EU AI Act** (Annex III no. 4 —
employment) is to be reviewed. **[To be reviewed; no classification is asserted.]**

## 4. Recipients

- **Employers** (only for the respective job): the display of names has been switched to pseudonyms
  (code mark `anzeige_name`); in individual views the real name may still be visible — this code gap
  is documented and will be closed. **Contact data and complete documents** are released **only
  after the invitation** (Art. 6(1)(b); data minimisation).
- **Authorities** (e.g. immigration authorities), where legally required.
- Data is **not** passed on for advertising purposes and **not** sold.

The following processors and services are used (Art. 28 GDPR):

| Service | Purpose | Location | DPA / transfer |
|---|---|---|---|
| Contabo | VPS hosting of the application | **[to be added]** | DPA to be confirmed |
| Cloudflare | CDN / reverse proxy | global (US parent) | DPA and transfer basis to be confirmed |
| NVIDIA | LLM API (extraction, matching, language test) | **USA** | DPA and transfer basis to be confirmed |
| VDO.Ninja | Video interview (WebRTC) | **[to be added]** | DPA and transfer basis to be confirmed |
| SMTP provider | Email delivery | **[to be added]** | DPA to be confirmed |

## 5. Transfers to third countries

The controller is established in **Tunisia (a third country outside the EU/EEA)**. Any transfer
of personal data to the EU or from the EU to Tunisia is made only on the basis of appropriate
safeguards under **Art. 44 ff. GDPR**. Whether an adequacy decision exists for Tunisia is to be
reviewed; until then, standard contractual clauses are used (implemented in Germany by the
StandVKlV). **[Specific safeguard: to be added.]**

Data is transferred to the **USA** via the NVIDIA API (text processing) and the Cloudflare proxy.
The basis is standard contractual clauses or certification under the EU-US Data Privacy Framework,
where the provider is certified. **[Status per provider: to be confirmed.]**

## 6. Storage period

- **Application data:** deleted **183 days after the process ends** (final status
  `rejected`/`hired`/`withdrawn`), automated GDPR cleanup (**Art. 17 GDPR**).
- **Active applications:** are not deleted.
- **Account data:** until the account is deleted (self-service, Art. 17).
- **Recordings of video interviews:** **6 months after the process ends** (design decision, see
  `knowledge/legal/recording-consent.md`).
- **Consent records:** **36 months** (project value, `knowledge/legal/gdpr-policy.md`).
- **Match/score data:** **12 months**, then anonymised (`knowledge/legal/gdpr-policy.md`).
- **Server/proxy logs:** period to be confirmed. **[To be added.]**

## 7. Cookies and local storage

Only **technically necessary** cookies/storage are used (session cookie for login, possibly local
storage of UI state). Non-essential, tracking, analytics or marketing cookies are **not** set.
Legal basis: **§ 25(2) TDDDG** ("strictly necessary"). If non-essential cookies are introduced in
future, consent under § 25(1) TDDDG must be obtained beforehand.

## 8. Hosting

The application runs on a virtual server (VPS) at **Contabo**. Server location and data processing
agreement are to be confirmed. **[To be added.]** **Cloudflare** is placed in front as CDN/reverse
proxy; DPA and third-country implications are to be confirmed. **[To be added.]**

## 9. Your rights

Under **Art. 15–22 GDPR** you have the right to:
- **access** (Art. 15), **rectification** (Art. 16), **erasure** (Art. 17),
  **restriction** (Art. 18), **data portability** (Art. 20),
- **object** to processing based on Art. 6(1)(f) (Art. 21),
- **withdraw** consent with effect for the future (Art. 7(3)),
- **not to be subject to a solely automated decision** (Art. 22) — currently not applicable because
  the final decision is made by a human (section 3).

## 10. Right to lodge a complaint

You have the right to lodge a complaint with a **data protection supervisory authority** (Art. 77
GDPR), in particular in the Member State of your residence, place of work or the seat of the EU
representative. The competent authority will be added once the EU seat is fixed.
**[To be added: supervisory authority.]**

## 11. Contact

For data protection questions: **batniniabdelkader@yahoo.com** · phone **+216 52 369 325**.
EU representative: **Batnini Abdelkader**, **+49 1577 7774764**, **batniniabdelkader@yahoo.com**.
