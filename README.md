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
| 2 | scRNA-seq | [nf-core/scrnaseq](https://github.com/nf-core/scrnaseq) | [`sc-rnaseq/`](sc-rnaseq/) |
| 3 | Bulk WGS | [nf-core/sarek](https://github.com/nf-core/sarek) | [`bulk-wgs/`](bulk-wgs/) |
| 4 | Bulk WES (germline + somatic) | [nf-core/sarek](https://github.com/nf-core/sarek) | [`bulk-wes/`](bulk-wes/) |
| 5 | Spatial transcriptomics (10x Visium) | [sage-bdf/synapse_spatialvi_nf_pipeline](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline) | [`spatial-transcriptomics/`](spatial-transcriptomics/) |

Modalities 1 through 4 build on community [nf-core](https://nf-co.re/) pipelines; spatial transcriptomics runs on a Sage-authored pipeline.

## Repository layout

Every modality directory follows the same contract:

```
<modality>/
├── samplesheet.csv     # inputs, in the pipeline's expected sample-sheet format
├── nextflow.config     # pinned pipeline configuration for this modality
└── *_workflow.py       # ORCA recipe(s) that launch the pipeline on Nextflow Tower
```

This README is the single source of truth for per-modality details (below).

## Modality details

### 1. Bulk RNA-seq (PDX)
- Pipeline: [nf-core/rnaseq](https://github.com/nf-core/rnaseq). Includes a **BBSplit** step to separate mouse from human reads before quantification.
- Sample sheet columns: `sample,fastq_1,fastq_2,strandedness,seq_platform`
- Open: link ORCA recipe; confirm BBSplit reference/params; fill Synapse input/output folders.

### 2. scRNA-seq
- Pipeline: [nf-core/scrnaseq](https://github.com/nf-core/scrnaseq).
- Sample sheet columns: `sample,fastq_1,fastq_2,expected_cells`
- Open: link ORCA recipe; decide nf-core direct vs. Synapse staging step; fill Synapse folders.

### 3. Bulk WGS
- Pipeline: [nf-core/sarek](https://github.com/nf-core/sarek).
- Sample sheet columns: `patient,sample,lane,fastq_1,fastq_2`
- Candidate dataset: CCKP open-access [syn18425401](https://cancercomplexity.synapse.org/Explore/Datasets/DetailsPage?datasetId=syn18425401).
- Open: select final dataset; link ORCA recipe; fill Synapse folders.

### 4. Bulk WES (germline + somatic)
- Pipeline: [nf-core/sarek](https://github.com/nf-core/sarek). Sarek has no `--somatic` flag: the mode is set by the sample sheet (a tumor `status=1` and matched normal `status=0` under one `patient` triggers tumor-vs-normal) and the chosen caller.
- Sample sheet columns: `patient,sample,fastq_1,fastq_2,lane,status`
- Recipes: [`sarek_germline_workflow.py`](bulk-wes/sarek_germline_workflow.py) (also in [orca-recipes PR#1](https://github.com/sagebio-ada/orca-recipes/pull/1)) and [`sarek_somatic_workflow.py`](bulk-wes/sarek_somatic_workflow.py).
- Somatic reproduces the [JHU NF1 Biobank release-2](https://github.com/nf-osi/biobank-release-2) run scoped to JH_batch1: sarek v3.1.2, GATK.GRCh38, WES + Agilent V6 intervals, callers `strelka,mutect2,vep`. Input sample sheet [syn52236715](https://www.synapse.org/Synapse:syn52236715).
- Open: fill the JH_batch1 output folder synID (input is wired in).

### 5. Spatial transcriptomics (10x Visium)
- Pipeline: [sage-bdf/synapse_spatialvi_nf_pipeline](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline) (Sage-authored).
- Sample sheet columns: `sample,fastq_1,fastq_2,fastq_3,fastq_4,image,slide,area` ([synstage format](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline#input-samplesheet-for-synstage)).
- ORCA chain: synstage, make tarball, spatialvi, synindex.
- Open: fill sample sheet from the existing spatialvi example; link ORCA recipe/chain; fill Synapse folders.
