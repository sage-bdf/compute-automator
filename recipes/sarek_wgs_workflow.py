"""ORCA recipe: nf-core/sarek WGS (whole genome sequencing) somatic variant calling (tumor vs. matched normal), GRCh38.
[Derived from sarek_wes_somatic_workflow.py with only WES-specific parts
commented out. No structural changes, only parameter disabling
Commented out:
  - 'wes': True parameter
  - 'intervals': dataset.intervals parameter
  - BED file definitions (BED_JH, BED_WU)
  - institution parameter
  - intervals property
Runs on Nextflow Tower and returns results to Synapse.]

Orchestrates four steps:
  1. fetch_samplesheet    : Fetch the samplesheet from Synapse to S3
  2. nf-synapse SYNSTAGE  : Download FASTQ files from Synapse to S3
  3. sarek                : Run nf-core/sarek somatic variant calling
  4. nf-synapse SYNINDEX  : Index results back to Synapse

Somatic mode is set by the samplesheet, not a flag: a tumor (status=1) and matched
normal (status=0) sharing a `patient` id trigger tumor-vs-normal calling.

Prerequisites:
  - pip install py-orca; AWS profile `tower`; SYNAPSE_AUTH_TOKEN set as a Tower
    workspace secret (not a user secret).
  - Export Tower credentials before running:
      export TOWER_ACCESS_TOKEN="<token>"
      export TOWER_WORKSPACE="sage-bionetworks/ntap-add5-project"
      export TOWER_API_ENDPOINT="https://tower.sagebionetworks.org/api"

Usage:
  python sarek_wgs_workflow.py [step ...] [--run-number N]
  steps: fetch_samplesheet, synstage, sarek, synindex (default: all)
  increment --run-number for a clean rerun that preserves prior S3 outputs
"""
import asyncio
import argparse
import os
from dataclasses import dataclass

import boto3
from orca.services.nextflowtower import NextflowTowerOps
from orca.services.nextflowtower.client import NextflowTowerClient
from orca.services.nextflowtower.config import NextflowTowerConfig
from orca.services.nextflowtower.models import LaunchInfo
from synapseclient import Synapse

session = boto3.Session(profile_name="tower")
s3 = session.client("s3")


def _patch_tower_client_double_slash():
    """Fix py-orca URL construction: path has leading slash, causing // in URL and 401.

    orca builds request URLs by joining the api_endpoint with a leading-slash path,
    which yields e.g. https://tower.sagebionetworks.org/api//workflow/launch. The
    doubled slash triggers 400/401 responses from the Tower API. Stripping the leading
    slash from each request path fixes it. (Ported from spatialvi_workflow.py.)
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


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('step', nargs='*', default='all', help='Processing step (Default: all)')
    parser.add_argument('--run-number', type=int, default=1, help='Run version number (Default: 1). Increment to preserve previous outputs.')
    args = parser.parse_args()

    ops = get_tower_ops()
    datasets = generate_datasets(run_number=args.run_number)
    runs = [run_workflows(ops, dataset, args.step) for dataset in datasets]
    statuses = await asyncio.gather(*runs)
    print(statuses)


@dataclass
class Dataset:
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

    # institution: str  # COMMENTED OUT for WGS (no BED file selection needed)
    # """The institution that generated the samples ('JH' or 'WU'). Determines the BED file used."""

    run_number: int = 1
    """Run version number. Passed from CLI --run-number; increment to preserve previous outputs."""

    version: int | None = None
    """Synapse version of the samplesheet to fetch. None = latest (default); set to
    pin a specific curated version for reproducible reruns."""

    # @property  # COMMENTED OUT for WGS (no BED file needed)
    # def intervals(self) -> str:
    #     """The S3 uri for the BED file, determined by institution."""
    #     if self.institution == "JH":
    #         return BED_JH
    #     elif self.institution == "WU":
    #         return BED_WU

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
        """The S3 uri where the output is going to be uploaded to. The is used as the
        input for the synindex workflow."""
        return f"s3://{self.bucket_name}/outputs/sarek_somatic_GRCh38_{self.id}_{self.run_number}/"

    @property
    def synstage_run_name(self) -> str:
        """The name of the synstage run."""
        return f"synstage_{self.id}"

    @property
    def sarek_run_name(self) -> str:
        """The name of the sarek run."""
        return f"sarek_somatic_GRCh38_{self.id}_{self.run_number}"

    @property
    def synindex_run_name(self) -> str:
        """The name of the synindex run."""
        return f"synindex_{self.id}_{self.run_number}"


# NOTE: BED files NOT needed for WGS (whole genome calling). Commented out for reference only.
# BED_JH = "s3://ntap-add5-project-tower-bucket/reference/Baits_BED_Files_AgilentV6_REVISED_S07604514_ALLBED_merged_020816_withChr_GRCh38_sorted.bed"
# BED_WU = "s3://ntap-add5-project-tower-bucket/reference/xgen-exome-research-panel-v2-probes-hg3862a5791532796e2eaa53ff00001c1b3c.bed"

# Optional panel of normals for Mutect2. GATK.GRCh38 igenomes already provides the
# af-only-gnomad germline resource, so PON is optional; leave as None to run without one.
# ponytail: no PON by default; set these if a project-matched PON exists to cut FP calls.
PON = None      # e.g. "s3://.../1000g_pon.hg38.vcf.gz"
PON_TBI = None  # e.g. "s3://.../1000g_pon.hg38.vcf.gz.tbi"


def generate_datasets(run_number: int = 1) -> list[Dataset]:
    """Generate list of datasets.

    SOMATIC PAIRING REQUIREMENT (the key difference from the germline recipe):
    each samplesheet must contain, for every patient, a matched normal (status=0)
    AND tumor (status=1) row sharing the same `patient` id, e.g.:

        patient,sample,fastq_1,fastq_2,lane,status
        P1,P1_normal,syn://<n1>,syn://<n2>,P1_normal-lane-1,0
        P1,P1_tumor,syn://<t1>,syn://<t2>,P1_tumor-lane-1,1


    Samplesheet columns: patient,sample,fastq_1,fastq_2,lane,status
    (status 1 = tumor, 0 = normal; fastqs are syn:// URIs resolved by synstage).

    """
    return [
        Dataset(
            #MPNST cell line
            id="syn77362192",
            samplesheet="wgs_mpnst_cell_line_demo_samplesheet.csv",
            staging_key="samplesheets/Sarek_Process/Sarek_WGS/",
            bucket_name="ntap-add5-project-tower-bucket",
            synapse_id_for_output="syn77361958",
#            institution="JH",
            run_number=run_number,
        ),
    ]


def fetch_samplesheet(syn: Synapse, dataset: Dataset) -> None:
    """Download the samplesheet from synapse and upload it to S3 in the location where synstage
    is going to grab the file.

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
        dataset: The dataset to stage the samplesheet for

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
        workspace_secrets=["SYNAPSE_AUTH_TOKEN"]  # set as workspace secret (not user secret) in Tower
    )


def prepare_sarek_launch_info(dataset: Dataset) -> LaunchInfo:
    """Generate LaunchInfo for nf-core/sarek workflow run.

    Arguments:
        dataset: The dataset to stage the samplesheet for

    Returns:
        The Nextflow Tower workflow launch specification for sarek processing step
    """
    params = {
        "input": dataset.staged_samplesheet_location,
        "outdir": dataset.output_directory,
        # "wes": True,  # COMMENTED OUT for WGS (whole genome mode)
        # "intervals": dataset.intervals,  # COMMENTED OUT for WGS (no exome targeting)
        "igenomes_base": "s3://sage-igenomes/igenomes",
        "genome": "GATK.GRCh38",
        "tools": "strelka,mutect2,vep",
    }
    # Optional Mutect2 panel of normals (see PON above).
    if PON:
        params["pon"] = PON
        params["pon_tbi"] = PON_TBI
    return LaunchInfo(
        run_name=dataset.sarek_run_name,
        pipeline="nf-core/sarek",
        revision="3.1.2",  # matches JHU Biobank release-2 (sarek v3.1.2)
        profiles=["sage"],
        params=params,
    )


def prepare_synindex_launch_info(dataset: Dataset) -> LaunchInfo:
    """Generate LaunchInfo for nf-synindex workflow run.

    Arguments:
        dataset: The dataset to stage the samplesheet for

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
        workspace_secrets=["SYNAPSE_AUTH_TOKEN"]  # set as workspace secret (not user secret) in Tower
    )


async def run_workflows(ops: NextflowTowerOps, dataset: Dataset, step):
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
            raise SystemExit(f"synstage failed: {status.state}")

    if 'all' in step or 'sarek' in step:
        print('starting data processing pipeline')
        sarek_info = prepare_sarek_launch_info(dataset)
        sarek_run_id = ops.launch_workflow(sarek_info, "ondemand", ignore_previous_runs=True)  # on-demand: sarek is the long step; avoids spot reclaim mid-run
        status = await ops.monitor_workflow(run_id=sarek_run_id, wait_time=60 * 2)
        print(status)

    if 'all' in step or 'synindex' in step:
        print('starting synindex')
        synindex_info = prepare_synindex_launch_info(dataset)
        synindex_run_id = ops.launch_workflow(synindex_info, "spot", ignore_previous_runs=True)
        status = await ops.monitor_workflow(run_id=synindex_run_id, wait_time=60 * 2)
        print(status)


if __name__ == "__main__":
    asyncio.run(main())
