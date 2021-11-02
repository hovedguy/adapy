from ada.fem import Surface

from .common import get_instance_name


def surface_str(surface: Surface, write_on_assembly_level: bool) -> str:
    """Surface assignments str"""
    top_line = f"*Surface, type={surface.type}, name={surface.name}"
    from ada.fem.elements import find_element_type_from_list
    from ada.fem.shapes import ElemType

    if surface.name == "SURF_2006_CNS_":
        print("sd")

    if surface.id_refs is not None:
        id_refs_str = "\n".join([f"{m[0]}, {m[1]}" for m in surface.id_refs]).strip()
        return f"""{top_line}\n{id_refs_str}"""

    if surface.type == surface.TYPES.NODE:
        elem_face_index_label = surface.weight_factor
    else:
        elem_face_index_label = surface.el_face_index

    fs_str = ""
    if not type(surface.fem_set) is list:
        f_sets = [surface.fem_set]
        el_face_indices = [elem_face_index_label]
    else:
        f_sets = surface.fem_set
        el_face_indices = elem_face_index_label

    for fs, el_f_index in zip(f_sets, el_face_indices):
        set_ref = get_instance_name(fs, write_on_assembly_level)

        if surface.type == surface.TYPES.NODE:
            fs_str += f"{set_ref}\n"
            continue
        el_type = find_element_type_from_list(fs.members)
        if el_type == ElemType.SOLID:
            fs_str += f"{set_ref}, S{el_f_index + 1}\n"
        elif el_type == ElemType.SHELL:
            face_str = "SNEG" if el_f_index == -1 else "SPOS"
            fs_str += f"{set_ref}, {face_str}\n"
        else:
            raise NotImplementedError()

    return f"""{top_line}\n{fs_str.strip()}"""
