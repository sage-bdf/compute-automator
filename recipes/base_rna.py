"""Shared infrastructure for BDF ORCA recipes.

Common Tower auth, Dataset structure, and workflow orchestration.
"""
import asyncio
import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orca.services.nextflowtower import NextflowTowerOps
from orca.services.nextflowtower.client import NextflowTowerClient
from orca.services.nextflowtower.config import NextflowTowerConfig
from orca.services.nextflowtower.models import LaunchInfo
from synapseclient import Synapse

NXF_VER = "25.10.2"
NEXTFLOW_CONFIG = "process { errorStrategy = 'retry'; maxRetries = 3 }"

_s3_client = None
_tower_client_patched = False


def _get_s3_client():
    """Lazy-load S3 client (avoids requiring 'tower' AWS profile at import time)."""
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.Session(profile_name="tower").client("s3")
    return _s3_client


def _patch_tower_client_double_slash():
    """Fix py-orca URL double-slash bug (idempotent)."""
    global _tower_client_patched
    if _tower_client_patched:
        return
    _original = NextflowTowerClient.request
    NextflowTowerClient.request = lambda self, m, p, **kw: _original(self, m, p.lstrip("/"), **kw)
    _tower_client_patched = True


def get_tower_ops() -> NextflowTowerOps:
    """Create Tower ops from TOWER_* env vars (with double-slash URL fix)."""
    _patch_tower_client_double_slash()
    token = os.environ.get("TOWER_ACCESS_TOKEN") or os.environ.get("TOWER_AUTH_TOKEN")
    workspace = os.environ.get("TOWER_WORKSPACE")
    if not token:
        raise SystemExit("Missing TOWER_ACCESS_TOKEN or TOWER_AUTH_TOKEN")
    if not workspace:
        raise SystemExit("Missing TOWER_WORKSPACE (org/workspace format)")
    return NextflowTowerOps(NextflowTowerConfig(
        api_endpoint=os.environ.get("TOWER_API_ENDPOINT", "https://api.tower.nf").rstrip("/"),
        auth_token=token,
        workspace=workspace,
    ))


@dataclass
class Dataset:
    """Dataset config: samplesheet location, S3 paths, output folder."""
    id: str
    samplesheet: str
    synapse_id_for_output: str
    bucket_name: str
    staging_key: str
    run_number: int = 1
    version: int | None = None

    @property
    def samplesheet_location(self) -> str:
        return f"{self.samplesheet_location_prefix}{self.samplesheet}"

    @property
    def samplesheet_to_stage_key(self) -> str:
        return f"{self.staging_key}to_stage/{self.samplesheet}"

    @property
    def staged_samplesheet_location(self) -> str:
        return f"{self.staging_location}synstage_{self.id}/{self.samplesheet}"

    @property
    def staging_location(self) -> str:
        return f"s3://{self.bucket_name}/{self.staging_key}"

    @property
    def samplesheet_location_prefix(self) -> str:
        return f"s3://{self.bucket_name}/{self.staging_key}to_stage/"

    @property
    def output_directory(self) -> str:
        return f"s3://{self.bucket_name}/outputs/{self.id}_{self.run_number}/"

    @property
    def synstage_run_name(self) -> str:
        return f"synstage_{self.id}"

    @property
    def synindex_run_name(self) -> str:
        return f"synindex_{self.id}_{self.run_number}"


def fetch_samplesheet(syn: Synapse, dataset: Dataset) -> None:
    """Download samplesheet from Synapse, upload to S3."""
    path = syn.get(dataset.id, version=dataset.version).path
    _get_s3_client().upload_file(path, dataset.bucket_name, dataset.samplesheet_to_stage_key)


def _launch_nf_synapse(dataset: Dataset, entry: str) -> LaunchInfo:
    """Shared nf-synapse launcher for synstage/synindex."""
    params = {
        "synstage": {"input": dataset.samplesheet_location, "outdir": dataset.staging_location},
        "synindex": {"s3_prefix": dataset.output_directory, "parent_id": dataset.synapse_id_for_output},
    }[entry]
    params["entry"] = entry
    run_name = dataset.synstage_run_name if entry == "synstage" else dataset.synindex_run_name
    return LaunchInfo(
        run_name=run_name, pipeline="Sage-Bionetworks-Workflows/nf-synapse", revision="main",
        profiles=["sage"], params=params, workspace_secrets=["SYNAPSE_AUTH_TOKEN"]
    )


def prepare_synstage_info(dataset: Dataset) -> LaunchInfo:
    return _launch_nf_synapse(dataset, "synstage")


def prepare_synindex_info(dataset: Dataset) -> LaunchInfo:
    return _launch_nf_synapse(dataset, "synindex")


async def run_workflows(ops: NextflowTowerOps, dataset: Dataset, steps: list, modality: str, prepare_pipeline: Callable) -> None:
    """Run requested steps sequentially; fail fast on error."""
    step_order = ['fetch_samplesheet', 'synstage', modality, 'synindex']
    steps_to_run = step_order if 'all' in steps else [s for s in step_order if s in steps]

    for step in steps_to_run:
        if step == 'fetch_samplesheet':
            print('fetching samplesheet')
            syn = Synapse()
            syn.login()
            fetch_samplesheet(syn, dataset)
        else:
            info_map = {
                'synstage': prepare_synstage_info(dataset),
                modality: prepare_pipeline(dataset),
                'synindex': prepare_synindex_info(dataset),
            }
            print(f'starting {step}')
            launch_type = "ondemand" if step == modality else "spot"
            run_id = ops.launch_workflow(info_map[step], launch_type, ignore_previous_runs=True)
            status = await ops.monitor_workflow(run_id, wait_time=120)
            print(status)
            if not status.is_successful:
                raise SystemExit(f"{step} failed: {status.state}")


def load_params_from_json(params_path: Path) -> dict:
    """Load params from JSON, skip keys starting with '_'."""
    return {k: v for k, v in json.loads(params_path.read_text()).items() if not k.startswith("_")}


def prepare_pipeline_launch_info(modality: str, params_path: Path, dataset: Dataset) -> LaunchInfo:
    """Generic factory for RNA pipeline launches (rnaseq/scrnaseq)."""
    params = load_params_from_json(params_path)
    pipeline_name = params.pop("pipeline_name")
    revision = params.pop("pipeline_revision")
    genome = params.get("genome")
    params["input"] = dataset.staged_samplesheet_location
    params["outdir"] = dataset.output_directory
    return LaunchInfo(
        run_name=f"{modality}_{genome}_{dataset.id}_{dataset.run_number}",
        pipeline=pipeline_name, revision=revision, profiles=["sage"], params=params,
        pre_run_script=f"export NXF_VER={NXF_VER}", nextflow_config=NEXTFLOW_CONFIG,
    )


async def main(generate_datasets: Callable[[int], list[Dataset]], prepare_pipeline: Callable) -> None:
    """Main entry point for all recipes."""
    # Extract modality from script name: rnaseq_workflow.py → rnaseq
    modality = Path(sys.argv[0]).stem.replace('_workflow', '')

    parser = argparse.ArgumentParser()
    step_names = ['fetch_samplesheet', 'synstage', modality, 'synindex']
    parser.add_argument('step', nargs='*', default=['all'], help=f"Step(s) to run: {', '.join(step_names)} (default: all)")
    parser.add_argument('--run-number', type=int, default=1, help='Run version (default: 1)')
    args = parser.parse_args()
    ops = get_tower_ops()
    datasets = generate_datasets(run_number=args.run_number)
    await asyncio.gather(*(run_workflows(ops, ds, args.step, modality, prepare_pipeline) for ds in datasets))
