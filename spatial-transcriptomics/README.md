# Spatial transcriptomics (10x Visium)

Spatial transcriptomics processing. This modality uses **Sage's own pipeline** (original contribution), not an nf-core pipeline.

| Artifact | Value |
|----------|-------|
| Pipeline | [sage-bdf/synapse_spatialvi_nf_pipeline](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline) |
| Sample sheet | [`samplesheet.csv`](samplesheet.csv) — `sample,fastq_1,fastq_2,fastq_3,fastq_4,image,slide,area` ([synstage format](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline#input-samplesheet-for-synstage)) |
| Config | [`nextflow.config`](nextflow.config) (from [synapse_spatialvi_nf_pipeline](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline/blob/main/nextflow.config)) |
| ORCA chain | synstage → make tarball → spatialvi → synindex |
| Synapse input folder | TODO — synID |
| Synapse output dataset | existing spatialvi example (TODO — synID) |

## TODO
- [ ] Fill sample sheet from the existing spatialvi example
- [ ] Link ORCA recipe/chain and Synapse input/output folders
