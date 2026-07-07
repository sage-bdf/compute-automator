# compute-automator

Centralized reference repository for the **BDF Compute Automator**. It houses, in one place, the artifacts needed to run each supported data modality end-to-end through a Nextflow pipeline orchestrated by [ORCA](https://github.com/Sage-Bionetworks-Workflows/orca-recipes) with results returned to Synapse.

Tracking issue: [BDFLINC-224](https://sagebionetworks.jira.com/browse/BDFLINC-224) · Initiative: [BDFLINC-25 — BDF Compute Automator](https://sagebionetworks.jira.com/browse/BDFLINC-25)

## What's here

Each modality directory holds the three artifacts that drive an automated run:

1. **Input sample sheet** — nf-core / spatialvi format (`samplesheet.csv`)
2. **ORCA recipe incl. config** — pointer to the orca-recipe + the workflow `nextflow.config`
3. **Output dataset** — pointer to the processed results in Synapse

Each modality is backed by a Synapse project with a designated **input folder** and **output folder**. Where data has already been processed, reuse the processed files — avoid reprocessing.

## Supported modalities

| # | Modality | Underlying pipeline | Directory |
|---|----------|--------------------|-----------|
| 1 | Bulk RNA-seq (PDX; BBSplit mouse/human) | [nf-core/rnaseq](https://github.com/nf-core/rnaseq) | [`bulk-rnaseq/`](bulk-rnaseq/) |
| 2 | scRNA-seq | [nf-core/scrnaseq](https://github.com/nf-core/scrnaseq) | [`scrnaseq/`](scrnaseq/) |
| 3 | Bulk WGS | [nf-core/sarek](https://github.com/nf-core/sarek) | [`bulk-wgs/`](bulk-wgs/) |
| 4 | Bulk WES (germline first) | [nf-core/sarek](https://github.com/nf-core/sarek) | [`bulk-wes/`](bulk-wes/) |
| 5 | Spatial transcriptomics (10x Visium) | [sage-bdf/synapse_spatialvi_nf_pipeline](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline) *(Sage original)* | [`spatial-trxn/`](spatial-trxn/) |

Modalities 1–4 run off community nf-core pipelines; spatial transcriptomics is Sage's original contribution.

## Layout

```
compute-automator/
├── bulk-rnaseq/    samplesheet.csv, nextflow.config, README (orca-recipe + output synID)
├── scrnaseq/       …
├── bulk-wgs/       …
├── bulk-wes/       …
└── spatial-trxn/   … (references sage-bdf/synapse_spatialvi_nf_pipeline)
```

## Status

Scaffold with per-modality templates. Sample sheets, configs, and Synapse project IDs are being filled in — see each directory's README for the current state and open TODOs.
