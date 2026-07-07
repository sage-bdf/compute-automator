# Bulk RNA-seq (PDX)

PDX bulk RNA-seq processing. Includes a **BBSplit** step to separate mouse reads from human reads before quantification.

| Artifact | Value |
|----------|-------|
| Pipeline | [nf-core/rnaseq](https://github.com/nf-core/rnaseq) |
| Sample sheet | [`samplesheet.csv`](samplesheet.csv) — `sample,fastq_1,fastq_2,strandedness,seq_platform` |
| Config | [`nextflow.config`](nextflow.config) (from [nf-core/rnaseq](https://github.com/nf-core/rnaseq/blob/master/nextflow.config)) |
| ORCA recipe | TODO — link orca-recipe |
| Synapse input folder | TODO — synID |
| Synapse output dataset | TODO — synID |

## TODO
- [ ] Fill in real sample sheet rows from the PDX example dataset
- [ ] Confirm BBSplit reference and parameters in config
- [ ] Link ORCA recipe and Synapse input/output folders
