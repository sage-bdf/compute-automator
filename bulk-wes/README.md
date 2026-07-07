# Bulk WES

Whole-exome sequencing processing via Sarek. **Starting with germline**; somatic (tumor-only, tumor + paired normal) to follow.

| Artifact | Value |
|----------|-------|
| Pipeline | [nf-core/sarek](https://github.com/nf-core/sarek) |
| Sample sheet | [`samplesheet.csv`](samplesheet.csv) — `patient,sample,lane,fastq_1,fastq_2` |
| Config | [`nextflow.config`](nextflow.config) (from [nf-core/sarek](https://github.com/nf-core/sarek/blob/3.2.3/nextflow.config)) |
| ORCA recipe | germline recipe in [orca-recipes PR#1](https://github.com/sagebio-ada/orca-recipes/pull/1) (waiting to merge) |
| Candidate dataset | WES cancer dataset — [syn75817905](https://www.synapse.org/Synapse:syn75817905) (NF + cancer) |
| Synapse input folder | TODO — synID |
| Synapse output dataset | TODO — synID |

## TODO
- [ ] Merge/reference germline ORCA recipe ([PR#1](https://github.com/sagebio-ada/orca-recipes/pull/1))
- [ ] Fill sample sheet from syn75817905
- [ ] Plan somatic variant (tumor-only, tumor + paired normal) as a follow-up
