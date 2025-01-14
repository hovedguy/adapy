import ada
from ada.fem.surfaces import create_surface_from_nodes


def test_surface_box():
    # Build Model
    a = ada.Assembly() / (ada.Part("MyBoxPart") / ada.PrimBox("MyBoxShape", (0, 0, 0), (1, 1, 1)))

    # Create FEM mesh
    p = a.get_part("MyBoxPart")
    p.fem = p.to_fem_obj(0.1, "solid", interactive=False)

    # Add Step
    step = a.fem.add_step(ada.fem.StepImplicit("MyStep"))

    # Add surfaces
    box: ada.PrimBox = a.get_by_name("MyBoxShape")

    front_nodes = box.sides.front(return_fem_nodes=True)
    btn_nodes = box.sides.bottom(return_fem_nodes=True)

    p.fem.add_set(ada.fem.FemSet("FrontNodes", front_nodes))
    fs_btn = p.fem.add_set(ada.fem.FemSet("BottomNodes", btn_nodes))
    p.fem.add_bc(ada.fem.Bc("fix", fs_btn, [1, 2, 3]))

    surface = p.fem.add_surface(create_surface_from_nodes("FrontElements", front_nodes, p.fem))

    step.add_load(ada.fem.LoadPressure("MyPressureLoad", 200, surface))
    #
    # tetra: [(0, 1, 2), (0, 3, 2), (0, 1, 3), (1, 3, 2)]

    print(box)
    el = p.fem.elements[0]
    print(el)
    a.to_fem("MyFemBox", "abaqus", overwrite=True)
    a.to_fem("MyFemBox_ca", "code_aster", overwrite=True)

    # TODO: Specify surfaces on elements on the East and North side of this box and assign pressure and surface traction
