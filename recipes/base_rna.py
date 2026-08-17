"""Shared infrastructure for BDF ORCA recipes.

Common Tower auth, Dataset structure, and workflow orchestration (fetch_samplesheet -> ssynstage ->  modality-specific pipeline -> synindex)
"""
import asyncio
import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import boto3
from orca.services.nextflowtower import NextflowTowerOps
from orca.services.nextflowtower.client import NextflowTowerClient
from orca.services.nextflowtower.config import NextflowTowerConfig
from orca.services.nextflowtower.models import LaunchInfo
from synapseclient import Synapse

session = boto3.Session(profile_name="tower")
s3 = session.client("s3")

# Nextflow version (same as sarek_somatic_workflow baseline)
NXF_VER = "25.10.2"

# Shared process configuration: retry failed tasks up to 3 times
NEXTFLOW_CONFIG = """
process {
  errorStrategy = 'retry'
  maxRetries = 3
}
"""


def _patch_tower_client_double_slash():
    """Fix py-orca URL construction: path has leading slash, causing // in URL and 401.

    orca builds request URLs by joining the api_endpoint with a leading-slash path,
    which yields e.g. https://tower.sagebionetworks.org/api//workflow/launch. The
    doubled slash triggers 400/401 responses from the Tower API. Stripping the leading
    slash from each request path fixes it.
    """
    _original_request = NextflowTowerClient.request

    def _patched_request(self, method: str, path: str, **kwargs):
        path = path.lstrip("/")
        return _original_request(self, method, path, **kwargs)

    NextflowTowerClient.request = _patched_request


def get_tower_ops() -> NextflowTowerOps:
    """Create NextflowTowerOps with config from the three TOWER_* environment variables.

    Uses explicit TOWER_ACCESS_TOKEN / TOWER_WORKSPACE / TOWER_API_ENDPOINT rather than
    the packed NEXTFLOWTOWER_CONNECTION_URI, and applies the double-slash URL patch.
    """
    _patch_tower_client_double_slash()

    token = os.environ.get("TOWER_ACCESS_TOKEN") or os.environ.get("TOWER_AUTH_TOKEN")
    workspace = os.environ.get("TOWER_WORKSPACE")
    api_endpoint = os.environ.get("TOWER_API_ENDPOINT", "https://api.tower.nf")

    if not token:
        raise SystemExit(
            "Missing TOWER_ACCESS_TOKEN. Set it before running:\n"
            "  export TOWER_ACCESS_TOKEN=your-token"
        )
    if not workspace:
        raise SystemExit(
            "Missing TOWER_WORKSPACE. Set it before running (org/workspace format):\n"
            "  export TOWER_WORKSPACE=sage-bionetworks/ntap-add5-project"
        )

    config = NextflowTowerConfig(
        api_endpoint=api_endpoint.rstrip("/"),
        auth_token=token,
        workspace=workspace,
    )
    return NextflowTowerOps(config=config)


@dataclass
class Dataset:
    """Base dataset configuration for all modalities."""

    id: str
    """The synapse id for the samplesheet."""

    samplesheet: str
    """The name of the samplesheet to run."""

    synapse_id_for_output: str
    """The synapse id for the output folder, this is where the output will be uploaded to."""

    bucket_name: str
    """The name of the bucket to stage the samplesheet in."""

    staging_key: str
    """The key in the S3 bucket where this workflow is going to run."""

    run_number: int = 1
    """Run version number. Passed from CLI --run-number; increment to preserve previous outputs."""

    version: int | None = None
    """Synapse version of the samplesheet to fetch. None = latest (default); set to
    pin a specific curated version for reproducible reruns."""

    @property
    def samplesheet_location(self) -> str:
        """The location where the unstaged samplesheet is located."""
        return f"{self.samplesheet_location_prefix}{self.samplesheet}"

    @property
    def samplesheet_to_stage_key(self) -> str:
        """The key in the S3 bucket where the samplesheet is going to be staged."""
        return f"{self.staging_key}to_stage/{self.samplesheet}"

    @property
    def staged_samplesheet_location(self) -> str:
        """The S3 uri where the samplesheet is staged."""
        return f"{self.staging_location}synstage_{self.id}/{self.samplesheet}"

    @property
    def staging_location(self) -> str:
        """The S3 uri where the workflow is going to be run."""
        return f"s3://{self.bucket_name}/{self.staging_key}"

    @property
    def samplesheet_location_prefix(self) -> str:
        """The S3 uri where the unstaged samplesheet is located."""
        return f"s3://{self.bucket_name}/{self.staging_key}to_stage/"

    @property
    def output_directory(self) -> str:
        """The S3 uri where the output is going to be uploaded to."""
        return f"s3://{self.bucket_name}/outputs/{self.id}_{self.run_number}/"

    @property
    def synstage_run_name(self) -> str:
        """The name of the synstage run."""
        return f"synstage_{self.id}"

    @property
    def synindex_run_name(self) -> str:
        """The name of the synindex run."""
        return f"synindex_{self.id}_{self.run_number}"


def fetch_samplesheet(syn: Synapse, dataset: Dataset) -> None:
    """Download the samplesheet from Synapse and upload it to S3.

    Arguments:
        syn: The logged in synapse instance
        dataset: The dataset to stage the samplesheet for
    """
    samplesheet_file = syn.get(dataset.id, version=dataset.version)
    samplesheet_file_path = samplesheet_file.path
    s3.upload_file(
        samplesheet_file_path, dataset.bucket_name, dataset.samplesheet_to_stage_key
    )


def prepare_synstage_info(dataset: Dataset) -> LaunchInfo:
    """Generate LaunchInfo for nf-synstage.

    Arguments:
        dataset: The dataset to stage

    Returns:
        The Nextflow Tower workflow launch specification for synstage step
    """
    return LaunchInfo(
        run_name=dataset.synstage_run_name,
        pipeline="Sage-Bionetworks-Workflows/nf-synapse",
        revision="main",
        profiles=["sage"],
        params={
            "input": dataset.samplesheet_location,
            "outdir": dataset.staging_location,
            "entry": "synstage",
        },
        workspace_secrets=["SYNAPSE_AUTH_TOKEN"]
    )


def prepare_synindex_info(dataset: Dataset) -> LaunchInfo:
    """Generate LaunchInfo for nf-synindex workflow run.

    Arguments:
        dataset: The dataset to index

    Returns:
        The Nextflow Tower workflow launch specification for synindex step
    """
    return LaunchInfo(
        run_name=dataset.synindex_run_name,
        pipeline="Sage-Bionetworks-Workflows/nf-synapse",
        revision="main",
        profiles=["sage"],
        params={
            "s3_prefix": dataset.output_directory,
            "parent_id": dataset.synapse_id_for_output,
            "entry": "synindex",
        },
        workspace_secrets=["SYNAPSE_AUTH_TOKEN"]
    )


async def run_workflows(
    ops: NextflowTowerOps,
    dataset: Dataset,
    step,
    prepare_pipeline_info: Callable[[Dataset], LaunchInfo],
) -> None:
    """Orchestrate the four-step workflow: fetch, synstage, pipeline, synindex.

    Runs steps in sequence, checking success after each step before proceeding.
    Stops if any step fails.

    Arguments:
        ops: NextflowTowerOps instance
        dataset: The dataset to process
        step: Which step(s) to run (or 'all')
        prepare_pipeline_info: Callable that returns LaunchInfo for the pipeline-specific step
    """
    if 'all' in step or 'fetch_samplesheet' in step:
        print('fetching samplesheet')
        syn = Synapse()
        syn.login()
        fetch_samplesheet(syn, dataset)

    if 'all' in step or 'synstage' in step:
        print('starting synstage')
        synstage_info = prepare_synstage_info(dataset)
        synstage_run_id = ops.launch_workflow(synstage_info, "spot", ignore_previous_runs=True)
        status = await ops.monitor_workflow(run_id=synstage_run_id, wait_time=60 * 2)
        print(status)
        if not status.is_successful:
            raise SystemExit(f"synstage failed with status: {status.status}")
        # Don't continue to pipeline if only synstage was requested
        if 'all' not in step:
            return

    if 'all' in step or 'pipeline' in step:
        print('starting pipeline')
        pipeline_info = prepare_pipeline_info(dataset)
        pipeline_run_id = ops.launch_workflow(pipeline_info, "ondemand", ignore_previous_runs=True)
        status = await ops.monitor_workflow(run_id=pipeline_run_id, wait_time=60 * 2)
        print(status)
        if not status.is_successful:
            raise SystemExit(f"pipeline failed with status: {status.status}")
        # Don't continue to synindex if only pipeline was requested
        if 'all' not in step:
            return

    if 'all' in step or 'synindex' in step:
        print('starting synindex')
        synindex_info = prepare_synindex_info(dataset)
        synindex_run_id = ops.launch_workflow(synindex_info, "spot", ignore_previous_runs=True)
        status = await ops.monitor_workflow(run_id=synindex_run_id, wait_time=60 * 2)
        print(status)
        if not status.is_successful:
            raise SystemExit(f"synindex failed with status: {status.status}")


def load_params_from_json(params_path: Path) -> dict:
    """Load science params from JSON, filtering out internal notes (keys starting with '_').

    Reusable across all RNA modalities. Recipes call this once per prepare_*_launch_info().

    Arguments:
        params_path: Path to the .params.json file

    Returns:
        Dictionary of params ready for pipeline
    """
    return {k: v for k, v in json.loads(params_path.read_text()).items() if not k.startswith("_")}


async def main(
    generate_datasets: Callable[[int], list[Dataset]],
    prepare_pipeline_info: Callable[[Dataset], LaunchInfo],
) -> None:
    """Main entry point for all modality recipes.

    Arguments:
        generate_datasets: Callable that returns list of datasets for this modality
        prepare_pipeline_info: Callable that returns LaunchInfo for the pipeline-specific step
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('step', nargs='*', default='all', help='Processing step (Default: all)')
    parser.add_argument('--run-number', type=int, default=1, help='Run version number (Default: 1). Increment to preserve previous outputs.')
    args = parser.parse_args()

    ops = get_tower_ops()
    datasets = generate_datasets(run_number=args.run_number)
    runs = [run_workflows(ops, dataset, args.step, prepare_pipeline_info) for dataset in datasets]
    statuses = await asyncio.gather(*runs)
    print(statuses)
