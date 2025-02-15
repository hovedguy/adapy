from __future__ import annotations

import logging
import reprlib
from bisect import bisect_left, bisect_right
from itertools import chain
from operator import attrgetter
from typing import Dict, Iterable, List, Union

import numpy as np
import toolz

from ada.config import Settings
from ada.core.utils import Counter, points_in_cylinder, roundoff, vector_length
from ada.materials import Material

from .points import Node
from .structural import Beam, Plate, Section
from .transforms import Rotation

__all__ = [
    "Nodes",
    "Beams",
    "Plates",
    "Connections",
    "Materials",
    "Sections",
]


class BaseCollections:
    """
    The Base class for all collections

    :param parent:
    """

    def __init__(self, parent):
        self._parent = parent

    @property
    def parent(self):
        """:rtype: ada.Part"""
        return self._parent


class Beams(BaseCollections):
    """A collections of Beam objects"""

    def __init__(self, beams: Iterable[Beam] = None, unique_ids=True, parent=None):

        super().__init__(parent)
        beams = [] if beams is None else beams
        if unique_ids:
            beams = toolz.unique(beams, key=attrgetter("name"))
        self._beams = sorted(beams, key=attrgetter("name"))
        self._dmap = {n.name: n for n in self._beams}

    def __contains__(self, item):
        return item.guid in self._dmap.keys()

    def __len__(self):
        return len(self._beams)

    def __iter__(self) -> Iterable[Beam]:
        return iter(self._beams)

    def __getitem__(self, index):
        result = self._beams[index]
        return Beams(result) if isinstance(index, slice) else result

    def __eq__(self, other):
        if not isinstance(other, Beams):
            return NotImplemented
        return self._beams == other._beams

    def __ne__(self, other):
        if not isinstance(other, Beams):
            return NotImplemented
        return self._beams != other._beams

    def __add__(self, other):
        return Beams(chain(self, other))

    def __repr__(self):
        rpr = reprlib.Repr()
        rpr.maxlist = 8
        rpr.maxlevel = 1
        return f"Beams({rpr.repr(self._beams) if self._beams else ''})"

    def index(self, item):
        index = bisect_left(self._beams, item)
        if (index != len(self._beams)) and (self._beams[index] == item):
            return index
        raise ValueError(f"{repr(item)} not found")

    def count(self, item):
        return int(item in self)

    def from_name(self, name: str) -> Beam:
        """Get beam from its name"""
        if name not in self._dmap.keys():
            raise ValueError(f'The beam "{name}" is not found')
        else:
            return self._dmap[name]

    def add(self, beam: Beam) -> Beam:
        if beam.name is None:
            raise Exception("Name is not allowed to be None.")

        if beam.name in self._dmap.keys():
            logging.warning(f'Beam with name "{beam.name}" already exists. Will not add')
            return self._dmap[beam.name]
        self._dmap[beam.name] = beam
        self._beams.append(beam)
        return beam

    def remove(self, beam: Beam):
        i = self._beams.index(beam)
        self._beams.pop(i)
        self._dmap = {n.name: n for n in self._beams}

    def get_beams_within_volume(self, vol_, margins=None) -> Iterable[Beam]:
        """
        :param vol_: List or tuple of tuples [(xmin, xmax), (ymin, ymax), (zmin, zmax)]
        :param margins: Add margins to the volume box (equal in all directions). Input is in meters. Can be negative.
        :return: List of beam ids
        """
        from bisect import bisect_left, bisect_right

        if margins is not None:
            vol_new = []
            for p in vol_:
                vol_new.append((roundoff(p[0] - margins), roundoff(p[1] + margins)))
        else:
            vol_new = vol_
        vol = vol_new

        def sort_beams(bms):
            xkeys = [key[1] for key in bms]
            xmin = bisect_left(xkeys, vol[0][0])
            xmax = bisect_right(xkeys, vol[0][1])

            within_x_list = sorted(bms[xmin:xmax], key=lambda elem: elem[2])

            ykeys = [key[2] for key in within_x_list]
            ymin = bisect_left(ykeys, vol[1][0])
            ymax = bisect_right(ykeys, vol[1][1])

            within_y_list = sorted(within_x_list[ymin:ymax], key=lambda elem: elem[3])

            zkeys = [key[3] for key in within_y_list]
            zmin = bisect_left(zkeys, vol[2][0])
            zmax = bisect_right(zkeys, vol[2][1])

            within_vol_list = within_y_list[zmin:zmax]
            return [bm[0] for bm in within_vol_list]

        bm_list1 = [(bm.name, bm.n1.x, bm.n1.y, bm.n1.z) for bm in sorted(self._beams, key=lambda bm: bm.n1.x)]
        bm_list2 = [(bm.name, bm.n2.x, bm.n2.y, bm.n2.z) for bm in sorted(self._beams, key=lambda bm: bm.n2.x)]

        return set([self._dmap[bm_id] for bms_ in (bm_list1, bm_list2) for bm_id in sort_beams(bms_)])

    @property
    def dmap(self) -> dict[int, Beam]:
        return self._dmap


class Plates(BaseCollections):
    """Plate object collection"""

    def __init__(self, plates: Iterable[Plate] = None, unique_ids=True, parent=None):
        """:type parent: ada.Part"""

        plates = [] if plates is None else plates
        super().__init__(parent)

        if unique_ids:
            plates = toolz.unique(plates, key=attrgetter("name"))
        self._plates = sorted(plates, key=attrgetter("name"))
        self._idmap = {n.name: n for n in self._plates}

    def __contains__(self, item: Plate):
        return item.id in self._idmap.keys()

    def __len__(self):
        return len(self._plates)

    def __iter__(self) -> Iterable[Plate]:
        return iter(self._plates)

    def __getitem__(self, index):
        result = self._plates[index]
        return Materials(result) if isinstance(index, slice) else result

    def __eq__(self, other):
        if not isinstance(other, Plates):
            return NotImplemented
        return self._plates == other._plates

    def __ne__(self, other):
        if not isinstance(other, Plates):
            return NotImplemented
        return self._plates != other._plates

    def __add__(self, other: Plates) -> Plates:
        return Plates(chain(self, other))

    def __repr__(self):
        rpr = reprlib.Repr()
        rpr.maxlist = 8
        rpr.maxlevel = 1
        return f"Plates({rpr.repr(self._plates) if self._plates else ''})"

    def index(self, plate: Plate):
        index = bisect_left(self._plates, plate)
        if (index != len(self._plates)) and (self._plates[index] == plate):
            return index
        raise ValueError(f"{repr(plate)} not found")

    def count(self, item: Plate):
        return int(item in self)

    def get_by_id(self, plate_id: int) -> Plate:
        plate = self._idmap.get(plate_id, None)
        if plate is None:
            raise ValueError(f'The node id "{plate_id}" is not found')
        return plate

    @property
    def dmap(self) -> dict[int, Plate]:
        return self._idmap

    def add(self, plate: Plate) -> Plate:
        if plate.name is None:
            raise Exception("Name is not allowed to be None.")

        if plate.name in self._idmap.keys():
            return self._idmap[plate.name]
        mat = self._parent.materials.add(plate.material)
        if mat is not None:
            plate.material = mat

        self._plates.append(plate)
        return plate


class Connections(BaseCollections):
    _counter = Counter(1, "C")

    def __init__(self, connections=None, parent=None):

        connections = [] if connections is None else connections
        super().__init__(parent)
        self._connections = connections
        self._dmap = {j.id: j for j in self._connections}
        self._joint_centre_nodes = Nodes([c.centre for c in self._connections])
        self._nmap = {self._joint_centre_nodes.index(c.centre): c for c in self._connections}

    @property
    def joint_centre_nodes(self):
        return self._joint_centre_nodes

    def __contains__(self, item):
        return item.id in self._dmap.keys()

    def __len__(self):
        return len(self._connections)

    def __iter__(self):
        return iter(self._connections)

    def __getitem__(self, index):
        result = self._connections[index]
        return Connections(result) if isinstance(index, slice) else result

    def __eq__(self, other: Connections):
        if not isinstance(other, Connections):
            return NotImplemented
        return self._connections == other._connections

    def __ne__(self, other: Connections):
        if not isinstance(other, Connections):
            return NotImplemented
        return self._connections != other._connections

    def __add__(self, other: Connections):
        return Connections(chain(self._connections, other._connections))

    def __repr__(self):
        rpr = reprlib.Repr()
        rpr.maxlist = 8
        rpr.maxlevel = 1
        return f"Connections({rpr.repr(self._connections) if self._connections else ''})"

    def add(self, joint, point_tol=Settings.point_tol):
        """
        Add a joint

        :param joint:
        :param point_tol: Point Tolerance
        :type joint: ada.JointBase
        """
        if joint.name is None:
            raise Exception("Name is not allowed to be None.")

        if joint.name in self._dmap.keys():
            raise ValueError("Joint Exists with same name")

        new_node = Node(joint.centre)
        node = self._joint_centre_nodes.add(new_node, point_tol=point_tol)
        if node != new_node:
            return self._nmap[node]
        else:
            self._nmap[node] = joint
        joint.parent = self
        self._dmap[joint.name] = joint
        self._connections.append(joint)

    def find(self, out_of_plane_tol=0.1, joint_func=None, point_tol=Settings.point_tol):
        """
        Find all connections between beams in all parts using a simple clash check.

        :param out_of_plane_tol:
        :param joint_func: Pass a function for mapping the generic Connection classes to a specific reinforced Joints
        :param point_tol:
        """
        from ada.concepts.connections import JointBase
        from ada.core.clash_check import are_beams_connected

        ass = self._parent.get_assembly()
        bm_res = ass.beam_clash_check()

        nodes = Nodes()
        nmap = dict()

        for bm1_, beams_ in bm_res:
            are_beams_connected(bm1_, beams_, out_of_plane_tol, point_tol, nodes, nmap)

        for node, mem in nmap.items():
            if joint_func is not None:
                joint = joint_func(next(self._counter), mem, node.p, parent=self)
                if joint is None:
                    continue
            else:
                joint = JointBase(next(self._counter), mem, node.p, parent=self)

            self.add(joint, point_tol=point_tol)


class NumericMapped(BaseCollections):
    def __init__(self, parent):
        super(NumericMapped, self).__init__(parent=parent)
        self._name_map = dict()
        self._id_map = dict()

    def recreate_name_and_id_maps(self, collection):
        self._name_map = {n.name: n for n in collection}
        self._id_map = {n.id: n for n in collection}


class Materials(NumericMapped):
    """Collection of materials"""

    def __init__(self, materials: Iterable[Material] = None, unique_ids=True, parent=None, units="m"):
        """:type parent: ada.Part | ada.Assembly"""
        super().__init__(parent)
        self._materials = sorted(materials, key=attrgetter("name")) if materials is not None else []
        self._unique_ids = unique_ids
        self.recreate_name_and_id_maps(self._materials)
        self._units = units

    def __contains__(self, item: Material):
        return item.name in self._name_map.keys()

    def __len__(self) -> int:
        return len(self._materials)

    def __iter__(self) -> Iterable[Material]:
        return iter(self._materials)

    def __getitem__(self, index):
        result = self._materials[index]
        return Materials(result) if isinstance(index, slice) else result

    def __eq__(self, other: Materials):
        if not isinstance(other, Materials):
            return NotImplemented
        return self._materials == other._materials

    def __ne__(self, other: Materials):
        if not isinstance(other, Materials):
            return NotImplemented
        return self._materials != other._materials

    def __add__(self, other: Materials):
        max_id = max(self.id_map.keys())
        other.renumber_id(max_id + 1)
        return Materials(chain(self, other))

    def __repr__(self):
        rpr = reprlib.Repr()
        rpr.maxlist = 8
        rpr.maxlevel = 1
        return f"Materials({rpr.repr(self._materials) if self._materials else ''})"

    def merge_materials_by_properties(self):
        models = []
        final_mats = []
        for i, mat in enumerate(self._materials):
            if mat.model not in models:
                models.append(mat.model)
                final_mats.append(mat)
            else:
                index = models.index(mat.model)
                replacement_mat = models[index].parent
                for ref in mat.refs:
                    ref.material = replacement_mat

        self._materials = final_mats
        self.recreate_name_and_id_maps(self._materials)

    def index(self, item: Material):
        return self._materials.index(item)

    def count(self, item: Material):
        return int(item in self)

    def get_by_name(self, name: str) -> Material:
        if name not in self._name_map.keys():
            raise ValueError(f'The material name "{name}" is not found')
        else:
            return self._name_map[name]

    def get_by_id(self, mat_id: int) -> Material:
        if mat_id not in self._id_map.keys():
            raise ValueError(f'The material id "{mat_id}" is not found')
        else:
            return self._id_map[mat_id]

    def renumber_id(self, start_id=1):
        cnt = Counter(start=start_id)
        for mat_id in sorted(self.id_map.keys()):
            mat = self.get_by_id(mat_id)
            mat.id = next(cnt)
        self.recreate_name_and_id_maps(self._materials)

    @property
    def name_map(self) -> Dict[str, Material]:
        return self._name_map

    @property
    def id_map(self) -> Dict[int, Material]:
        return self._id_map

    @property
    def parent(self):
        """:rtype: ada.Part"""
        return self._parent

    @property
    def units(self):
        return self._units

    @units.setter
    def units(self, value):
        if value != self._units:
            for m in self._materials:
                m.units = value
            self._units = value

    def add(self, material) -> Material:
        if material in self:
            return self._name_map[material.name]

        if material.id is None or material.id in self._id_map.keys():
            material.id = len(self._materials) + 1
        self._id_map[material.id] = material
        self._name_map[material.name] = material
        self._materials.append(material)

        return material


class Sections(NumericMapped):
    sec_id = Counter(1)

    def __init__(self, sections: Iterable[Section] = None, unique_ids=True, parent=None):
        super(Sections, self).__init__(parent=parent)
        """:type parent: ada.Part"""
        sections = [] if sections is None else sections
        if unique_ids:
            sections = list(toolz.unique(sections, key=attrgetter("name")))

        self._sections = sorted(sections, key=attrgetter("name"))

        def section_id_maker(section: Section) -> Section:
            if section.id is None:
                section.id = next(Sections.sec_id)
            return section

        [section_id_maker(sec) for sec in self._sections]

        self.recreate_name_and_id_maps(self._sections)

        if len(self._name_map.keys()) != len(self._id_map.keys()):
            raise ValueError("Non-unique ids or name are observed..")

    def renumber_id(self, start_id=1):
        cnt = Counter(start=start_id)
        for mat_id in sorted(self.id_map.keys()):
            mat = self.get_by_id(mat_id)
            mat.id = next(cnt)
        self.recreate_name_and_id_maps(self._sections)

    def __contains__(self, item):
        return item.name in self._name_map.keys()

    def __len__(self):
        return len(self._sections)

    def __iter__(self) -> Iterable[Section]:
        return iter(self._sections)

    def __getitem__(self, index):
        result = self._sections[index]
        return Sections(result) if isinstance(index, slice) else result

    def __add__(self, other: Sections):
        max_id = max(self.id_map.keys())
        other.renumber_id(max_id + 1)
        return Sections(chain(self, other))

    def __repr__(self):
        rpr = reprlib.Repr()
        rpr.maxlist = 8
        rpr.maxlevel = 1
        return f"Sections({rpr.repr(self._sections) if self._sections else ''})"

    def merge_sections_by_properties(self):
        models = []
        final_sections = []
        for i, sec in enumerate(self.sections):
            if sec not in models:
                models.append(sec)
                final_sections.append(sec)
            else:
                index = models.index(sec)
                replacement_sec = models[index].parent
                for ref in sec.refs:
                    ref.section = replacement_sec

        self._sections = final_sections
        self.recreate_name_and_id_maps(self._sections)

    def index(self, item):
        index = bisect_left(self._sections, item)
        if (index != len(self._sections)) and (self._sections[index] == item):
            return index
        raise ValueError(f"{repr(item)} not found")

    def count(self, item: Section) -> int:
        return int(item in self)

    def get_by_name(self, name: str) -> Section:
        if name not in self._name_map.keys():
            raise ValueError(f'The section id "{name}" is not found')
        else:
            return self._name_map[name]

    def get_by_id(self, sec_id: int) -> Section:
        if sec_id not in self._id_map.keys():
            raise ValueError(f'The node id "{sec_id}" is not found')
        else:
            return self._id_map[sec_id]

    @property
    def id_map(self) -> dict[int, Section]:
        return self._id_map

    @property
    def name_map(self) -> dict[str, Section]:
        return self._name_map

    def add(self, section: Section) -> Section:
        from ada.concepts.structural import section_counter

        if section.name is None:
            raise Exception("Name is not allowed to be None.")

        # Note: Evaluate if parent should be "Sections" not Part object?
        if section.parent is None:
            section.parent = self._parent

        if section in self._sections:
            index = self._sections.index(section)
            return self._sections[index]

        if section.name in self._name_map.keys():
            logging.error(f'Section with same name "{section.name}" already exists. Will use that section instead')
            return self._name_map[section.name]

        if section.id is None:
            section.id = next(section_counter)

        if len(self._sections) > 0:
            if section.id is None or section.id in self._id_map.keys():
                new_sec_id = next(section_counter)
                section.id = new_sec_id

        self._sections.append(section)
        self._id_map[section.id] = section
        self._name_map[section.name] = section

        return section

    @property
    def sections(self) -> List[Section]:
        return self._sections


class Nodes:
    def __init__(self, nodes=None, unique_ids=True, parent=None, from_np_array=None):
        self._parent = parent
        if from_np_array is not None:
            self._array = from_np_array
            nodes = self._np_array_to_nlist(from_np_array)
        else:
            nodes = [] if nodes is None else nodes

        if unique_ids is True:
            nodes = toolz.unique(nodes, key=attrgetter("id"))

        self._nodes = list(nodes)
        self._idmap = dict()
        self._bbox = None
        self._maxid = 0
        if len(self._nodes) > 0:
            self._sort()
            self._maxid = max(self._idmap.keys())
            self._bbox = self._get_bbox()

    def _sort(self):
        self._nodes = sorted(self._nodes, key=attrgetter("x", "y", "z"))
        self._idmap = {n.id: n for n in sorted(self._nodes, key=attrgetter("id"))}

    def renumber(self, start_id: int = 1, renumber_map: dict = None):
        """Ensures that the node numberings starts at 1 and has no holes in its numbering."""
        if renumber_map is not None:
            self._renumber_from_map(renumber_map)
        else:
            self._renumber_linearly(start_id)

        self._sort()
        self._maxid = max(self._idmap.keys()) if len(self._nodes) > 0 else 0
        self._bbox = self._get_bbox() if len(self._nodes) > 0 else None

    def _renumber_linearly(self, start_id):
        for i, n in enumerate(sorted(self._nodes, key=attrgetter("id")), start=start_id):
            if i != n.id:
                n.id = i

    def _renumber_from_map(self, renumber_map):
        for n in sorted(self._nodes, key=attrgetter("id")):
            n.id = renumber_map[n.id]

    def _np_array_to_nlist(self, np_array):
        from ada import Node

        return [Node(row[1:], int(row[0]), parent=self._parent) for row in np_array]

    def to_np_array(self, include_id=False):
        if include_id:
            return np.array([(n.id, *n.p) for n in self._nodes])
        else:
            return np.array([n.p for n in self._nodes])

    def __contains__(self, item):
        return item in self._nodes

    def __len__(self):
        return len(self._nodes)

    def __iter__(self):
        return iter(self._nodes)

    def __getitem__(self, index):
        result = self._nodes[index]
        return Nodes(result) if isinstance(index, slice) else result

    def __eq__(self, other):
        if not isinstance(other, Nodes):
            return NotImplemented
        return self._nodes == other._nodes

    def __ne__(self, other):
        if not isinstance(other, Nodes):
            return NotImplemented
        return self._nodes != other._nodes

    def __add__(self, other):
        return Nodes(chain(self._nodes, other.nodes))

    def __repr__(self):
        return f"Nodes({len(self._nodes)}, min_id: {self.min_nid}, max_id: {self.max_nid})"

    def index(self, item):
        index = bisect_left(self._nodes, item)
        if (index != len(self._nodes)) and (self._nodes[index] == item):
            return index
        raise ValueError(f"{repr(item)} not found")

    def count(self, item):
        return int(item in self)

    def move(self, move: Iterable[float, float, float] = None, rotate: Rotation = None):
        """A method for translating and/or rotating your model."""

        def moving(no):
            no.p = no.p + move

        def map_rotations(no, p):
            no.p = p

        if rotate is not None:
            p1 = np.array(rotate.origin)
            rot_mat = rotate.to_rot_matrix()
            vectors = np.array([n.p - p1 for n in self._nodes])
            res = np.matmul(vectors, np.transpose(rot_mat))
            [map_rotations(n, p + p1) for n, p in zip(self._nodes, res)]

        if move is not None:
            move = np.array(move)
            list(map(moving, self._nodes))

        self._sort()

    def from_id(self, nid: int):
        if nid not in self._idmap.keys():
            raise ValueError(f'The node id "{nid}" is not found')
        else:
            return self._idmap[nid]

    def _get_bbox(self):
        if len(self._nodes) == 0:
            raise ValueError("No Nodes are found")
        nodes_yids = sorted(self._nodes, key=attrgetter("y"))
        nodes_zids = sorted(self._nodes, key=attrgetter("z"))
        xmin, xmax = self._nodes[0], self._nodes[-1]
        ymin, ymax = nodes_yids[0], nodes_yids[-1]
        zmin, zmax = nodes_zids[0], nodes_zids[-1]
        return (xmin, xmax), (ymin, ymax), (zmin, zmax)

    @property
    def dmap(self) -> Dict[str, Node]:
        return self._idmap

    @property
    def bbox(self):
        if self._bbox is None:
            self._bbox = self._get_bbox()
        return self._bbox

    @property
    def vol_cog(self):
        return tuple([(self.bbox[i][0][i] + self.bbox[i][1][i]) / 2 for i in range(3)])

    @property
    def max_nid(self):
        return max(self.dmap.keys()) if len(self.dmap.keys()) > 0 else 0

    @property
    def min_nid(self):
        return min(self.dmap.keys()) if len(self.dmap.keys()) > 0 else 0

    @property
    def nodes(self) -> List[Node]:
        return self._nodes

    def get_by_volume(self, p=None, vol_box=None, vol_cyl=None, tol=Settings.point_tol) -> List[Node]:
        """

        :param p: Point
        :param vol_box: Additional point to find nodes inside a rectangular box
        :param vol_cyl: (radius, height, cylinder thickness). Note! Radius is measured to outside of cylinder wall
        :param tol: Point tolerance
        :return:
        """
        p = np.array(p) if type(p) is (list, tuple) else p
        if p is not None and vol_cyl is None and vol_box is None:
            vol = [(coord - tol, coord + tol) for coord in p]
        elif vol_box is not None:
            vol = list(zip(p, vol_box))
        elif vol_cyl is not None and p is not None:
            r, h, t = vol_cyl
            vol = [
                (p[0] - r - tol, p[0] + r + tol),
                (p[1] - r - tol, p[1] + r + tol),
                (p[2] - tol, p[2] + tol + h),
            ]
        else:
            raise Exception("No valid search input provided. None is returned")

        vol_min, vol_max = zip(*vol)
        xmin = bisect_left(self._nodes, Node(vol_min))
        xmax = bisect_right(self._nodes, Node(vol_max))

        xlist = sorted(self._nodes[xmin:xmax], key=attrgetter("y"))
        ysorted = [n.y for n in xlist]
        ymin = bisect_left(ysorted, vol_min[1])
        ymax = bisect_right(ysorted, vol_max[1])

        ylist = sorted(xlist[ymin:ymax], key=attrgetter("z"))
        zsorted = [n.z for n in ylist]
        zmin = bisect_left(zsorted, vol_min[2])
        zmax = bisect_right(zsorted, vol_max[2])

        simplesearch = ylist[zmin:zmax]

        if vol_cyl is not None:
            r, h, t = vol_cyl
            pt1_ = p + np.array([0, 0, -h])
            pt2_ = p + np.array([0, 0, +h])

            def eval_p_in_cyl(no):
                if t == r:
                    if points_in_cylinder(pt1_, pt2_, r, no.p) is True:
                        return no
                else:
                    eval1 = points_in_cylinder(pt1_, pt2_, r + t, no.p)
                    eval2 = points_in_cylinder(pt1_, pt2_, r - t, no.p)
                    if eval1 is True and eval2 is False:
                        return no
                return None

            return list(filter(None, [eval_p_in_cyl(q) for q in simplesearch]))
        else:
            return list(simplesearch)

    def add(self, node: Node, point_tol=Settings.point_tol, allow_coincident=False):
        """Insert node into sorted list"""

        def insert_node(n, i):
            new_id = self._maxid + 1 if len(self._nodes) > 0 else 1
            if n.id in self._idmap.keys() or n.id is None:
                n.id = new_id

            self._nodes.insert(i, n)
            self._idmap[n.id] = n
            self._bbox = None
            self._maxid = n.id if n.id > self._maxid else self._maxid

        index = bisect_left(self._nodes, node)
        if (len(self._nodes) != 0) and allow_coincident is False:
            res = self.get_by_volume(node.p, tol=point_tol)
            if len(res) == 1:
                nearest_node = res[0]
                vlen = vector_length(nearest_node.p - node.p)
                if vlen < point_tol:
                    logging.debug(f'Replaced new node with node id "{nearest_node.id}" found within point tolerances')
                    return nearest_node

        insert_node(node, index)
        return node

    def remove(self, nodes: Union[Node, Iterable[Node]]):
        """Remove node(s) from the nodes container"""
        nodes = list(nodes) if isinstance(nodes, Iterable) else [nodes]
        for node in nodes:
            if node in self._nodes:
                logging.debug(f"Removing {node}")
                self._nodes.pop(self._nodes.index(node))
                self.renumber()
            else:
                logging.error(f"'{node}' not found in node-container.")

    def remove_standalones(self):
        """Remove nodes that are without any usage references"""
        self.remove(filter(lambda x: len(x.refs) == 0, self._nodes))

    def merge_coincident(self, tol=Settings.point_tol):
        """
        Merge nodes which are within the standard default of Nodes.get_by_volume. Nodes merged into the node connected
        to most elements.
        :return:
        """
        from ada.core.utils import replace_node

        def replace_duplicate_nodes(duplicates, new_node):
            if duplicates and len(new_node.refs) >= np.max(list(map(lambda x: len(x.refs), duplicates))):
                for duplicate_node in duplicates:
                    replace_node(duplicate_node, new_node)
                    new_node.refs.extend(duplicate_node.refs)
                    duplicate_node.refs.clear()
                    self.remove(duplicate_node)

        for node in list(filter(lambda x: len(x.refs) > 0, self._nodes)):
            duplicate_nodes = list(filter(lambda x: x.id != node.id, self.get_by_volume(node.p, tol=tol)))
            replace_duplicate_nodes(duplicate_nodes, node)

        self._sort()
