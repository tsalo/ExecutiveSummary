"""Builds the layout for the Executive Summary of output from DCAN-Labs fMRI pipelines."""

__version__ = "2.0.0"

import argparse
import os
from datetime import datetime

from workflow import interface


def generate_parser():
    """Generate parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="ExecutiveSummary",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        dest="output_dir",
        required=True,
        metavar="FILES_PATH",
        help="path to the output files directory for all intermediate and "
        'output files from the pipeline. Path should end with "files".',
    )
    parser.add_argument(
        "--bids-input",
        "-i",
        dest="bids_dir",
        metavar="FUNC_PATH",
        help="path to the bids dataset that was used as task input to the "
        'pipeline. Path should end with "func"',
    )
    parser.add_argument(
        "--participant-label",
        "-p",
        dest="subject_id",
        required=True,
        metavar="PARTICIPANT_LABEL",
        help='participant label, not including "sub-".',
    )
    parser.add_argument(
        "--session-id",
        "-s",
        dest="session_id",
        metavar="SESSION_ID",
        help="filter input dataset by session id. Default is all ids "
        "found under each subject output directory(s). A session id "
        'does not include "ses-"',
    )
    parser.add_argument(
        "--dcan-summary",
        "-d",
        dest="summary_dir",
        metavar="DCAN_SUMMARY",
        help="Optional. Expects the name of the subdirectory used for the summary data. "
        'Directory should be relative to "files" and whatever directory is specified '
        "will be used to find needed data from dcan bold processing. "
        "Example: summary_DCANBOLDProc_v4.0.0",
    )
    # TAYLOR: This doesn't sound like an atlas...
    parser.add_argument(
        "--atlas",
        "-a",
        dest="atlas",
        metavar="ATLAS_PATH",
        help="Optional. Expects the path to the atlas to register to the images. "
        "Default: templates/MNI_T1_1mm_brain.nii.gz. ",
    )
    parser.add_argument(
        "--version", "-v", action="version", version="%(prog)s " + __version__
    )
    parser.add_argument(
        "--layout-only",
        dest="layout_only",
        action="store_true",
        help="Can be specified for subjects that have been run through the "
        "executivesummary preprocessor, so the image data is ready. This "
        "calls only the layout_builder to get the latest layout. ",
    )

    return parser


def _cli():
    # Command line interface
    parser = generate_parser()
    args = parser.parse_args()

    date_stamp = datetime.strftime(datetime.now(), format="%Y%m%d %H:%M")

    print(f"Executive Summary was called at {date_stamp} with:")
    print(f"\tOutput directory:      {args.output_dir}")
    print(f"\tSubject:               {args.subject_id}")

    # output_dir is required, and the parser would have squawked if there was
    # not a value for output_dir. Just make sure it's a real directory.
    assert os.path.isdir(args.output_dir), args.output_dir + " is not a directory!"

    kwargs = {
        "files_path": args.output_dir,
        "subject_id": args.subject_id,
        "layout_only": args.layout_only,
    }

    # If the caller specifies an arg is None, python is treating it as a string.
    # So, do some extra checking before passing the values to the interface.
    if not (args.bids_dir is None or args.bids_dir.upper() == "NONE"):
        print(f"\tBIDS input files:      {args.bids_dir}")
        kwargs["func_path"] = args.bids_dir

    if not (args.summary_dir is None or args.summary_dir.upper() == "NONE"):
        print(f"\tSummary directory:     {args.summary_dir}")
        kwargs["summary_dir"] = args.summary_dir

    # For Session id, None *can* be a valid string. Leave as is.
    print(f"\tSession:               {args.session_id}")
    kwargs["session_id"] = args.session_id

    # If the user specified an atlas, make sure it exists.
    print(f"\tAtlas:                 {args.atlas}")
    if not (args.atlas is None or args.atlas.upper() == "NONE"):
        assert os.path.exists(args.atlas), args.atlas + " does not exist!"
        kwargs["atlas"] = args.atlas

    # Call the interface.
    interface(**kwargs)


if __name__ == "__main__":
    _cli()
    print("\nall done!")
