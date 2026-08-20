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

from base_rna import Dataset, load_params_from_json, prepare_pipeline_launch_info, main

# Load science params (aligner, genome, etc.) from config/rnaseq.params.json
PARAMS_PATH = Path(__file__).parent.parent / "config" / "rnaseq.params.json"


def generate_datasets(run_number: int = 1) -> list[Dataset]:
    """Generate list of RNA-seq datasets (modality-specific).

    Define datasets with Synapse IDs for samplesheets and output folders.
    """
    params = load_params_from_json(PARAMS_PATH)
    return [
        Dataset(
            id=params["input_samplesheet_id"],
            samplesheet="rnaseq_samplesheet.csv",
            staging_key="samplesheets/RNAseq/",
            bucket_name="ntap-add5-project-tower-bucket",
            synapse_id_for_output=params["output_folder_id"],
            run_number=run_number,
        ),
    ]


def prepare_rnaseq_launch_info(dataset: Dataset) -> LaunchInfo:
    """Generate LaunchInfo for nf-core/rnaseq workflow run.

    Delegates to shared factory in base_rna.py.
    """
    return prepare_pipeline_launch_info("rnaseq", PARAMS_PATH, dataset)


if __name__ == "__main__":
    asyncio.run(main(generate_datasets, prepare_rnaseq_launch_info))
