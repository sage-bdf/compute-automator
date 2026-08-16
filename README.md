# BDF ORCA Recipes

Nextflow Tower orchestration scripts for Biomedical Data Fabric data processing pipelines.

## Overview

Each recipe runs a standardized four-step workflow:
1. **fetch_samplesheet** — pull the samplesheet from Synapse to S3
2. **synstage** — download input FASTQ files from Synapse to S3
3. **pipeline** — run the actual processing (sarek, rnaseq, scrnaseq, etc.)
4. **synindex** — upload results back to Synapse

## Recipes

### sarek_somatic_workflow.py
WES variant calling (tumor vs. matched normal).
- Pipeline: nf-core/sarek v3.1.2
- Based on JHU NF1 Biobank release-2
- Requires paired tumor/normal samples

```bash
python sarek_somatic_workflow.py [step ...] [--run-number N]
```

### rnaseq_workflow.py
Bulk RNA-seq alignment and quantification.
- Pipeline: nf-core/rnaseq v3.11.1
- Based on ALS project runbook (sage_brain_repo)
- Reference genome: GRCh38

```bash
python rnaseq_workflow.py [step ...] [--run-number N]
```

### scrnaseq_workflow.py
Single-cell RNA-seq QC, alignment, quantification.
- Pipeline: nf-core/scrnaseq
- Requires protocol specification (10x, etc.)

```bash
python scrnaseq_workflow.py [step ...] [--run-number N]
```

## Prerequisites

```bash
pip install py-orca
```

AWS profile `tower` configured, and Synapse auth token set as a Tower workspace secret.

## Environment setup

Export Tower credentials before running any recipe:

```bash
export TOWER_ACCESS_TOKEN="<your-token>"
export TOWER_WORKSPACE="sage-bionetworks/ntap-add5-project"
export TOWER_API_ENDPOINT="https://tower.sagebionetworks.org/api"
```

## Recipes

Located in `recipes/`:
- **sarek_somatic_workflow.py** — WES somatic variant calling (tumor vs. matched normal)
- **rnaseq_workflow.py** — Bulk RNA-seq alignment and quantification
- **scrnaseq_workflow.py** — Single-cell RNA-seq processing

## Configuration

Located in `config/`:
- **rnaseq.params.json** — Parameters for nf-core/rnaseq (aligner, genome, etc.)
- **scrnaseq.params.json** — Parameters for nf-core/scrnaseq (protocol, aligner, etc.)

## Pipeline Details

### WES Somatic Variant Calling (sarek_somatic_workflow.py)
- Pipeline: nf-core/sarek v3.1.2
- Genome: GATK.GRCh38
- Variant callers: Strelka2, Mutect2, VEP
- Based on JHU NF1 Biobank release-2 (JH_batch1)
- Requirement: Samplesheet must have paired tumor/normal samples (tumor status=1, normal status=0, same patient ID)

### Bulk RNA-seq (rnaseq_workflow.py)
- Pipeline: nf-core/rnaseq v3.11.2
- Aligner: STAR with Salmon quantification
- Genome: GRCh38
- Based on NF-OSI Nextflow Data Processing standard

### Single-Cell RNA-seq (scrnaseq_workflow.py)
- Pipeline: nf-core/scrnaseq
- TODO: Define pipeline version and scRNA-seq-specific parameters
- Supported protocols: 10x, CEL-Seq2, MARS-Seq, Seq-Well, etc.

## Shared Infrastructure

**base_rna.py** — Common functions for RNA modalities (rnaseq, scrnaseq).
- Dataset configuration
- fetch_samplesheet, prepare_synstage_info, prepare_synindex_info
- load_params_from_json() — load science params from JSON
- Workflow orchestration (main entry point)

Note: wes/sarek_somatic_workflow.py is standalone (does not use base_rna.py).

## Configuration

Each recipe defines:
- **generate_datasets()** — list of datasets to process (synapse IDs, S3 paths)
- **prepare_[pipeline]_launch_info()** — pipeline-specific params and version
- **[modality].params.json** — Science parameters (aligner, genome, etc.)

Modify these to add new datasets or adjust pipeline parameters.
