import os
from itertools import groupby
from operator import attrgetter

from ada.core.utils import NewLine, bool2text
from ada.fem.io import _folder_prep
from ada.fem.io.utils import get_fem_model_from_assembly

from ..abaqus.writer import (
    AbaqusWriter,
    AbaSection,
    AbaStep,
    _aba_bc_map,
    _valid_aba_bcs,
)
from .execute import run_calculix

main_header_str = """*Heading
** Generated by: {username}
** Assembly For Design and Analysis (ADA) FEM IO (Calculix)
"""


def to_fem(
    assembly,
    name,
    scratch_dir=None,
    description=None,
    execute=False,
    run_ext=False,
    cpus=2,
    gpus=None,
    overwrite=False,
    exit_on_complete=True,
):
    """
    Write a Calculix input file stack

    :param assembly:
    :param name:
    :param scratch_dir:
    :param description:
    :param execute:
    :param run_ext:
    :param cpus:
    :param gpus:
    :param overwrite:
    :param exit_on_complete:
    :return:
    """
    analysis_dir = _folder_prep(scratch_dir, name, overwrite)
    inp_file = (analysis_dir / name).with_suffix(".inp")

    p = get_fem_model_from_assembly(assembly)

    with open(inp_file, "w") as f:
        # Header
        f.write(main_header_str.format(username=os.getlogin()))

        # Part level information
        f.write(nodes_str(p.fem.nodes) + "\n")
        f.write(elements_str(p.fem.elements) + "\n")
        f.write(elsets_str(p.fem.elsets) + "\n")
        f.write(elsets_str(assembly.fem.elsets) + "\n")
        f.write(nsets_str(p.fem.nsets) + "\n")
        f.write(nsets_str(assembly.fem.nsets) + "\n")
        f.write(solid_sec_str(p) + "\n")
        f.write(shell_sec_str(p) + "\n")
        f.write(beam_sec_str(p) + "\n")

        # Assembly Level information
        f.write("\n".join([material_str(mat) for mat in p.materials]) + "\n")
        f.write("\n".join([bc_str(x) for x in p.fem.bcs + assembly.fem.bcs]) + "\n")
        f.write(step_str(assembly.fem.steps[0]))
        # f.write(mass_str)
        # f.write(surfaces_str)
        # f.write(constraints_str)
        # f.write(springs_str)

    print(f'Created a Calculix input deck at "{analysis_dir}"')
    # Create run batch files and if execute=True run the analysis
    if execute:
        run_calculix(
            (analysis_dir / name).with_suffix(".inp"),
            cpus=cpus,
            gpus=gpus,
            run_ext=run_ext,
            manifest=assembly.metadata,
            execute=execute,
            exit_on_complete=exit_on_complete,
        )


class CcxSection(AbaSection):
    def __init__(self, origin, fem_writer):
        super().__init__(origin, fem_writer)

    @property
    def section_data(self):
        if "section_type" in self._metadata.keys():
            return self._metadata["section_type"]
        from ada.sections import SectionCat

        if self.section.type in SectionCat.circular:
            self.section.properties.calculate()
            return "GENERAL"
        elif self.section.type in SectionCat.igirders or self.section.type in SectionCat.iprofiles:
            self.section.properties.calculate()
            return "GENERAL"
        elif self.section.type in SectionCat.box:
            return "BOX"
        elif self.section.type in SectionCat.general:
            return "GENERAL"
        elif self.section.type in SectionCat.tubular:
            self.section.properties.calculate()
            return "PIPE"
        elif self.section.type in SectionCat.angular:
            self.section.properties.calculate()
            return "GENERAL"
        else:
            raise Exception('section type "{sec_type}" is not added to AbaBeam yet'.format(sec_type=self.section.type))

    @property
    def beam_str(self):
        """
        BOX, CIRC, HEX, I, L, PIPE, RECT, THICK PIPE, and TRAPEZOID sections
        https://abaqus-docs.mit.edu/2017/English/SIMACAEKEYRefMap/simakey-r-beamsection.htm


        General Section
        https://abaqus-docs.mit.edu/2017/English/SIMACAEKEYRefMap/simakey-r-beamgeneralsection.htm#simakey-r-beamgeneralsection__simakey-r-beamgeneralsection-s-datadesc1


        Comment regarding Rotary Inertia and Explicit analysis
        https://abaqus-docs.mit.edu/2017/English/SIMACAEELMRefMap/simaelm-c-beamsectionbehavior.htm#hj-top

        """
        top_line = f"** Section: {self.elset.name}  Profile: {self.elset.name}"
        n1 = ", ".join(str(x) for x in self.local_y)
        ass = self.parent.parent.get_assembly()
        rotary_str = ""
        if len(ass.fem.steps) > 0:
            initial_step = ass.fem.steps[0]
            if initial_step.type == "explicit":
                rotary_str = ", ROTARY INERTIA=ISOTROPIC"

        if self.section_data != "GENERAL":
            return f"""{top_line}
*Beam Section, elset={self.elset.name}, material={self.material.name}, section={self.section_data}{rotary_str}
 {self.props}"""
        elif self.section_data == "PIPE":
            return f"{self.section.r}, {self.section.wt}\n {n1}"
        else:
            return f"""{top_line}
*Beam Section, elset={self.elset.name}, material={self.material.name},  section=GENERAL{rotary_str}
 {self.props}"""


def step_str(step):
    """

    :param step:
    :type step: ada.fem.Step
    :return:
    """

    bcstr = "\n".join([bc_str(bc) for bc in step.bcs.values()]) if len(step.bcs) > 0 else "** No BCs"
    lstr = "\n".join([load_str(l) for l in step.loads]) if len(step.loads) > 0 else "** No Loads"

    int_str = (
        "\n".join([interactions_str(interact) for interact in step.interactions.values()])
        if len(step.interactions.values()) > 0
        else "** No Interactions"
    )

    nodal = []
    elem = []
    for fi in step.field_outputs:
        nodal += fi.nodal
        elem += fi.element
    nodal_str = "*node file\n" + ", ".join(nodal) if len(nodal) > 0 else "** No nodal output"
    elem_str = "*el file\n" + ", ".join(elem) if len(elem) > 0 else "** No elem output"

    return f"""**
** STEP: {step.name}
**
*Step, nlgeom={bool2text(step.nl_geom)}, inc={step.total_incr}
*Static
 {step.init_incr}, {step.total_time}, {step.min_incr}, {step.max_incr}
**
** BOUNDARY CONDITIONS
**
{bcstr}
**
** LOADS
**
{lstr}
**
** INTERACTIONS
**
{int_str}
**
** OUTPUT REQUESTS
**
{nodal_str}
{elem_str}
*End Step"""


def nodes_str(fem_nodes):
    f = "{nid:>7}, {x:>13}, {y:>13}, {z:>13}"
    return (
        "*NODE\n"
        + "\n".join(
            [f.format(nid=no.id, x=no[0], y=no[1], z=no[2]) for no in sorted(fem_nodes, key=attrgetter("id"))]
        ).rstrip()
        if len(fem_nodes) > 0
        else "** No Nodes"
    )


def elements_str(fem_elements):
    """

    :param fem_elements:
    :return:
    """

    def aba_write(el):
        """

        :type el: ada.fem.Elem
        """
        nl = NewLine(10, suffix=7 * " ")
        if len(el.nodes) > 6:
            di = " {}"
        else:
            di = "{:>13}"
        return f"{el.id:>7}, " + " ".join([f"{di.format(no.id)}," + next(nl) for no in el.nodes])[:-1]

    def elwriter(eltype_set, elements):
        if "connector" in eltype_set:
            return None
        eltype, elset = eltype_set
        el_set_str = f", ELSET={elset.name}" if elset is not None else ""
        el_str = "\n".join(map(aba_write, elements))
        return f"""*ELEMENT, type={eltype}{el_set_str}\n{el_str}\n"""

    return (
        "".join(
            filter(
                None,
                [elwriter(x, elements) for x, elements in groupby(fem_elements, key=attrgetter("type", "elset"))],
            )
        ).rstrip()
        if len(fem_elements) > 0
        else "** No elements"
    )


def gen_set_str(fem_set):
    if len(fem_set.members) == 0:
        if "generate" in fem_set.metadata.keys():
            if fem_set.metadata["generate"] is False:
                raise ValueError(f'set "{fem_set.name}" is empty. Please check your input')
        else:
            raise ValueError("No Members are found")

    generate = fem_set.metadata.get("generate", False)
    internal = fem_set.metadata.get("internal", False)
    newline = NewLine(15)

    el_str = "*Elset, elset" if fem_set.type == "elset" else "*Nset, nset"

    el_instances = dict()

    for p, mem in groupby(fem_set.members, key=attrgetter("parent")):
        el_instances[p.name] = list(mem)

    # for mem in self.members:
    #     if mem.parent.name not in el_instances.keys():
    #         el_instances[mem.parent.name] = []
    #     if mem not in el_instances[mem.parent.name]:
    #         el_instances[mem.parent.name].append(mem)

    set_str = ""
    for elinst, members in el_instances.items():
        el_root = f"{el_str}={fem_set.name}"
        if internal is True and type(fem_set._fem_writer) in (
            AbaqusWriter,
            AbaStep,
        ):
            el_root += "" if "," in el_str[-2] else ", "
            el_root += "internal"

        if generate:
            assert len(fem_set.metadata["gen_mem"]) == 3
            el_root += "" if "," in el_root[-2] else ", "
            set_str += (
                el_root + "generate\n {},  {},   {}" "".format(*[no for no in fem_set.metadata["gen_mem"]]) + "\n"
            )
        else:
            set_str += el_root + "\n " + " ".join([f"{no.id}," + next(newline) for no in members]).rstrip()[:-1] + "\n"
    return set_str.rstrip()


def elsets_str(fem_elsets):
    if len(fem_elsets) > 0:
        return "\n".join([gen_set_str(el) for el in fem_elsets.values()]).rstrip()
    else:
        return "** No element sets"


def nsets_str(fem_nsets):
    return (
        "\n".join([gen_set_str(no) for no in fem_nsets.values()]).rstrip() if len(fem_nsets) > 0 else "** No node sets"
    )


def solid_sec_str(part):
    solid_secs = [AbaSection(sec, part).str for sec in part.fem.sections.solids]
    return "\n".join(solid_secs).rstrip() if len(solid_secs) > 0 else "** No solid sections"


def shell_sec_str(part):
    shell_secs = [AbaSection(sec, part).str for sec in part.fem.sections.shells]
    return "\n".join(shell_secs).rstrip() if len(shell_secs) > 0 else "** No shell sections"


def beam_sec_str(part):
    beam_secs = [CcxSection(sec, part).str for sec in part.fem.sections.beams]
    return "\n".join(beam_secs).rstrip() if len(beam_secs) > 0 else "** No beam sections"


def material_str(material):
    if "aba_inp" in material.metadata.keys():
        return material.metadata["aba_inp"]
    if "rayleigh_damping" in material.metadata.keys():
        alpha, beta = material.metadata["rayleigh_damping"]
    else:
        alpha, beta = None, None

    no_compression = material._metadata["no_compression"] if "no_compression" in material._metadata.keys() else False
    compr_str = "\n*No Compression" if no_compression is True else ""

    if material.model.eps_p is not None and len(material.model.eps_p) != 0:
        pl_str = "\n*Plastic\n"
        pl_str += "\n".join(
            ["{x:>12.5E}, {y:>10}".format(x=x, y=y) for x, y in zip(material.model.sig_p, material.model.eps_p)]
        )
    else:
        pl_str = ""

    if alpha is not None and beta is not None:
        d_str = "\n*Damping, alpha={alpha}, beta={beta}".format(alpha=material.model.alpha, beta=material.model.beta)
    else:
        d_str = ""

    if material.model.zeta is not None and material.model.zeta != 0.0:
        exp_str = "\n*Expansion\n {zeta}".format(zeta=material.model.zeta)
    else:
        exp_str = ""

    return f"""*Material, name={material.name}
*Elastic
 {material.model.E:.6E},  {material.model.v}{compr_str}
*Density
 {material.model.rho},{exp_str}{d_str}{pl_str}"""


def bc_str(bc):
    """

    :param bc:
    :type bc: ada.fem.Bc
    :return:
    """
    ampl_ref_str = "" if bc.amplitude_name is None else ", amplitude=" + bc.amplitude_name

    if bc.type in _valid_aba_bcs:
        aba_type = bc.type
    else:
        aba_type = _aba_bc_map[bc.type]

    dofs_str = ""
    for dof, magn in zip(bc.dofs, bc.magnitudes):
        if dof is None:
            continue
        # magn_str = f", {magn:.4f}" if magn is not None else ""

        if bc.type in ["connector displacement", "connector velocity"] or type(dof) is str:
            inst_name = bc.fem_set.name
            dofs_str += f" {inst_name}, {dof}\n"
        else:
            inst_name = bc.fem_set.name
            dofs_str += f" {inst_name}, {dof}\n"

    dofs_str = dofs_str.rstrip()

    if bc.type == "connector displacement":
        bc_str = "*Connector Motion"
        add_str = ", type=DISPLACEMENT"
    elif bc.type == "connector velocity":
        bc_str = "*Connector Motion"
        add_str = ", type=VELOCITY"
    else:
        bc_str = "*Boundary"
        add_str = ""

    return f"""** Name: {bc.name} Type: {aba_type}
{bc_str}{ampl_ref_str}{add_str}
{dofs_str}"""


def load_str(load):
    """

    :param load:
    :type load: ada.fem.Load
    :return:
    """
    dof = [0, 0, 1] if load.dof is None else load.dof
    if load.fem_set is None:
        raise ValueError("Calculix does not accept Loads without reference to a fem_set")

    fem_set = load.fem_set.name
    return f"""** Name: gravity   Type: Gravity
*Dload
{fem_set}, GRAV, {load.magnitude}, {', '.join([str(x) for x in dof[:3]])}"""


def surface_str(surface):
    """

    :param surface:
    :type surface: ada.fem.Surface
    :return:
    """
    top_line = f"*Surface, type={surface.type}, name={surface.name}"
    id_refs_str = "\n".join([f"{m[0]}, {m[1]}" for m in surface.id_refs]).strip()
    if surface.id_refs is None:
        if surface.type == "NODE":
            add_str = surface.weight_factor
        else:
            add_str = surface.face_id_label
        if surface.fem_set.name in surface.parent.elsets.keys():
            return f"{top_line}\n{surface.fem_set.name}, {add_str}"
        else:
            return f"""{top_line}
{surface.fem_set.name}, {add_str}"""
    else:
        return f"""{top_line}
{id_refs_str}"""


def interactions_str(interaction):
    """

    :param interaction:
    :type interaction: ada.fem.Interaction
    :return:
    """
    from ada.fem import Step

    if interaction.type == "SURFACE":
        adjust_par = interaction.metadata.get("adjust", None)
        geometric_correction = interaction.metadata.get("geometric_correction", None)
        small_sliding = interaction.metadata.get("small_sliding", None)

        stpstr = f"*Contact Pair, interaction={interaction.interaction_property.name}"

        if small_sliding is not None:
            stpstr += f", {small_sliding}"

        if type(interaction.parent) is Step:
            step = interaction.parent
            assert isinstance(step, Step)
            stpstr += "" if "explicit" in step.type else f", type={interaction.surface_type}"
        else:
            stpstr += f", type={interaction.surface_type}"

        if interaction.constraint is not None:
            stpstr += f", mechanical constraint={interaction.constraint}"

        if adjust_par is not None:
            stpstr += f", adjust={adjust_par}" if adjust_par is not None else ""

        if geometric_correction is not None:
            stpstr += f", geometric correction={geometric_correction}"

        stpstr += f"\n{interaction.surf1.name}, {interaction.surf2.name}"
    else:
        raise NotImplementedError(f'type "{interaction.type}"')

    return f"""**
** Interaction: {interaction.name}
{stpstr}"""
