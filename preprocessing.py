"""Functions translated from the bash code."""
import glob
import os
import shutil

from nilearn.image import binarize_img
from nipype.interfaces import fsl

from interfaces import PNGAppend, ShowScene, SlicesDir


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
    """Build template scene from PNG files.

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
    paths = {
        "TX_IMG": tx_img,
        "R_PIAL": rp_path,
        "L_PIAL": lp_path,
        "R_WHITE": rw_path,
        "L_WHITE": lw_path,
    }

    with open(brainsprite_template, "r") as fo:
        data = fo.read()

    for template, path in paths.items():
        # Replace templated pathnames and filenames in local copy.
        data = data.replace(f"{template}_NAME_and_PATH", path)
        filename = os.path.basename(path)
        data = data.replace(f"{template}_NAME", filename)

    with open(brainsprite_scene, "w") as fo:
        fo.write(data)


def create_images_from_brainsprite_scene(Tx, processed_files, brainsprite_scene):
    # bash code: total_frames=$( grep "SceneInfo Index=" ${brainsprite_scene} | wc -l )
    with open(brainsprite_scene, "r") as fo:
        data = fo.read()

    total_frames = data.count("SceneInfo Index=")

    for i in range(total_frames):
        out_file = os.path.join(processed_files, f"{Tx}_pngs", f"P_{Tx}_frame_{i}.png")

        show_scene = ShowScene(
            scene_file=brainsprite_scene,
            scene_name_or_number=i + 1,  # starts with 1
            out_file=out_file,
            image_width=900,
            image_height=800,
        )
        _ = show_scene.run()


def make_default_slices_row(base_img, out_png, working, red_img=None):
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
    slicesdir = SlicesDir(in_files=[base_img])

    if red_img is not None:
        slicesdir.inputs.outline_image = red_img

    results = slicesdir.run(cwd=working)
    img_png = results.outputs.out_files[0]
    return img_png


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
    # TAYLOR: SECTION 1
    # SET UP ENVIRONMENT VARIABLES
    scriptdir = os.path.dirname(__file__)
    templatedir = os.path.join(scriptdir, "templates")

    # Use the command line args to setup the requied paths
    processed_files = output_dir
    if not os.path.isdir(processed_files):
        raise Exception(f"Directory does not exist: {processed_files}")

    AtlasSpaceFolder = "MNINonLinear"  # defined in setup_env.sh
    AtlasSpacePath = os.path.join(processed_files, AtlasSpaceFolder)
    Results = os.path.join(AtlasSpacePath, "Results")
    ROIs = os.path.join(AtlasSpacePath, "ROIs")

    if not atlas:
        print("Use default atlas")
        # Note: there is one of these in $FSLDIR/data/standard, but if differs. Why?
        atlas = os.path.join(templatedir, "MNI152_T1_1mm_brain.nii.gz")
    else:
        print(f"Use atlas: {atlas}")

    if html_path is None:
        # The summary directory was not supplied, write to the output-dir ('files').
        html_path = os.path.join(processed_files, "executivesummary")

    if not os.path.isdir(html_path):
        # The summary directory was supplied, but does not yet exist.
        os.makedirs(html_path)

    # TAYLOR: SECTION 2
    # Make the subfolder for the images. All paths in the html are relative to
    # the html folder, so must img must remain a subfolder to the html folder.

    # Lose old images.
    images_path = os.path.join(html_path, "img")
    if not os.path.isdir(images_path):
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

    os.makedirs(images_path, exists_ok=True)
    if not os.path.isdir(images_path):
        raise Exception(f"Unable to write {images_path}. Permissions?")

    # Sometimes need a "working directory"
    working = os.path.join(html_path, "temp_files")
    os.makedirs(working, exists_ok=True)
    if not os.path.isdir(working):
        raise Exception(f"Unable to write {working}. Permissions?")

    # TAYLOR: END SECTION 2

    # TAYLOR: SECTION 3
    # TAYLOR: These don't get used?!
    # wm_mask_L = f"L_wm_2mm_{subject_id}_mask.nii.gz"
    # wm_mask_R = f"R_wm_2mm_{subject_id}_mask.nii.gz"
    # wm_mask = f"wm_2mm_{subject_id}_mask.nii.gz"
    # wm_mask_eroded = f"wm_2mm_{subject_id}_mask_erode.nii.gz"
    # vent_mask_L = f"L_vent_2mm_{subject_id}_mask.nii.gz"
    # vent_mask_R = f"R_vent_2mm_{subject_id}_mask.nii.gz"
    # vent_mask = f"vent_2mm_{subject_id}_mask.nii.gz"
    # vent_mask_eroded = f"vent_2mm_{subject_id}_mask_eroded.nii.gz"

    print("START: executive summary image preprocessing")

    # Anat
    images_pre = os.path.join(images_path, f"sub-{subject_id}")
    if session_id is not None:
        images_pre += f"_ses-{session_id}"

    # TAYLOR: What is the t1_mask supposed to be? The file isn't available...
    t1_mask = os.path.join(AtlasSpacePath, "T1w_restore_brain.nii.gz")

    if atlas is None:
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
            f"{images_pre}_desc-AtlasInT1w.gif",
            red_img=atlas,
        )
        make_default_slices_row(
            atlas,
            f"{images_pre}_desc-T1wInAtlas.gif",
            red_img=t1_mask,
        )

    # From here on, use the whole T1 file rather than the mask (used above).
    t1 = os.path.join(AtlasSpacePath, "T1w_restore.nii.gz")
    t2 = os.path.join(AtlasSpacePath, "T2w_restore.nii.gz")
    has_t2 = True
    if not os.path.isfile(t2):
        print("t2 not found; using t1")
        has_t2 = False
        t2 = t1

    rw = os.path.join(
        AtlasSpacePath,
        "fsaverage_LR32k",
        f"{subject_id}.R.white.32k_fs_LR.surf.gii",
    )
    rp = os.path.join(
        AtlasSpacePath,
        "fsaverage_LR32k",
        f"{subject_id}.R.pial.32k_fs_LR.surf.gii",
    )
    lw = os.path.join(
        AtlasSpacePath,
        "fsaverage_LR32k",
        f"{subject_id}.L.white.32k_fs_LR.surf.gii",
    )
    lp = os.path.join(
        AtlasSpacePath,
        "fsaverage_LR32k",
        f"{subject_id}.L.pial.32k_fs_LR.surf.gii",
    )
    t1_brain = os.path.join(AtlasSpacePath, "T1w_restore_brain.nii.gz")
    t2_brain = os.path.join(AtlasSpacePath, "T2w_restore_brain.nii.gz")
    if not os.path.isfile(t2_brain):
        print("t2_brain not found")

    # Make named pngs to show specific anatomical areas.
    if pngs_template is None:
        # Use default.
        pngs_template = os.path.join(templatedir, "image_template_temp.scene")

    pngs_scene = os.path.join(processed_files, "pngs_scene.scene")
    build_scene_from_pngs_template(
        t2,
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
            out_file=f"{images_pre}_{image_name}.png",
            image_width=900,
            image_height=800,
        )
        _ = show_scene.run()

    os.remove(pngs_scene)

    # TAYLOR: SECTION 4
    # Make pngs to be used for the brainsprite.
    if brainsprite_template is None:
        # Use default.
        brainsprite_template = os.path.join(
            templatedir, "parasagittal_Tx_169_template.scene"
        )

    if skip_sprite:
        # Skip brainsprite processing.
        print("Skip brainsprite processing per user request.")

    elif not os.path.isfile(brainsprite_template):
        # Cannot do brainsprite processing if there is no template
        print(f"Missing {brainsprite_template}")
        print("Cannot perform processing needed for brainsprite.")

    else:
        os.makedirs(os.path.join(processed_files, "T1_pngs"))

        # Create brainsprite images for T1
        brainsprite_scene = os.path.join(processed_files, "t1_bs_scene.scene")
        build_scene_from_brainsprite_template(
            t1,
            rp,
            lp,
            rw,
            lw,
            brainsprite_template,
            brainsprite_scene,
        )
        create_images_from_brainsprite_scene("T1", processed_files, brainsprite_scene)

        if has_t2:
            os.makedirs(os.path.join(processed_files, "T2_pngs"))

            # Create brainsprite images for T2
            brainsprite_scene = os.path.join(processed_files, "t2_bs_scene.scene")
            build_scene_from_brainsprite_template(
                t2,
                rp,
                lp,
                rw,
                lw,
                brainsprite_template,
                brainsprite_scene,
            )
            create_images_from_brainsprite_scene("T2", processed_files, brainsprite_scene)

    # TAYLOR: SECTION 5
    # Subcorticals
    subcort_sub = os.path.join(ROIs, "sub2atl_ROI.2.nii.gz")
    subcort_atl = os.path.join(ROIs, "Atlas_ROIs.2.nii.gz")
    # set -x
    if not os.path.isfile(subcort_sub):
        if not os.path.join(subcort_atl):
            print("Create subcortical images.")

            # The default slices are not as nice for subcorticals as they are for a whole brain.
            # Pick out slices using slicer.

            # pushd ${working}
            shutil.copyfile(subcort_sub, "subcort_sub.nii.gz")
            shutil.copyfile(subcort_atl, "subcort_atl.nii.gz")

            prefix = "slice_"

            # slices/slicer does not do well trying to make the red outline when it
            # cannot find the edges, so cannot use the ROI files with some low intensities.

            # Make a binarized copy of the subcortical atlas to be used for the outline.
            bin_atl = "bin_subcort_atl.nii.gz"
            # fslmaths subcort_atl.nii.gz -bin ${bin_atl}
            bin_img = binarize_img("subcort_atl.nii.gz")
            bin_img.to_filename(bin_atl)

            # Make a binarized copy of the subject's subcorticals to be used for the outline.
            bin_sub = "bin_subcort_sub.nii.gz"
            # fslmaths subcort_sub.nii.gz -bin ${bin_sub}
            bin_img = binarize_img("subcort_sub.nii.gz")
            bin_img.to_filename(bin_sub)

            SLICES = {
                "x": [36, 45, 52],  # sagittal
                "y": [43, 54, 65],  # coronal
                "z": [23, 33, 39],  # axial
            }
            counter, atlas_in_subcort_pngs, subcort_in_atlas_pngs = 0, [], []
            for view, slice_numbers in SLICES.items():
                for slice_number in slice_numbers:
                    # Generate atlas in subcortical figure
                    atlas_in_subcort_png = f"{prefix}_atl_{counter}.png"
                    # TAYLOR: TODO: Figure out a way not to use FSL
                    slicer_interface = fsl.Slicer(
                        in_file="subcort_sub.nii.gz",
                        image_edges=bin_atl,
                        single_slice=view,
                        slice_number=slice_number,
                        out_file=atlas_in_subcort_png,
                        args="-u -L",
                    )
                    slicer_interface.run()
                    atlas_in_subcort_pngs.append(atlas_in_subcort_png)

                    # Generate subcortical in atlas figure
                    subcort_in_atlas_png = f"{prefix}_sub_{counter}.png"
                    # TAYLOR: TODO: Figure out a way not to use FSL
                    slicer_interface = fsl.Slicer(
                        in_file="subcort_atl.nii.gz",
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
                out_file=os.path.join(working, f"{images_pre}_desc-AtlasInSubcort.gif"),
            )
            append_atlas_in_subcort.run()

            append_subcort_in_atlas = PNGAppend(
                in_files=subcort_in_atlas_pngs,
                out_file=os.path.join(working, f"{images_pre}_desc-SubcortInAtlas.gif"),
            )
            append_subcort_in_atlas.run()

        else:
            print(f"Missing {subcort_atl}.")
            print("Cannot create atlas-in-subcort or subcort-in-atlas.")
    else:
        print(f"Missing {subcort_sub}.")
        print("No subcorticals will be included.")

    # TAYLOR: SECTION 6
    # Tasks
    t1_2_brain = os.path.join(AtlasSpacePath, "T1w_restore_brain.2.nii.gz")
    t2_2_brain = os.path.join(AtlasSpacePath, "T2w_restore_brain.2.nii.gz")
    if not os.path.isfile(t2_2_brain):
        print("t2_2_brain not found")

    t1_2_brain_img = ""  # TAYLOR: Added bc these variables aren't defined
    if os.path.isfile(t1_2_brain_img):
        print("removing old resampled t1 brain")
        os.remove(t1_2_brain_img)

    t2_2_brain_img = ""  # TAYLOR: Added bc these variables aren't defined
    if os.path.isfile(t2_2_brain_img):
        print("removing old resampled t2 brain")
        os.remove(t2_2_brain_img)

    # Make T1w and T2w task images.
    tasks = sorted(glob.glob(os.path.join(Results, "*task-*")))
    tasks = [t for t in tasks if os.path.isdir(t)]
    for task in tasks:
        fMRIName = os.path.basename(task)
        print(f"Make images for {fMRIName}")
        task_img = os.path.join(Results, fMRIName, f"{fMRIName}.nii.gz")

        # Use the first task image to make the resampled brain.
        # TAYLOR: TODO: Replace with ANTS' ApplyTransforms
        flt = fsl.FLIRT()
        flt.inputs.in_file = t1_brain
        flt.inputs.reference = task_img
        flt.inputs.apply_xfm = True
        flt.inputs.out_file = t1_2_brain
        flt.run()

        if has_t2:
            # TAYLOR: TODO: Replace with ANTS' ApplyTransforms
            flt = fsl.FLIRT()
            flt.inputs.in_file = t2_brain
            flt.inputs.reference = task_img
            flt.inputs.apply_xfm = True
            flt.inputs.out_file = t2_2_brain
            flt.run()

        fMRI_pre = os.path.join(images_path, f"sub-{subject_id}_{fMRIName}")
        make_default_slices_row(
            task_img,
            f"{fMRI_pre}_desc-T1InTask.gif",
            red_img=t1_2_brain,
        )
        make_default_slices_row(
            t1_2_brain,
            f"{fMRI_pre}_desc-TaskInT1.gif",
            red_img=task_img,
        )
        if has_t2:
            make_default_slices_row(
                task_img,
                f"{fMRI_pre}_desc-T2InTask.gif",
                red_img=t2_2_brain,
            )
            make_default_slices_row(
                t2_2_brain,
                f"{fMRI_pre}_desc-TaskInT2.gif",
                red_img=task_img,
            )

    # TAYLOR: SECTION 7
    # If the bids-input was supplied and there are func files, slice
    # the bold and sbref_files into pngs so we can display them.
    # shopt -s nullglob
    if os.path.isdir(bids_input):
        # Slice bold.nii.gz files for tasks into pngs.
        bold_files = sorted(glob.glob(os.path.join(bids_input, "*task-*_bold*.nii*")))
        for bold_file in bold_files:
            png_name = os.path.basename(bold_file)
            png_name = png_name.replace(".nii.gz", ".png")
            png_name = png_name.replace(".nii", ".png")
            # TAYLOR: TODO: Figure out a way not to use FSL
            slicer_interface = fsl.Slicer(
                in_file=bold_file,
                out_file=os.path.join(images_path, png_name),
                args="-u -a",
            )
            slicer_interface.run()

        # Slice sbref.nii.gz files for tasks into pngs.
        sbref_files = sorted(glob.glob(os.path.join(bids_input, "*task-*_sbref*.nii*")))

        if len(sbref_files) == 0:
            # There are no SBRefs; use scout files for references.
            scout_files = sorted(
                glob.glob(os.path.join(processed_files, "task-*", "Scout_orig.nii.gz"))
            )
            for scout_file in scout_files:
                # Get the task name and number from the parent.
                task_name = os.path.basename(os.path.dirname(scout_file))
                png_name = f"sub-{subject_id}_{task_name}_ref.png"
                # TAYLOR: TODO: Figure out a way not to use FSL
                slicer_interface = fsl.Slicer(
                    in_file=scout_file,
                    out_file=os.path.join(images_path, png_name),
                    args="-u -a",
                )
                slicer_interface.run()

        else:
            for sbref_file in sbref_files:
                png_name = os.path.basename(sbref_file)
                png_name = png_name.replace(".nii.gz", ".png")
                png_name = png_name.replace(".nii", ".png")
                # TAYLOR: TODO: Figure out a way not to use FSL
                slicer_interface = fsl.Slicer(
                    in_file=sbref_file,
                    out_file=os.path.join(images_path, png_name),
                    args="-u -a",
                )
                slicer_interface.run()

    else:
        print("No func files. Neither bold nor sbref will be shown.")

    # shopt -u nullglob
