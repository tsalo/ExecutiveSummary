"""Main functions for ExecutiveSummary."""
import os
import shutil
from math import sqrt
from re import split

from PIL import Image  # for BrainSprite

from layout_builder import layout_builder
from preprocessing import preprocess


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

        os.makedirs(html_path, exist_ok=True)

    else:
        print(f"Directory does not exist: {summary_path}")
        summary_path = None

    if html_path is not None:
        images_path = os.path.join(html_path, "img")
        os.makedirs(images_path, exist_ok=True)

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

    for index, file_ in enumerate(files):
        path = os.path.expanduser(file_)
        with Image.open(path) as img:
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


def preprocess_tx(tx, images_path):
    """If there are pngs for tx, make the mosaic file for the brainsprite.

    If not, no problem. Layout will use the mosaic if it is there.
    """
    pngs_dir = os.path.join(images_path, f"{tx}_pngs")

    if os.path.isdir(pngs_dir):
        # Call the program to make the mosaic from the pngs. and write
        mosaic_path = os.path.join(images_path, f"{tx}_mosaic.jpg")
        make_mosaic(pngs_dir, mosaic_path)
    else:
        print(f"There is no path: {pngs_dir}.")


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
        )

        # Make mosaic(s) for brainsprite(s).
        print("Making mosaic for T1 BrainSprite.")
        preprocess_tx("T1", images_path)
        print("Making mosaic for T2 BrainSprite.")
        preprocess_tx("T2", images_path)
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
