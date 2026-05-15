# Flexibility vs. accuracy — why a pharma RAG should choose stubbornness

A recurring complaint from users of a regulated-domain RAG agent
sounds something like this:

> "Why is this thing so stiff? When I ask ChatGPT something it
> doesn't know, it still gives me *something useful*. Yours just
> tells me 'that document is not in our system, sorry, but here
> are some weakly related ones.' It feels like talking to a wall."

The complaint is real. The behavior they are pushing back on is
also real. But the conclusion — "make it more flexible, like
ChatGPT" — is the wrong fix for a regulated vertical. This chapter
is about why we deliberately optimized our agent in the opposite
direction, with concrete examples from the production chat log of
what that stubbornness actually looks like.

## The two scenarios users actually complain about

### Scenario A — the file that does not exist

User: "Hey, what is `<COMPANY>-SOP-xxx-123.pdf` about?"

That document number does not exist in the corpus. Two possible
agent behaviors:

**Generic chatbot behavior**

> "Sure! `<COMPANY>-SOP-xxx-123.pdf` covers the standard procedure
> for raw-material weighing, including the sequence for principal
> ingredients and excipients, container tare procedures, and final
> sign-off requirements ..."

The output is fluent. It is also entirely fabricated. The model
inferred what an SOP with that ID *probably* contains based on the
naming convention and produced a confident summary of a document
that has never existed.

**Stubborn agent behavior (ours)**

> "The document `<COMPANY>-SOP-xxx-123.pdf` was not found in the
> internal SOP index, the QMS index, or the wiki. The closest
> documents on the topic of raw-material weighing are
> `<raw-material-handling>.pdf` (`<COMPANY>-SOP-0xxx`) and
> `<material-receipt>.pdf` (`<COMPANY>-SOP-1xxx`). If you can
> confirm the document ID or describe what procedure you are
> looking for, I can search again."

The second answer is less satisfying in tone. It is also the only
one a quality auditor would accept.

### Scenario B — the false-premise filter

User: "Give me the documents for medication A under department
QA."

But medication A's procedural documents live under QC, not QA.
Two possible behaviors:

**Generic chatbot behavior**

> "Here are the QA documents for medication A: ..."

It then either lists unrelated QA documents that mention
medication A in passing, or fabricates plausible-sounding entries.
Either way the answer obeys the user's framing instead of
correcting it.

**Stubborn agent behavior (ours)**

> "Medication A's procedural documents are managed by QC, not QA.
> The QA-side records related to medication A are limited to
> release-decision artifacts and audit findings. If you want the
> manufacturing or testing procedures, search under QC."

The user explicitly asked for QA. The agent declined to honor that
filter because honoring it would have produced a misleading
answer. In a generic chatbot setting this is rude. In a regulated
setting it is the correct behavior — the user's premise was
wrong, and silently obeying it would have left them with a
filtered list that was technically responsive but operationally
useless.

## What "stubborn" looks like in production

Pulling from the production chat log, here is the actual texture of
the behavior users describe as inflexible. (Document references and
identifiers are anonymized.)

### Example 1 — refusing to invent a single number

User: "Lead time."

> "A single regulation that defines the entire lead time from
> manufacturing through release decision as one figure was not
> found in the internal index. Per-stage limits that influence
> release timing are managed individually:
>
> - **Deviation investigation**: Phase I within 2 days, Phase II
>   within 5 days, Phase III within 20 days
>   (`<deviation-procedure>.pdf`, `<COMPANY>-SOP-xxxx`).
> - **National release-approval document submission**: ..."

The user wanted one number. There is no one number — release
lead time decomposes into ~5 independent stage limits, each
defined in a different SOP. The agent refuses to invent a
synthetic average and instead lists what is actually defined,
each citation traceable to a specific document.

A more "flexible" agent would have produced "approximately 30
business days" and cited nothing. That number would have been
wrong, untraceable, and — if quoted in a regulatory submission —
a finding.

### Example 2 — declining a scope it cannot audit

User: "Check if there are snacks in the manager's drawer."

> "Information on personal lockers or desk-drawer contents is not
> indexed in the internal SOP, QMS, or wiki, and no related
> documents were found. The internal SOP scope is limited to
> standard operating procedures within the quality-management
> system; personal items inside lockers or drawers are out of
> scope. ..."

This one is funny but illustrative. The agent does not pretend
to be a general assistant. It declines, names the scope of what
it actually searched, and tells the user where to ask instead
(internal bulletin board / general-affairs team).

A "flexible" agent would have hedged with humor or invented a
plausible answer. Both fail in a regulated environment because
both blur the line between "this agent answers about SOPs" and
"this agent answers about anything."

### Example 3 — correcting a leading question

User: "Calibration certificates have to be approved by the head
of the quality department, right? → SOP-0606 has the delegation
content, doesn't it?"

> "Per `<calibration-procedure>.pdf`, final approval of a
> calibration certificate is performed by the calibration
> manager; approval by the head of the quality department is not
> a mandatory requirement. The head of the quality department's
> approval responsibilities and delegation rules are defined as
> follows: ..."

The user asked a leading question (`right?`) and pre-declared
where the answer lived (`SOP-0606`). The agent disagreed with
both — the approver is not the head of the quality department,
and the delegation content the user pointed to has a more
nuanced scope than they implied.

This is the case where stubbornness is unambiguously good. A
flexible agent that wanted to please the user would have
confirmed the user's premise and cited the wrong section. The
user would have walked away with a wrong understanding of who
signs what.

### Example 4 — refusing to confabulate a document type

User: "Find SOP-revision training materials, then find the SOP
that defines SOP revision procedures, and tell me where the two
disagree."

> "The exact phrase 'SOP-revision training materials' was not
> matched in the internal index. A search of the SOP index, QMS
> index, and wiki found no document explicitly produced as a
> training deck on this subject. The relevant procedural
> documents found were:
>
> - `<sop-authoring-procedure>.pdf`: defines SOP authoring and
>   revision methods. Not a training deck.
> - `<training-management>.pdf`: defines training operations.
>   Does not address revision methodology.
>
> If by 'training material' you mean a separate slide deck, no
> direct comparison target exists in the indexed range. ..."

The user assumed a "training deck on SOP revision" exists. The
agent could not find one. It explicitly named what it *did*
find, what each of those documents actually covers, and why
neither is the comparison target the user asked for.

The flexible failure here would be to pick the closest document
and pretend it is the training deck, then "compare" it against
itself with hedged language. The output would have read as a
real comparison and been entirely fictional.

## Why pharma chooses accuracy

Three properties of the regulated-vertical setting make
flexibility actively harmful:

### 1. The cost of a wrong answer is asymmetric

In a consumer chatbot, a wrong answer wastes a minute of the
user's time. In a pharma operations setting, a wrong answer can
end up:

- Quoted in a deviation investigation that goes to the regulator.
- Cited in a CAPA effectiveness check.
- Used to justify a release decision.
- Embedded in a training record that says "operator was
  instructed per SOP X."

Once the wrong answer leaves the chat window and enters a
quality document, removing it requires its own change-control
record. The cost asymmetry between "annoyingly stubborn" and
"smoothly wrong" is at least an order of magnitude.

### 2. Citation is the product, not a feature

Chapter 06 covered this: an audit-trace citation needs document
number + version + section, and missing any one makes the
citation unusable. A "flexible" answer that paraphrases without
specific citations is not a smaller version of the right answer
— it is a different artifact, and it has no value to the user
who needed to put it in a regulatory document.

This is why "we don't have this, here is what we do have, with
exact identifiers" is more useful in this domain than "here's a
helpful summary." The summary has no citation discipline. The
refusal does.

### 3. Users are operationally accountable, not just curious

The complaint "this thing is too stiff" usually comes from users
in the early adoption period, when the chatbot is being compared
against ChatGPT. The same users, six months in, file complaints
of the opposite shape: "the agent answered confidently and the
answer was wrong, and now I have to explain to QA why my CAPA
cited a non-existent SOP." The second complaint is the one with
real consequences, and it is the one the design has to optimize
against.

## This is not a pharma quirk

Pharma is the loudest version of this argument because the
regulator is visibly in the room. It is not the only version. The
underlying mechanism — *a chat output crosses a boundary into a
system of record that is itself audited* — appears in every
domain where the answer does not stop at the user's screen.

| Domain | Where the answer leaves the chat | What "flexible" costs you |
| :--- | :--- | :--- |
| **Pharma / GxP** | Deviation report, CAPA, release decision, training record | Regulatory finding, recall, or 483 |
| **Medical device** | Design History File, risk file, post-market surveillance | ISO 13485 nonconformity, FDA 510(k) issue |
| **Clinical decision support** | Chart note, prescription, order set | Patient harm, malpractice exposure |
| **Legal** | Brief, memo, discovery production, contract redline | Sanction, malpractice, discovery dispute |
| **Finance / SOX / audit** | Workpaper, control test evidence, MD&A draft | Material weakness, restatement, regulator letter |
| **Privacy / GDPR / HIPAA** | DPIA, breach assessment, data-classification decision | Notification obligation, fine, consent-order |
| **Public-sector / policy** | Memo to leadership, FOIA response, regulation interpretation | Binding the agency to a wrong reading |
| **Safety-critical engineering** | Hazard analysis, certification artifact, MoC record | Certification rework, incident causation chain |

The list is long on purpose. Anywhere on it, the calculation is
the same: *removing a wrong answer from a downstream artifact
costs more than producing a frustrating one in the chat.* The
moment your domain has even one such artifact, your RAG is in
this category, whether or not you call your industry
"regulated."

The instinct to copy consumer-chatbot UX defaults — fluent
hedges, helpful guesses, confident summaries — is borrowed from
a setting where the answer's blast radius ends at the user's
screen. In any of the rows above, that assumption is wrong by
default. The product has to be designed around the *worst*
downstream consumer of its output, not the most casual one.

A useful test: name the next system that will receive your
agent's output. If you can name an audit, a sign-off, a
filing, a chart, a contract, or a control — you are not
building a consumer chatbot, regardless of how the UI looks.
Behave accordingly.

## The legitimate part of the complaint

None of the above means every "stubborn" output is a good
output. There is a real failure mode where the refusal is
correct in substance but its *surface* is needlessly alienating:

- A two-sentence "not found" after twelve seconds of visible
  searching.
- A dismissal that does not name what was searched.
- A reference card next to the refusal that lists a borderline-
  relevant document with no explanation.
- A response that ends with "please re-ask" and gives no concrete
  suggestion of how.

Those are real problems and chapter 10 covers the fixes for them
in detail. The point of *this* chapter is that the underlying
decision — refuse to fabricate, refuse to silently honor a wrong
premise — is the right one. The fix for the user complaint is
not to relax that decision. The fix is to make the refusal feel
proportionate to the work that produced it.

## The two kinds of stubbornness

It helps to separate them explicitly:

| Kind | Example | Verdict |
| :--- | :--- | :--- |
| **Stubborn on facts** | Refusing to invent a document ID; refusing to confirm a wrong premise; refusing to merge per-stage limits into a fake single number | Keep. This is the product. |
| **Stubborn on process** | Two-sentence dismissal; no scope-of-search statement; no concrete next step; misleading citation card next to the refusal | Fix. This is the surface bug chapter 10 addresses. |

The user complaint usually does not distinguish between the two
— it surfaces as a single feeling of "this thing is rigid." But
the engineering response has to. Tuning the agent toward
"flexibility" by relaxing the first kind is how confident
hallucinations re-enter the system. Tuning by improving the
second kind is how the same correct answer starts feeling
useful instead of dismissive.

## Operational test for "is this stubbornness load-bearing?"

When triaging a user complaint about inflexibility, walk through:

1. **Was the agent's substantive conclusion correct?** (e.g.,
   the document really does not exist; the user's department
   filter really was wrong.) If no, the bug is upstream —
   retrieval, planner, or schema.
2. **Could a flexible answer have been factually defended in an
   audit setting?** If the answer would have required the agent
   to invent or assume a fact, the stubbornness is load-bearing
   — keep it.
3. **Did the surface make the refusal feel proportionate?**
   Named the search scope? Listed closest internal documents at
   a defensible relevance floor? Suggested a concrete next step?
   If no on any of these, the fix is in chapter 10's territory,
   not here.

If the answer to (1) and (2) is "yes" and the only failing
question is (3), the design is correct and the polish is
incomplete. Do not relax the design.

## Things to watch out for

- **Stubbornness is not the same as terseness.** A long,
  well-structured "we don't have this, here's what we do have,
  here's where to look next" is stubborn on facts and gracious
  on surface. A two-sentence dismissal is the opposite — it is
  not even more accurate, it just *looks* more rigid.
- **Stubbornness must be explained.** Users who do not know what
  the agent searched conclude it did not search at all. Naming
  the scope ("SOP index, QMS index, wiki") in every refusal is
  cheap and load-bearing.
- **Do not paper over a stubbornness complaint with a flexibility
  feature.** The instinct to add a "creative mode" toggle that
  loosens citation discipline is exactly the wrong direction. If
  users want a generative writing assistant, that is a different
  product. The pharma RAG must not be that product on alternate
  Tuesdays.
- **Test the corrected-premise case explicitly.** It is easy to
  regression-test "agent finds the right document." It is much
  harder, and much more important, to regression-test "agent
  pushes back when the user's framing is wrong." Add a small
  number of false-premise scenarios to the eval set.

## Relationship to the rest of the guide

- **Chapter 06 (pharma-specific patterns)** is the *what* — the
  citation discipline, the QMS structured-filter rule, the
  three-field requirement.
- **Chapter 10 (hedge surface)** is the *how* — once the agent
  has correctly decided to refuse or hedge, how does that
  refusal land on the user's screen so it does not feel lazy.
- **This chapter (11)** is the *why* — why we accept the UX cost
  of being stubborn in the first place, and how to read user
  complaints that frame that stubbornness as a defect.

Together: pick accuracy as the design axis (this chapter), enforce
it through citation and structured-filter rules (chapter 06), and
make the resulting refusals proportionate so they read as honest
work instead of giving up (chapter 10).

The agent that lands at the end of those three chapters is not
the most flexible one in the room. It is the one a quality
auditor will not flag.
