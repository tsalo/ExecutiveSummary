"""Builds the layout for the Executive Summary of output from DCAN-Labs fMRI pipelines."""

__version__ = "2.0.0"

import argparse
import os
import shutil
from datetime import datetime
from math import sqrt
from re import split

from PIL import Image  # for BrainSprite

from layout_builder import layout_builder
from preprocessing import preprocess


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


def init_summary(proc_files, summary_dir=None, layout_only=False):
    """Initialize summary."""
    summary_path = None
    html_path = None
    images_path = None

    summary_path = proc_files
    if summary_dir is not None:
        summary_path = os.path.join(proc_files, summary_dir)

    if os.path.isdir(summary_path):
        # Build the directory tree for the output.
        # This also ensures we can write to the path.
        html_path = os.path.join(summary_path, "executivesummary")

        # If we are going to create the files, need to clean up old files.
        if os.path.exists(html_path) and not layout_only:
            shutil.rmtree(html_path)

        if not os.path.exists(html_path):
            try:
                os.makedirs(html_path)

            except OSError as err:
                print(
                    "cannot make executivesummary folder within path... permissions? \n"
                    f"Path: {summary_path}"
                )
                print(f"OSError: {err}")
                summary_path = None
                html_path = None
    else:
        print(f"Directory does not exist: {summary_path}")
        summary_path = None

    if html_path is not None:

        images_path = os.path.join(html_path, "img")

        if not os.path.exists(images_path):
            try:
                os.makedirs(images_path)
            except OSError as err:
                print(
                    f"cannot make img folder within path... permissions? \nPath: {html_path}"
                )
                print(f"OSError: {err}")
                summary_path = None
                html_path = None
                images_path = None

    return summary_path, html_path, images_path


def natural_sort(list_):
    """Need this function so frames sort in correct order."""

    def convert(text):
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key):
        return [convert(c) for c in split("([0-9]+)", key)]

    return sorted(list_, key=alphanum_key)


def make_mosaic(png_path, mosaic_path):
    """Take path to .png anatomical slices, create a mosaic, and save to file.

    The mosaic will be usable in a BrainSprite viewer.
    """
    # Get the cwd so we can get back; then change directory.
    cwd = os.getcwd()
    os.chdir(png_path)

    files = os.listdir(png_path)
    files = natural_sort(files)
    files = files[::-1]

    image_dim = 218
    images_per_side = int(sqrt(len(files)))
    square_dim = image_dim * images_per_side
    result = Image.new("RGB", (square_dim, square_dim))

    for index, file in enumerate(files):
        path = os.path.expanduser(file)
        img = Image.open(path)
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        img.thumbnail((image_dim, image_dim), resample=Image.ANTIALIAS)
        x = index % images_per_side * image_dim
        y = index // images_per_side * image_dim
        w, h = img.size
        result.paste(img, (x, y, x + w, y + h))

    # Back to original working dir.
    os.chdir(cwd)

    quality_val = 95
    dest = os.path.join(mosaic_path)
    result.save(dest, "JPEG", quality=quality_val)


def preprocess_tx(tx, files_path, images_path):
    """If there are pngs for tx, make the mosaic file for the brainsprite.

    If not, no problem. Layout will use the mosaic if it is there.
    """
    pngs = tx + "_pngs"
    pngs_dir = os.path.join(files_path, pngs)

    if os.path.isdir(pngs_dir):
        # Call the program to make the mosaic from the pngs. and write
        mosaic = tx + "_mosaic.jpg"
        mosaic_path = os.path.join(images_path, mosaic)
        make_mosaic(pngs_dir, mosaic_path)
    else:
        print(f"There is no path: {pngs_dir}.")


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


def interface(
    files_path,
    subject_id,
    summary_dir=None,
    func_path=None,
    session_id=None,
    atlas=None,
    layout_only=False,
):
    """Run the interface."""
    # Most of the data needed is in the summary directory. Also, it is where the
    # preprocessor will make the images and where the layout_builder will write
    # the HTML. We must be able to write to the path.
    if summary_dir is not None:
        print(f"summary_dir is {summary_dir}")

    summary_path, html_path, images_path = init_summary(
        files_path, summary_dir, layout_only
    )
    if summary_path is None:
        # We were not able to find and/or write to the path.
        print("Exiting.")
        return

    if not layout_only:
        # preproc_cmd = os.path.join(
        #     os.path.dirname(os.path.abspath(__file__)),
        #     "executivesummary_preproc.sh",
        # )
        # preproc_cmd += f" --output-dir {files_path}"
        # preproc_cmd += f" --html-path {html_path}"
        # preproc_cmd += f" --subject-id {subject_id}"
        # if session_id is not None:
        #     preproc_cmd += f" --session-id {session_id}"
        #
        # if func_path is not None:
        #     preproc_cmd += f" --bids-input {func_path}"
        #
        # if atlas is not None:
        #     preproc_cmd += f" --atlas {atlas}"
        #
        # subprocess.call(preproc_cmd, shell=True)

        preprocess(
            output_dir=files_path,
            html_path=html_path,
            subject_id=subject_id,
            brainsprite_template=None,  # use default
            pngs_template=None,  # use default
            session_id=session_id,
            bids_input=func_path,
            atlas=atlas,
            skip_sprite=False,  # non-debug mode
            group="fnl_lab",
        )

        # Make mosaic(s) for brainsprite(s).
        print("Making mosaic for T1 BrainSprite.")
        preprocess_tx("T1", files_path, images_path)
        print("Making mosaic for T2 BrainSprite.")
        preprocess_tx("T2", files_path, images_path)
        print("Finished with preprocessing.")

    # Done with preproc (or skipped it). Call the page layout to make the page.
    print("Begin page layout.")
    layout_builder(
        files_path=files_path,
        summary_path=summary_path,
        html_path=html_path,
        images_path=images_path,
        subject_id=subject_id,
        session_id=session_id,
    )


if __name__ == "__main__":
    _cli()
    print("\nall done!")
