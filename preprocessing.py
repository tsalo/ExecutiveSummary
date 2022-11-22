"""Functions translated from the bash code."""
import glob
import gzip
import os
import shutil

import nibabel as nib
# from nilearn.image import binarize_img
from nipype.interfaces import fsl

from interfaces import PNGAppend, ShowScene, SlicesDir


def binarize_img(f):
    """Binarize a niimg.

    TODO: Replace with nilearn.image.binarize_img when I have 0.9.2+ in Docker image.
    """
    img = nib.load(f)
    data = img.get_fdata()
    data = data.astype(bool).astype(int)
    new_img = nib.Nifti1Image(data, img.affine, img.header)
    return new_img


def build_scene_from_pngs_template(
    t2_path,
    t1_path,
    rp_path,
    lp_path,
    rw_path,
    lw_path,
    pngs_scene,
    pngs_template,
):
    """Create modified .scene text file to be used to create PNGs later.

    takes the following arguments: t2_path t1_path rp_path lp_path rw_path lw_path
    """
    paths = {
        "T2_IMG": t2_path,
        "T1_IMG": t1_path,
        "RPIAL": rp_path,
        "LPIAL": lp_path,
        "RWHITE": rw_path,
        "LWHITE": lw_path,
    }

    if pngs_template.endswith(".gz"):
        with gzip.open(pngs_template, mode="rt") as fo:
            data = fo.read()
    else:
        with open(pngs_template, "r") as fo:
            data = fo.read()

    for template, path in paths.items():
        # Replace templated pathnames and filenames in local copy.
        data = data.replace(f"{template}_PATH", path)
        filename = os.path.basename(path)
        data = data.replace(f"{template}_NAME", filename)

    with open(pngs_scene, "w") as fo:
        fo.write(data)


def build_scene_from_brainsprite_template(
    tx_img,
    rp_path,
    lp_path,
    rw_path,
    lw_path,
    brainsprite_template,
    brainsprite_scene,
):
    """Create modified .scene text file to be used for creating PNGs later."""
    paths = {
        "TX_IMG": tx_img,
        "R_PIAL": rp_path,
        "L_PIAL": lp_path,
        "R_WHITE": rw_path,
        "L_WHITE": lw_path,
    }

    if brainsprite_template.endswith(".gz"):
        with gzip.open(brainsprite_template, mode="rt") as fo:
            data = fo.read()
    else:
        with open(brainsprite_template, "r") as fo:
            data = fo.read()

    for template, path in paths.items():
        # Replace templated pathnames and filenames in local copy.
        data = data.replace(f"{template}_NAME_and_PATH", path)
        filename = os.path.basename(path)
        data = data.replace(f"{template}_NAME", filename)

    with open(brainsprite_scene, "w") as fo:
        fo.write(data)


def create_images_from_brainsprite_scene(
    image_type,
    output_dir,
    brainsprite_scene,
):
    """Create a series of PNG files that will later be used in a brainsprite."""
    # bash code: total_frames=$( grep "SceneInfo Index=" ${brainsprite_scene} | wc -l )
    with open(brainsprite_scene, "r") as fo:
        data = fo.read()

    total_frames = data.count("SceneInfo Index=")
    pngs_out_dir = os.path.join(output_dir, f"{image_type}_pngs")
    os.makedirs(pngs_out_dir, exist_ok=True)

    for i in range(total_frames):
        out_file = os.path.join(pngs_out_dir, f"P_{image_type}_frame_{i}.png")

        show_scene = ShowScene(
            scene_file=brainsprite_scene,
            scene_name_or_number=i + 1,  # starts with 1
            out_file=out_file,
            image_width=900,
            image_height=800,
        )
        _ = show_scene.run()


def make_default_slices_row(base_img, out_png, work_dir, red_img=None):
    """Use the default slices made by slicesdir (.4, .5, and .6).

    It calls slicesdir, grabs the output png, and cleans up the
    subdirectory left by slicesdir (also called slicesdir).

    Note: everything must be "local" or we get horrible filenames.
    Also, this whole process makes a mess. So use the working directory.

    Notes
    -----
    TAYLOR: slicesdir is an FSL command that "takes in a list of images, and for each one,
    runs slicer to produce the same 9 default slicings as described above,
    combining them into a single GIF picture."

    See https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Miscvis
    """
    # TAYLOR: TODO: Figure out a way not to use FSL
    slicesdir = SlicesDir()
    slicesdir.inputs.in_files = [base_img]

    if red_img is not None:
        slicesdir.inputs.outline_image = red_img

    results = slicesdir.run(cwd=work_dir)
    img_png = results.outputs.out_files
    os.rename(img_png, out_png)
    return out_png


def preprocess(
    output_dir,
    html_path,
    subject_id,
    brainsprite_template,
    pngs_template,
    session_id=None,
    bids_input=None,
    atlas=None,
    skip_sprite=False,
):
    """Prepare data for executive summary.

    Parameters
    ----------
    output_dir : str
    html_path : str
    subject_id : str
    brainsprite_template : str
    pngs_template : str
    session_id : str or None, optional
        Default is None.
    bids_input : str or None, optional
        Default is None.
    atlas : str or None, optional
        Default is None.
    skip_sprite : bool, optional
        Default is False.
    """
    # SET UP ENVIRONMENT VARIABLES
    scriptdir = os.path.dirname(__file__)
    templatedir = os.path.join(scriptdir, "templates")

    # Use the command line args to set up the requied paths
    if not os.path.isdir(output_dir):
        raise Exception(f"Directory does not exist: {output_dir}")

    # Template subfolders is defined in setup_env.sh
    # Seems to be location of all MNI-space preprocessed derivatives
    atlas_space_path = os.path.join(output_dir, "MNINonLinear")
    results_path = os.path.join(atlas_space_path, "Results")
    rois_path = os.path.join(atlas_space_path, "ROIs")

    if not atlas:
        print("Use default atlas")
        # Note: there is one of these in $FSLDIR/data/standard, but if differs. Why?
        atlas = os.path.join(templatedir, "MNI152_T1_1mm_brain.nii.gz")
    else:
        print(f"Use atlas: {atlas}")

    if html_path is None:
        # The summary directory was not supplied, write to the output-dir ('files').
        html_path = os.path.join(output_dir, "executivesummary")

    # The summary directory was supplied, but does not yet exist.
    os.makedirs(html_path, exist_ok=True)

    # Make the subfolder for the images. All paths in the html are relative to
    # the html folder, so must img must remain a subfolder to the html folder.

    # Lose old images.
    images_path = os.path.join(html_path, "img")
    if os.path.isdir(images_path):
        print("Remove images from prior runs.")
        if skip_sprite:
            # Cheat - keep the mosaics, and don't bother to log each file removed.
            # (For debug only.)
            # mv ${images_path}/*mosaic* ${html_path}
            # rm -f ${images_path}/*
            # mv ${html_path}/*mosaic* .
            pass
        else:
            for file_ in glob.glob(os.path.join(images_path, "*")):
                os.remove(file_)

    os.makedirs(images_path, exist_ok=True)

    # Sometimes need a "working directory"
    work_dir = os.path.join(html_path, "temp_files")
    os.makedirs(work_dir, exist_ok=True)

    print("START: executive summary image preprocessing")

    # Select input files
    # Standard-space images
    # NOTE: Why is t1_mask the same as t1_brain? Is it actually a mask?
    t1_mask = os.path.join(atlas_space_path, "T1w_restore_brain.nii.gz")
    t1 = os.path.join(atlas_space_path, "T1w_restore.nii.gz")
    t2 = os.path.join(atlas_space_path, "T2w_restore.nii.gz")
    rw = os.path.join(
        atlas_space_path,
        "fsaverage_LR32k",
        f"{subject_id}.R.white.32k_fs_LR.surf.gii",
    )
    rp = os.path.join(
        atlas_space_path,
        "fsaverage_LR32k",
        f"{subject_id}.R.pial.32k_fs_LR.surf.gii",
    )
    lw = os.path.join(
        atlas_space_path,
        "fsaverage_LR32k",
        f"{subject_id}.L.white.32k_fs_LR.surf.gii",
    )
    lp = os.path.join(
        atlas_space_path,
        "fsaverage_LR32k",
        f"{subject_id}.L.pial.32k_fs_LR.surf.gii",
    )
    t1_brain = os.path.join(atlas_space_path, "T1w_restore_brain.nii.gz")
    t2_brain = os.path.join(atlas_space_path, "T2w_restore_brain.nii.gz")

    # Subcorticals
    # Standard-space ROIs
    # TAYLOR: NOTE: This file is only created by the infant pipeline
    subcort_sub = os.path.join(rois_path, "sub2atl_ROI.2.nii.gz")
    subcort_atl = os.path.join(rois_path, "Atlas_ROIs.2.nii.gz")

    # Temporary files
    t1_2_brain = os.path.join(work_dir, "T1w_restore_brain.2.nii.gz")
    t2_2_brain = os.path.join(work_dir, "T2w_restore_brain.2.nii.gz")
    # Temporary modified scene file. Will be removed by end of workflow.
    pngs_scene = os.path.join(work_dir, "pngs_scene.scene")
    # Temporary modified scene file. Will be removed by end of workflow.
    t1w_brainsprite_scene = os.path.join(work_dir, "t1_bs_scene.scene")
    t2w_brainsprite_scene = os.path.join(work_dir, "t2_bs_scene.scene")

    if pngs_template is None:
        pngs_template = os.path.join(templatedir, "image_template_temp.scene.gz")

    if brainsprite_template is None:
        brainsprite_template = os.path.join(templatedir, "parasagittal_Tx_169_template.scene.gz")

    # Anat
    images_prefix = f"sub-{subject_id}"
    if session_id is not None:
        images_prefix += f"_ses-{session_id}"

    if atlas is None:
        # NOTE: Unreachable because atlas is already overwritten if not set.
        print(
            "The atlas argument was not supplied. Cannot create atlas-in-t1 or t1-in-atlas"
        )
    elif not os.path.isfile(atlas):
        print(f"Missing {atlas}")
        print("Cannot create atlas-in-t1 or t1-in-atlas")
    else:
        print(f"Registering {os.path.basename(t1_mask)} and atlas file: {atlas}")
        make_default_slices_row(
            t1_mask,
            os.path.join(images_path, f"{images_prefix}_desc-AtlasInT1w.gif"),
            work_dir=work_dir,
            red_img=atlas,
        )
        make_default_slices_row(
            atlas,
            os.path.join(images_path, f"{images_prefix}_desc-T1wInAtlas.gif"),
            work_dir=work_dir,
            red_img=t1_mask,
        )

    # From here on, use the whole T1 file rather than the mask (used above).
    if not os.path.isfile(t2):
        print("t2 not found; using t1")
        has_t2 = False

    if not os.path.isfile(t2_brain):
        print("t2_brain not found")

    # Make named pngs to show specific anatomical areas.
    build_scene_from_pngs_template(
        t2 if has_t2 else t1,
        t1,
        rp,
        lp,
        rw,
        lw,
        pngs_scene=pngs_scene,
        pngs_template=pngs_template,
    )

    image_names = [
        "T1-Axial-InferiorTemporal-Cerebellum",
        "T2-Axial-InferiorTemporal-Cerebellum",
        "T1-Axial-BasalGangila-Putamen",
        "T2-Axial-BasalGangila-Putamen",
        "T1-Axial-SuperiorFrontal",
        "T2-Axial-SuperiorFrontal",
        "T1-Coronal-PosteriorParietal-Lingual",
        "T2-Coronal-PosteriorParietal-Lingual",
        "T1-Coronal-Caudate-Amygdala",
        "T2-Coronal-Caudate-Amygdala",
        "T1-Coronal-OrbitoFrontal",
        "T2-Coronal-OrbitoFrontal",
        "T1-Sagittal-Insula-FrontoTemporal",
        "T2-Sagittal-Insula-FrontoTemporal",
        "T1-Sagittal-CorpusCallosum",
        "T2-Sagittal-CorpusCallosum",
        "T1-Sagittal-Insula-Temporal-HippocampalSulcus",
        "T2-Sagittal-Insula-Temporal-HippocampalSulcus",
    ]

    indexer = 1 if has_t2 else 2  # skip T2 images if T2 not available
    for i_scene, image_name in enumerate(image_names[::indexer]):
        show_scene = ShowScene(
            scene_file=pngs_scene,
            scene_name_or_number=i_scene + 1,
            out_file=os.path.join(images_path, f"{images_prefix}_{image_name}.png"),
            image_width=900,
            image_height=800,
        )
        _ = show_scene.run()

    os.remove(pngs_scene)

    # Make pngs to be used for the brainsprite.
    if skip_sprite:
        # Skip brainsprite processing.
        print("Skip brainsprite processing per user request.")

    elif not os.path.isfile(brainsprite_template):
        # Cannot do brainsprite processing if there is no template
        print(f"Missing {brainsprite_template}")
        print("Cannot perform processing needed for brainsprite.")

    else:
        # Create brainsprite images for T1
        build_scene_from_brainsprite_template(
            t1,
            rp,
            lp,
            rw,
            lw,
            brainsprite_template,
            t1w_brainsprite_scene,
        )
        create_images_from_brainsprite_scene("T1", images_path, t1w_brainsprite_scene)

        if has_t2:
            # Create brainsprite images for T2
            build_scene_from_brainsprite_template(
                t2,
                rp,
                lp,
                rw,
                lw,
                brainsprite_template,
                t2w_brainsprite_scene,
            )
            create_images_from_brainsprite_scene(
                "T2",
                images_path,
                t2w_brainsprite_scene,
            )

    if os.path.isfile(subcort_sub) and os.path.isfile(subcort_atl):
        # NOTE: Apparently this is only done for infant data.
        print("Create subcortical images.")

        # The default slices are not as nice for subcorticals as they are for a whole brain.
        # Pick out slices using slicer.
        subcort_sub_temp = os.path.join(work_dir, "subcort_sub.nii.gz")
        subcort_atl_temp = os.path.join(work_dir, "subcort_atl.nii.gz")

        shutil.copyfile(subcort_sub, subcort_sub_temp)
        shutil.copyfile(subcort_atl, subcort_atl_temp)

        # slices/slicer does not do well trying to make the red outline when it
        # cannot find the edges, so cannot use the ROI files with some low intensities.

        # Make a binarized copy of the subcortical atlas to be used for the outline.
        bin_atl = os.path.join(work_dir, "bin_subcort_atl.nii.gz")
        # bash code: fslmaths subcort_atl.nii.gz -bin ${bin_atl}
        bin_img = binarize_img(subcort_atl_temp)
        bin_img.to_filename(bin_atl)

        # Make a binarized copy of the subject's subcorticals to be used for the outline.
        bin_sub = bin_atl = os.path.join(work_dir, "bin_subcort_sub.nii.gz")
        # bash code: fslmaths subcort_sub.nii.gz -bin ${bin_sub}
        bin_img = binarize_img(subcort_sub_temp)
        bin_img.to_filename(bin_sub)

        # NOTE: These slices are almost certainly specific to a given MNI template and
        # resolution.
        slices_to_plot = {
            "x": [36, 45, 52],  # sagittal
            "y": [43, 54, 65],  # coronal
            "z": [23, 33, 39],  # axial
        }
        counter, atlas_in_subcort_pngs, subcort_in_atlas_pngs = 0, [], []
        for view, slice_numbers in slices_to_plot.items():
            for slice_number in slice_numbers:
                # Generate atlas in subcortical figure
                atlas_in_subcort_png = os.path.join(work_dir, f"slice_atl_{counter}.png")
                # TAYLOR: TODO: Figure out a way not to use FSL
                slicer_interface = fsl.Slicer(
                    in_file=subcort_sub_temp,
                    image_edges=bin_atl,
                    single_slice=view,
                    slice_number=slice_number,
                    out_file=atlas_in_subcort_png,
                    args="-u -L",
                )
                slicer_interface.run()
                atlas_in_subcort_pngs.append(atlas_in_subcort_png)

                # Generate subcortical in atlas figure
                subcort_in_atlas_png = os.path.join(work_dir, f"slice_sub_{counter}.png")
                # TAYLOR: TODO: Figure out a way not to use FSL
                slicer_interface = fsl.Slicer(
                    in_file=subcort_atl_temp,
                    image_edges=bin_sub,
                    single_slice=view,
                    slice_number=slice_number,
                    out_file=subcort_in_atlas_png,
                    args="-u -L",
                )
                slicer_interface.run()
                subcort_in_atlas_pngs.append(subcort_in_atlas_png)

                counter += 1

        append_atlas_in_subcort = PNGAppend(
            in_files=atlas_in_subcort_pngs,
            out_file=os.path.join(images_path, "{images_prefix}_desc-AtlasInSubcort.gif"),
        )
        append_atlas_in_subcort.run()

        append_subcort_in_atlas = PNGAppend(
            in_files=subcort_in_atlas_pngs,
            out_file=os.path.join(images_path, f"{images_prefix}_desc-SubcortInAtlas.gif"),
        )
        append_subcort_in_atlas.run()

    else:
        print(f"Missing {subcort_atl} or {subcort_sub}.")
        print("Cannot create atlas-in-subcort or subcort-in-atlas.")
        print("No subcorticals will be included.")

    # Make T1w and T2w task images.
    tasks = sorted(glob.glob(os.path.join(results_path, "*task-*")))
    tasks = [t for t in tasks if os.path.isdir(t)]
    for task in tasks:
        task_name = os.path.basename(task)
        print(f"Make images for {task_name}")
        # TAYLOR: NOTE: {task_name}.nii.gz does not exist, but maybe task-rest01_nonlin.nii.gz?
        task_img = os.path.join(results_path, task_name, f"{task_name}.nii.gz")
        assert os.path.isfile(task_img), f"{task_img} DNE"

        # Use the first task image to make the resampled brain.
        # TAYLOR: When you use apply_xfm but no matrix, I guess FLIRT just resamples the data.
        # TAYLOR: Seems like a confusing way to do it though.
        # TAYLOR: TODO: Replace with nilearn's resample_to_img
        flt = fsl.FLIRT()
        flt.inputs.in_file = t1_brain
        flt.inputs.reference = task_img
        flt.inputs.args = "-applyxfm"  # can't use .apply_xfm = True
        flt.inputs.out_file = t1_2_brain
        flt.run()

        if has_t2:
            # TAYLOR: TODO: Replace with nilearn's resample_to_img
            flt = fsl.FLIRT()
            flt.inputs.in_file = t2_brain
            flt.inputs.reference = task_img
            flt.inputs.args = "-applyxfm"  # can't use .apply_xfm = True
            flt.inputs.out_file = t2_2_brain
            flt.run()

        task_prefix = f"sub-{subject_id}_{task_name}"
        make_default_slices_row(
            task_img,
            os.path.join(images_path, f"{task_prefix}_desc-T1InTask.gif"),
            work_dir=work_dir,
            red_img=t1_2_brain,
        )
        make_default_slices_row(
            t1_2_brain,
            os.path.join(images_path, f"{task_prefix}_desc-TaskInT1.gif"),
            work_dir=work_dir,
            red_img=task_img,
        )
        if has_t2:
            make_default_slices_row(
                task_img,
                os.path.join(images_path, f"{task_prefix}_desc-T2InTask.gif"),
                work_dir=work_dir,
                red_img=t2_2_brain,
            )
            make_default_slices_row(
                t2_2_brain,
                os.path.join(images_path, f"{task_prefix}_desc-TaskInT2.gif"),
                work_dir=work_dir,
                red_img=task_img,
            )

    # If the bids-input was supplied and there are func files, slice
    # the bold and sbref_files into pngs so we can display them.
    if os.path.isdir(bids_input):
        # Slice bold.nii.gz files for tasks into pngs.
        # TAYLOR: What about boldref files?
        bold_files = sorted(glob.glob(os.path.join(bids_input, "*task-*_bold*.nii*")))
        for bold_file in bold_files:
            png_name = os.path.basename(bold_file)
            png_name = png_name.replace(".nii.gz", ".png")
            png_name = png_name.replace(".nii", ".png")
            png_file = os.path.join(images_path, png_name)
            # TAYLOR: TODO: Figure out a way not to use FSL
            slicer_interface = fsl.Slicer(
                in_file=bold_file,
                out_file=png_file,
                args="-u -a",
            )
            slicer_interface.run()

        # Slice sbref.nii.gz files for tasks into pngs.
        sbref_files = sorted(glob.glob(os.path.join(bids_input, "*task-*_sbref*.nii*")))

        if len(sbref_files) > 0:
            for sbref_file in sbref_files:
                png_name = os.path.basename(sbref_file)
                png_name = png_name.replace(".nii.gz", ".png")
                png_name = png_name.replace(".nii", ".png")
                png_file = os.path.join(images_path, png_name)
                # TAYLOR: TODO: Figure out a way not to use FSL
                slicer_interface = fsl.Slicer(
                    in_file=sbref_file,
                    out_file=png_file,
                    args="-u -a",
                )
                slicer_interface.run()

        else:
            # There are no SBRefs; use scout files for references.
            scout_files = sorted(
                glob.glob(os.path.join(output_dir, "task-*", "Scout_orig.nii.gz"))
            )
            for scout_file in scout_files:
                # Get the task name and number from the parent.
                task_name = os.path.basename(os.path.dirname(scout_file))
                png_name = f"sub-{subject_id}_{task_name}_ref.png"
                png_file = os.path.join(images_path, png_name)
                # TAYLOR: TODO: Figure out a way not to use FSL
                slicer_interface = fsl.Slicer(
                    in_file=scout_file,
                    out_file=png_file,
                    args="-u -a",
                )
                slicer_interface.run()

    else:
        print("No func files. Neither bold nor sbref will be shown.")
