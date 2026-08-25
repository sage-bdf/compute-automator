# Compute Automator

ORCA recipes for Biomedical Data Fabric (BDF) data processing on Nextflow Tower.

## Supported Modalities

| Modality | Recipe | Pipeline | Status |
|----------|--------|----------|--------|
| WES/WGS | sarek_somatic_workflow.py | nf-core/sarek v3.1.2 | ✓ |
| Bulk RNA-seq | rnaseq_workflow.py | nf-core/rnaseq v3.11.2 | ✓ |
| Single-cell RNA-seq | scrnaseq_workflow.py | nf-core/scrnaseq v4.1.0 | ✓ |
| Spatial transcriptomics | [External](https://github.com/sage-bdf/synapse_spatialvi_nf_pipeline) | nf-core/spatialvi dev | ✓ |


## Workflow Architecture

Each recipe follows a standardized four-step workflow orchestrated by ORCA (Nextflow Tower):
1. **fetch_samplesheet**: Download samplesheet from Synapse to S3
2. **synstage**: Download input files (FASTQ, BAM, etc.) from Synapse to S3
3. **pipeline**: Run nf-core pipeline on staged data
4. **synindex**: Upload results back to Synapse

## Usage

Install dependencies first (in your environment):
```bash
pip install py-orca synapseclient
```

Set environment variables:
```bash
export TOWER_ACCESS_TOKEN="<your-token>"
export TOWER_WORKSPACE="sage-bionetworks/ntap-add5-project"
export TOWER_API_ENDPOINT="https://tower.sagebionetworks.org/api"
```

Run a recipe (all steps by default):
```bash
python recipes/sarek_somatic_workflow.py
python recipes/rnaseq_workflow.py
python recipes/scrnaseq_workflow.py
```

Run specific steps:
```bash
python recipes/rnaseq_workflow.py fetch_samplesheet synstage
python recipes/rnaseq_workflow.py rnaseq synindex
python recipes/scrnaseq_workflow.py synstage scrnaseq
```

Increment run number to preserve previous outputs:
```bash
python recipes/rnaseq_workflow.py --run-number 2
```

## Recipes

- **sarek_somatic_workflow.py**: WES variant calling (tumor vs. matched normal)
  - Pipeline: [nf-core/sarek](https://github.com/nf-core/sarek) v3.1.2
  - Config: GATK.GRCh38, WES + Agilent V6 intervals, callers: strelka, mutect2, vep
  - Based on [JHU NF1 Biobank release-2](https://github.com/nf-osi/biobank-release-2) (JH_batch1)
  - Input samplesheet: [syn52236715](https://www.synapse.org/Synapse:syn52236715)
  - **Note**: Standalone (does not use base_rna.py)
  - Usage: See docstring in `sarek_somatic_workflow.py`

- **rnaseq_workflow.py**: Bulk RNA-seq alignment and quantification
  - Pipeline: [nf-core/rnaseq](https://github.com/nf-core/rnaseq) v3.11.2
  - Config: GRCh38, STAR + Salmon quantification
  - Based on NF-OSI Nextflow Data Processing standard
  - Input samplesheet: syn76923670
  - Output folder: syn76921355
  - Uses: base_rna.py (shared module)
  - Usage: See docstring in `rnaseq_workflow.py`

- **scrnaseq_workflow.py**: Single-cell RNA-seq processing
  - Pipeline: [nf-core/scrnaseq](https://github.com/nf-core/scrnaseq) v4.1.0
  - Config: GRCh38 reference (10x CellRanger pre-built), CellRanger (alignment) + CellBender (ambient RNA correction)
  - Input samplesheet: syn76926335
  - Output folder: syn76921961
  - Uses: base_rna.py (shared module)
  - Usage: See docstring in `scrnaseq_workflow.py`

#### 10x Chromium v2 Protocol Verification

The sample data originates from Olah et al. 2020 (https://www.nature.com/articles/s41467-020-19737-2), 
which specifies in the Methods:

> "Upon dissolution of the Single Cell 3′ Gel Bead in a GEM, primers containing (i) an Illumina R1 
> sequence (read 1 sequencing primer), (ii) a **16 nucleotide 10x Barcode**, (iii) a **10 nucleotide 
> Unique Molecular Identifier (UMI)**, and (iv) a poly-dT primer sequence..."

This matches **10x Chromium v2** specification:
- Read 1: 26 cycles = 16bp cell barcode + 10bp UMI
- (Note: 10x Chromium v3 uses 16bp barcode + 12bp UMI)

Reference: [10x Chromium v2 Structure](https://scg-lib-structs.readthedocs.io/en/latest/ge/10xChromium3v2.html)

## Implementation

### Recipe Structure

- **WES Somatic (sarek_somatic_workflow.py)**: Self-contained with direct Tower orchestration
- **RNA Modalities (rnaseq, scrnaseq)**: Use shared base_rna.py for standardized workflow

### base_rna.py

Shared infrastructure for RNA modalities (rnaseq, scrnaseq). Manages Tower authentication, dataset configuration, samplesheet staging, workflow orchestration, and parameter management.

### Pipeline Configuration

Science parameters are defined in `config/`:
- `rnaseq.params.json`: nf-core/rnaseq settings (aligner, genome, reference)
- `scrnaseq.params.json`: nf-core/scrnaseq settings (protocol, genome, reference)

### Extending Pipelines

To add new datasets or modify pipeline parameters:
1. Update `generate_datasets()` in recipe file to specify Synapse IDs and run configurations
2. Modify `config/[modality].params.json` for science parameters
3. Adjust `prepare_[pipeline]_launch_info()` for pipeline-specific settings
