# Compute Automator

Centralized reference repository for the **Biomedical Data Fabric (BDF) Compute Automator**, the standardized way BDF processes raw sequencing data into analysis-ready results.

Each supported data modality is defined here as a self-contained, reproducible unit: a sample sheet describing the inputs, a pipeline configuration, an [ORCA](https://github.com/Sage-Bionetworks-Workflows/orca-recipes) recipe that runs the workflow, and a pointer to where the processed outputs live in Synapse. The goal is that any team member can look up a modality, understand exactly how it runs, and reproduce or extend it without tribal knowledge.

## How it works

```
Synapse input folder  ──▶  ORCA recipe  ──▶  Nextflow pipeline  ──▶  Synapse output dataset
   (raw data)               (orchestration)     (nf-core / Sage)         (analysis-ready)
```

ORCA reads inputs staged in a modality's Synapse **input folder**, runs the corresponding Nextflow pipeline with the pinned `nextflow.config`, and returns results to the modality's Synapse **output folder** as a versioned dataset. Where data has already been processed, reuse the published outputs rather than reprocessing.

## Supported modalities

| # | Modality | Underlying pipeline | Directory |
|---|----------|---------------------|-----------|
| 1 | Bulk RNA-seq (PDX; BBSplit mouse/human) | [nf-core/rnaseq](https://github.com/nf-core/rnaseq) | [`bulk-rnaseq/`](bulk-rnaseq/) |
| 2 | scRNA-seq | [nf-core/scrnaseq](https://github.com/nf-core/scrnaseq) | [`scrnaseq/`](scrnaseq/) |
| 3 | Bulk WGS | [nf-core/sarek](https://github.com/nf-core/sarek) | [`bulk-wgs/`](bulk-wgs/) |
| 4 | Bulk WES (germline first) | [nf-core/sarek](https://github.com/nf-core/sarek) | [`bulk-wes/`](bulk-wes/) |
| 5 | Spatial transcriptomics (10x Visium) | [sage-bdf/synapse_spatialvi_nf_pipeline](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline) | [`spatial-trxn/`](spatial-trxn/) |

Modalities 1 through 4 build on community [nf-core](https://nf-co.re/) pipelines; spatial transcriptomics runs on a Sage-authored pipeline.

## Repository layout

Every modality directory follows the same contract:

```
<modality>/
├── samplesheet.csv     # inputs, in the pipeline's expected sample-sheet format
├── nextflow.config     # pinned pipeline configuration for this modality
└── README.md           # ORCA recipe link, Synapse input/output pointers, run notes
```

## Per-modality artifacts

Each directory's `README.md` is the source of truth for that modality and records:

- **Input sample sheet**: `samplesheet.csv`, in the format the pipeline expects (columns documented in the modality README).
- **Processing recipe**: a link to the [ORCA recipe](https://github.com/Sage-Bionetworks-Workflows/orca-recipes) plus the pinned `nextflow.config` used for the run.
- **Output dataset**: the Synapse dataset holding analysis-ready results.
- **Synapse project**: the input and output folder locations backing the modality.
