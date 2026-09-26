# WO-02 measured results

| Stage | n | Recall@10 | MRR | nDCG@10 |
|---|---:|---:|---:|---:|
| bm25 | 300 | 0.7575 | 0.5942 | 0.6261 |
| dense_hnsw | 300 | 0.8015 | 0.6417 | 0.6728 |
| hybrid_rrf | 300 | 0.8244 | 0.6597 | 0.6905 |
| hybrid_rerank | 300 | 0.8096 | 0.6605 | 0.6843 |

## Generation metrics (reported separately)

| Metric | Value |
|---|---:|
| Citation coverage | 1.0000 |
| Citation correctness | 0.8333 |
| Extractive grounding | 1.0000 |
| Faithfulness | 0.5667 |
| Answer relevance cosine | 0.6261 |
| Verdict accuracy | 0.6333 |

## Cited answer examples

### calculation

- Claim: A total of 1,000 people in the UK are asymptomatic carriers of vCJD infection.
- Answer: CONTRADICT. conclusions this study corroborates previous studies and suggests a high prevalence of infection with abnormal prp, indicating vcjd carrier status in the population compared with the 177 vcjd cases to date. [13734012#c3]
- Gold / predicted: CONTRADICT / CONTRADICT

### comparison

- Claim: ALDH1 expression is associated with poorer prognosis in breast cancer.
- Answer: SUPPORT. in a series of 577 breast carcinomas, expression of aldh1 detected by immunostaining correlated with poor prognosis. [45638119#c1]
- Gold / predicted: SUPPORT / SUPPORT

### lookup

- Claim: ADAR1 binds to Dicer to cleave pre-miRNA.
- Answer: SUPPORT. ##r1 increases the maximum rate ( vmax ) of pre - microrna ( mirna ) cleavage by dicer and facilitates loading of mirna onto rna - induced silencing complexes, identifying a new role of adar1 in mirna processing and rnai mechanisms. [5953485#c1]
- Gold / predicted: SUPPORT / SUPPORT

