# BDF ORCA Recipes

Nextflow Tower orchestration scripts for Biomedical Data Fabric data processing pipelines.

## Overview

Each recipe runs a standardized four-step workflow:
1. **fetch_samplesheet** — pull the samplesheet from Synapse to S3
2. **synstage** — download input FASTQ files from Synapse to S3
3. **pipeline** — run the per-modalities analysis
4. **synindex** — upload results back to Synapse

## Quick Start

### Prerequisites

```bash
pip install py-orca
```

AWS profile `tower` configured, and Synapse auth token set as a Tower workspace secret.

### Environment Setup

Export Tower credentials before running any recipe:

```bash
export TOWER_ACCESS_TOKEN="<your-token>"
export TOWER_WORKSPACE="sage-bionetworks/ntap-add5-project"
export TOWER_API_ENDPOINT="https://tower.sagebionetworks.org/api"
```

## Recipes

### sarek_somatic_workflow.py — WES Variant Calling
Whole Exome Sequencing somatic variant calling (tumor vs. matched normal).

- **Pipeline**: nf-core/sarek v3.1.2
- **Genome**: GATK.GRCh38
- **Variant callers**: Strelka2, Mutect2, VEP
- **Based on**: JHU NF1 Biobank release-2
- **Requirement**: Paired tumor/normal samples (tumor status=1, normal status=0, same patient ID)
- **Note**: Standalone (does not use base_rna.py)

```bash
python sarek_somatic_workflow.py [step ...] [--run-number N]
```

### rnaseq_workflow.py — Bulk RNA-seq

Bulk RNA-seq alignment and quantification.

- **Pipeline**: nf-core/rnaseq v3.11.2
- **Aligner**: STAR with Salmon quantification
- **Genome**: GRCh38
- **Based on**: NF-OSI Nextflow Data Processing standard
- **Uses**: base_rna.py (shared module)

```bash
python rnaseq_workflow.py [step ...] [--run-number N]
```

### scrnaseq_workflow.py — Single-Cell RNA-seq (TBD)

Single-cell RNA-seq processing. Uses base_rna.py (shared module).

```bash
python scrnaseq_workflow.py [step ...] [--run-number N]
```

**Note**: Configuration pending test data validation.

## base_rna.py — Shared Module

Common orchestration module for RNA modalities (rnaseq, scrnaseq).

Core functions:
- `get_tower_ops()` — Tower client with URL double-slash fix
- `Dataset` — samplesheet/output configuration
- `fetch_samplesheet()` — download from Synapse to S3
- `prepare_synstage_info()` — stage FASTQ files to S3
- `prepare_synindex_info()` — upload results to Synapse
- `load_params_from_json()` — load pipeline params, filter internal notes
- `run_workflows()` — orchestrate four steps with success checks
- `main()` — command-line entry point

## Configuration

### File Structure

```
recipes/
  base_rna.py              # Shared module
  sarek_somatic_workflow.py
  rnaseq_workflow.py
  scrnaseq_workflow.py

config/
  rnaseq.params.json       # nf-core/rnaseq parameters
  scrnaseq.params.json     # nf-core/scrnaseq parameters
```

### Customization

Each recipe defines:
- **generate_datasets()** — list of datasets (Synapse IDs, S3 paths, run numbers)
- **prepare_[pipeline]_launch_info()** — pipeline-specific params and versions
- **[modality].params.json** — science parameters (aligner, genome, etc.)

Modify these to add new datasets or adjust pipeline parameters.
