# Compute Automator

ORCA recipes for Biomedical Data Fabric (BDF) data processing on Nextflow Tower.

## Recipes

- **sarek_somatic_workflow.py** — WES variant calling (tumor vs. matched normal)
  - Pipeline: [nf-core/sarek](https://github.com/nf-core/sarek) v3.1.2
  - Config: GATK.GRCh38, WES + Agilent V6 intervals, callers: strelka, mutect2, vep
  - Based on [JHU NF1 Biobank release-2](https://github.com/nf-osi/biobank-release-2) (JH_batch1)
  - Input samplesheet: [syn52236715](https://www.synapse.org/Synapse:syn52236715)
  - Usage: See docstring in `sarek_somatic_workflow.py`
