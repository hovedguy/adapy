from dataclasses import dataclass


@dataclass
class AbaqusDefaultShellTypes:
    TRIANGLE = "S3"
    TRIANGLE6 = "STRI65"
    TRIANGLE7 = "S7"
    QUAD = "S4R"
    QUAD8 = "S8"


@dataclass
class AbaqusDefaultSolidTypes:
    HEXAHEDRON = "C3D8"
    HEXAHEDRON20 = "C3D20R"
    HEXAHEDRON27 = "C3D27"
    TETRA = "C3D4"
    TETRA10 = "C3D10"
    PYRAMID5 = "C3D5"
    PRISM6 = "C3D6"
    PRISM15 = "C3D15"


@dataclass
class AbaqusDefaultLineTypes:
    LINE = "B31"
    LINE3 = "B32"


class AbaqusDefaultElemTypes:
    LINE = AbaqusDefaultLineTypes()
    SHELL = AbaqusDefaultShellTypes()
    SOLID = AbaqusDefaultSolidTypes()

    def get_element_type(self, el_type: str) -> str:
        from ada.fem.shapes import ElemType
        from ada.fem.shapes.definitions import get_elem_type_group

        type_group = get_elem_type_group(el_type)

        type_map = {
            ElemType.LINE: self.LINE,
            ElemType.SHELL: self.SHELL,
            ElemType.SOLID: self.SOLID,
        }
        res = getattr(type_map[type_group], el_type, None)
        if res is None:
            raise ValueError(f'Unrecognized element type "{el_type}"')
        return res


class AbaqusPointTypes:
    spring1n = ["SPRING1"]
    masses = ["MASS", "ROTARYI"]

    all = [spring1n, masses]