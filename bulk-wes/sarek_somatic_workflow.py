"""ORCA recipe: nf-core/sarek WES somatic variant calling (tumor vs. matched normal), GRCh38.
Runs on Nextflow Tower and returns results to Synapse.

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
  python sarek_somatic_workflow.py [step ...] [--run-number N]
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

    institution: str
    """The institution that generated the samples ('JH' or 'WU'). Determines the BED file used."""

    run_number: int = 1
    """Run version number. Passed from CLI --run-number; increment to preserve previous outputs."""

    version: int | None = None
    """Synapse version of the samplesheet to fetch. None = latest (default); set to
    pin a specific curated version for reproducible reruns."""

    @property
    def intervals(self) -> str:
        """The S3 uri for the BED file, determined by institution."""
        if self.institution == "JH":
            return BED_JH
        elif self.institution == "WU":
            return BED_WU

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


# BED files for exome seq data from JHU NF1 repository - different batches/institutions
BED_JH = "s3://ntap-add5-project-tower-bucket/reference/Baits_BED_Files_AgilentV6_REVISED_S07604514_ALLBED_merged_020816_withChr_GRCh38_sorted.bed"
BED_WU = "s3://ntap-add5-project-tower-bucket/reference/xgen-exome-research-panel-v2-probes-hg3862a5791532796e2eaa53ff00001c1b3c.bed"

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

    JH_batch1 (syn52236715) already provides these matched pairs, including triads
    where a patient carries both a benign and a malignant tumor (two status=1 rows)
    against one blood normal. Any tumor lacking a matched normal would fall back to
    Mutect2 tumor-only mode plus a PON; none are expected in this batch.

    Scoped to JH_batch1 to reproduce the JHU NF1 Biobank release-2 somatic run
    (https://github.com/nf-osi/biobank-release-2). JH_batch1 uses the Agilent V6
    capture kit (BED_JH). Build the paired samplesheet from the patient triads
    (blood normal status=0; benign + malignant tumors status=1, all sharing the
    patient id) rather than the germline tumor-only JH_batch1 sheet.

    Source: https://sagebionetworks.jira.com/browse/WORKFLOWS-538
    Samplesheets: https://www.synapse.org/Synapse:syn74378396

    Samplesheet columns: patient,sample,fastq_1,fastq_2,lane,status
    (status 1 = tumor, 0 = normal; fastqs are syn:// URIs resolved by synstage).

    TODO: fill in the output folder synID.
    """
    return [
        Dataset(
            # JH_batch1 paired tumor/normal (triads: blood normal + benign + malignant)
            id="syn76340211",
            samplesheet="jhu_biobank_wes_demo_samplesheet.csv",
            staging_key="samplesheets/Sarek_Process/EAGER-somatic/",
            bucket_name="ntap-add5-project-tower-bucket",
            synapse_id_for_output="syn76340288",
            institution="JH",
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
        "wes": True,
        "intervals": dataset.intervals,
        "igenomes_base": "s3://sage-igenomes/igenomes",
        "genome": "GATK.GRCh38",
        # Reproduces JHU NF1 Biobank release-2 somatic calling: Strelka2 (published
        # SNV caller) + Mutect2, annotated with VEP.
        # https://github.com/nf-osi/biobank-release-2 (experiments/exploratory/somatic_snv_Reanalysis.Rmd)
        # Note: biobank used VEP v99.2 + vcf2maf downstream; sarek's bundled VEP version
        # differs, and vcf2maf (MAF conversion) is a separate post-step not run here.
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

    if 'all' in step or 'sarek' in step:
        print('starting data processing pipeline')
        sarek_info = prepare_sarek_launch_info(dataset)
        sarek_run_id = ops.launch_workflow(sarek_info, "spot", ignore_previous_runs=True)
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
