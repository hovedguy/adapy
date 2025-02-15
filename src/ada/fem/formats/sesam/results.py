import logging
import os
import pathlib
from typing import List, Union

from ada.fem import StepEigen
from ada.fem.concepts.eigenvalue import EigenDataSummary, EigenMode
from ada.fem.formats.utils import DatFormatReader
from ada.fem.results import Results


def get_eigen_data(dat_file: Union[str, os.PathLike]) -> EigenDataSummary:
    dtr = DatFormatReader()

    re_compiled = dtr.compile_ff_re([int] + [float] * 3, separator=";")

    eig_str = "printofeigenvalues"
    eig_res = dtr.read_data_lines(dat_file, re_compiled, eig_str, split_data=True)
    eigen_modes: List[EigenMode] = []

    # Note! participation factors and effective modal mass are each deconstructed into 6 degrees of freedom
    for mode, eig_value, eig_freq, period in eig_res:
        eig_output = dict(
            eigenvalue=eig_value.replace(";", ""),
            f_hz=eig_freq.replace(";", ""),
        )
        eigen_modes.append(EigenMode(no=mode.replace(";", ""), **eig_output))

    return EigenDataSummary(eigen_modes)


def read_sesam_results(results: Results, file_ref: pathlib.Path, overwrite):
    dat_file = (file_ref.parent / "SESTRA").with_suffix(".LIS")
    if dat_file.exists() and type(results.assembly.fem.steps[0]) == StepEigen:
        results.eigen_mode_data = get_eigen_data(dat_file)

    logging.error("Result mesh data extraction is not supported for sesam")
    return None
