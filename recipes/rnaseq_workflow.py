"""ORCA recipe: nf-core/rnaseq bulk RNA-seq processing on GRCh38.
Runs on Nextflow Tower and returns results to Synapse.

Orchestrates four steps:
  1. fetch_samplesheet    : Fetch the samplesheet from Synapse to S3
  2. nf-synapse SYNSTAGE  : Download FASTQ files from Synapse to S3
  3. rnaseq               : Run nf-core/rnaseq STAR + Salmon quantification
  4. nf-synapse SYNINDEX  : Index results back to Synapse

Reproduces NF-OSI Nextflow Data Processing configuration:
https://sagebionetworks.jira.com/wiki/spaces/NPD/pages/2595913729/

Prerequisites:
  - pip install py-orca; AWS profile `tower`; SYNAPSE_AUTH_TOKEN set as a Tower
    workspace secret (not a user secret).
  - Export Tower credentials before running:
      export TOWER_ACCESS_TOKEN="<token>"
      export TOWER_WORKSPACE="sage-bionetworks/ntap-add5-project"
      export TOWER_API_ENDPOINT="https://tower.sagebionetworks.org/api"

Usage:
  python rnaseq_workflow.py [step ...] [--run-number N]
  steps: fetch_samplesheet, synstage, rnaseq, synindex (default: all)
  increment --run-number for a clean rerun that preserves prior S3 outputs
"""
import asyncio
from pathlib import Path

from orca.services.nextflowtower.models import LaunchInfo

from base_rna import Dataset, load_params_from_json, main, NXF_VER, NEXTFLOW_CONFIG

# Load science params (aligner, genome, etc.) from config/rnaseq.params.json
PARAMS_PATH = Path(__file__).parent.parent / "config" / "rnaseq.params.json"


def generate_datasets(run_number: int = 1) -> list[Dataset]:
    """Generate list of RNA-seq datasets (modality-specific).

    Define datasets with Synapse IDs for samplesheets and output folders.
    """
    return [
        Dataset(
            id="syn76923670",
            samplesheet="rnaseq_samplesheet.csv",
            staging_key="samplesheets/RNAseq/",
            bucket_name="ntap-add5-project-tower-bucket",
            synapse_id_for_output="syn76921355",
            run_number=run_number,
        ),
    ]


def prepare_rnaseq_launch_info(dataset: Dataset) -> LaunchInfo:
    """Generate LaunchInfo for nf-core/rnaseq workflow run (modality-specific).

    Loads params from rnaseq.params.json, adds input/outdir, returns Tower launch spec.
    """
    params = load_params_from_json(PARAMS_PATH)
    params["input"] = dataset.staged_samplesheet_location
    params["outdir"] = dataset.output_directory
    return LaunchInfo(
        run_name=f"rnaseq_GRCh38_{dataset.id}_{dataset.run_number}",
        pipeline="nf-core/rnaseq",
        revision="3.11.2",
        profiles=["sage"],
        params=params,
        pre_run_script=f"export NXF_VER={NXF_VER}",
        nextflow_config=NEXTFLOW_CONFIG,
    )


if __name__ == "__main__":
    asyncio.run(main(generate_datasets, prepare_rnaseq_launch_info))
