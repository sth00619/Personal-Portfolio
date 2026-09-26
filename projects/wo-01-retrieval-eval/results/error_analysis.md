# Hybrid-128 error analysis

The chosen `hybrid_128` run has 58 queries with incomplete Recall@10. The five cases below cover distinct failure modes; ranks are document ranks among the top 50 retained candidates.

| Query ID | Query (abridged) | Relevant rank | Failure mode |
|---|---|---:|---|
| 1 | 0-dimensional biomaterials show inductive properties. | 12 | RRF displacement |
| 1049 | Ribosomopathies have a low degree of cell and tissue specific pathology. | 44 | lexical decoy and polarity |
| 1110 | Suboptimal nutrition is not predictive of chronic disease. | >50 | broad evidence and negation |
| 1175 | The PPR MDA5 has two N-terminal CARD domains. | >50 | acronym typo and vocabulary mismatch |
| 1191 | Publicly available DNA data doubles every 10 years. | 24 | numeric claim and historical wording |

## QID 1 — fusion displaced a useful dense hit

- Relevant document: `31715818`, *New opportunities: the use of nanotechnologies to manipulate and track stem cells.*
- BM25 rank: >50; dense rank: 5; hybrid rank: 12; reranked rank: 19.
- Diagnosis: the evidence describes nanoscale materials without the literal phrase “0-dimensional.” BM25 strongly favors documents containing “three-dimensional,” and equal-weight RRF pushes the good dense hit below the cutoff.
- Candidate improvement: tune fusion weights on a held-out split or fall back to dense ranking when BM25 has weak exact-term coverage.

## QID 1049 — topical matches missed the evidential polarity

- Relevant document: `12486491`, *Ribosome-Mediated Specificity in Hox mRNA Translation and Vertebrate Tissue Patterning.*
- BM25 rank: >50; dense rank: 24; hybrid rank: 44.
- Diagnosis: the claim uses “ribosomopathies,” while the evidence discusses a ribosomal-protein mutation and tissue-specific defects. Highly lexical review articles about ribosomopathies dominate, and the retriever does not understand that “low specificity” is contradicted by tissue-specific pathology.
- Candidate improvement: use a biomedical embedding model and train a second-stage relevance model on scientific claim/evidence pairs.

## QID 1110 — a broad review is hard to retrieve from a short negated claim

- Relevant document: `13770184`, *Global, regional, and national comparative risk assessment ... Global Burden of Disease Study 2015.*
- BM25, dense, hybrid, and reranked ranks: >50.
- Diagnosis: the evidence is a broad population-risk review whose title and opening abstract do not closely restate “suboptimal nutrition.” Negation also makes nearby topical nutrition and chronic-disease papers appear semantically plausible.
- Candidate improvement: index sentence-level passages and add claim decomposition before retrieval.

## QID 1175 — a typo removes the strongest entity cue

- Relevant document: `31272411`, *Immune signaling by RIG-I-like receptors.*
- BM25, dense, hybrid, and reranked ranks: >50.
- Diagnosis: the query says “PPR MDA5,” while the domain term is “PRR.” The relevant review uses the family name “RIG-I-like receptors,” so both lexical and general-domain dense retrieval lose the connection.
- Candidate improvement: add acronym normalization and typo-aware query expansion (`PPR` → `PRR`, `MDA5` → `RIG-I-like receptor`).

## QID 1191 — exact numbers encourage unrelated matches

- Relevant document: `30655442`, *The EMBL nucleotide sequence database.*
- BM25 rank: >50; dense rank: 11; hybrid rank: 24; reranked rank: 24.
- Diagnosis: the historical database paper describes growth in wording that differs from the claim. BM25 overweights “DNA,” “data,” and “10 years,” while equal-weight fusion moves the semantically useful dense result below rank 10.
- Candidate improvement: normalize numeric expressions and use an adaptive fusion weight for claims dominated by quantities.

These are retrieval failures only. The experiment does not run a generator, so none of the misses are attributed to answer generation or faithfulness.
