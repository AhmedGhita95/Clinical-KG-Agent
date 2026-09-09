# HORUS

## A. Purpose

HORUS is an ontology for representing information from clinical scenes.

It defines concepts and relations for describing:

- Who is present.
- What objects and places are present.
- What happens.
- How these elements relate.

The goal is to use this ontology to convert scene descriptions into consistent,
queryable knowledge graphs.

### A.1 Example

Scene description:

> During a patient transfer, a nurse pushes a seated patient in a wheelchair along a corridor.

Information to represent:

- People: a nurse and a patient.
- Objects: a wheelchair.
- Place: a corridor.
- Action: pushing.
- Procedure: patient transfer.
- State: the patient is seated.
- Relations: the nurse performs the pushing action on the wheelchair; the action
  occurs in the corridor and is a step of the patient transfer; the seated state
  holds for the patient.

## B. Structure

```text
Entity                          Who or what is present
    Agent                       People involved
    Object                      Physical items
    Place                       Locations

Occurrent                       What happens
    Action                      An individual action
    Procedure                   An activity comprising related actions

State                           How an entity is at a given time

Assertion                       Links represented information
                                to its source description
```

## C. Relations

| Relation | Connects | Meaning |
|---|---|---|
| performedBy | Action → Agent | Who performs the action |
| actsOn | Action → Entity | What the action affects |
| occursIn | Occurrent → Place | Where it happens |
| hasStep | Procedure → Action | Which actions belong to a procedure |
| holdsFor | State → Entity | Who or what has the state |
| about | Assertion → Entity, Occurrent, or State | What the assertion describes |

## D. Knowledge representation

Information from a description is represented as instances of the HORUS classes,
connected through its relations.

For the example in A.1:

| Instance | Class | Label |
|---|---|---|
| nurse_1 | Agent | nurse |
| patient_1 | Agent | patient |
| wheelchair_1 | Object | wheelchair |
| corridor_1 | Place | corridor |
| pushing_1 | Action | pushing |
| transfer_1 | Procedure | patient transfer |
| seated_1 | State | seated |

```text
pushing_1  → performedBy → nurse_1
pushing_1  → actsOn      → wheelchair_1
pushing_1  → occursIn    → corridor_1
transfer_1 → hasStep     → pushing_1
seated_1   → holdsFor    → patient_1
```

Labels such as "nurse" and "wheelchair" do not require additional classes.
The patient is represented, but its connection to the wheelchair is not expressed
by the current relations.

## E. Query

The graph should answer these questions for the example in A.1:

| Question | Example answer |
|---|---|
| Who is present? | A nurse and a patient. |
| What action happens, and who performs it? | Pushing, performed by the nurse. |
| Where does it happen? | The corridor. |
| What procedures are described, and which actions belong to each? | Patient transfer: pushing. |
| What states are described, and who or what do they apply to? | Seated: the patient. |

## F. Pipeline

```text
Scene description + HORUS vocabulary
                |
                v
            Extraction
                |
                v
            Validation
                |
                v
          Knowledge graph
                |
                v
              Query
```

1. **Extraction:** An LLM maps information from the description to instances and
   relations using the classes in B and relations in C. The structured output is
   converted into an RDF graph.
2. **Validation:** Check that classes and relations are defined in HORUS,
   referenced instances exist, and relation endpoints have compatible types.
   Report errors for correction before using the graph for queries.
3. **Query:** Run queries over the validated graph to answer the questions in E.

Reasoning is limited to class inheritance: an Agent is also an Entity, and an
Action or Procedure is also an Occurrent. Validation and queries take this
hierarchy into account.

Broader reasoning will be introduced later to derive additional facts from
explicitly defined ontology axioms.
