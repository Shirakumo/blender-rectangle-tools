import bpy
from mathutils import Vector, Matrix, Quaternion
from . import module, render
from .mesh import *

def snap_to_grid(p, grid=0.1, basis=Matrix.Identity(4)):
    if grid == 0.0:
        return p
    p = basis.inverted_safe() @ p
    r = [*p]
    for i in range(len(r)):
        r[i] = round((r[i])/grid)*grid
    return basis @ Vector(r)

class SHIRAKUMO_RECT_OT_draw_rectangle(bpy.types.Operator):
    bl_idname = "shirakumo_rect.draw_rectangle"
    bl_label = "Draw rectangle"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Draw a rectangle"

    edge: bpy.props.IntProperty(
        name="Edge Index",
        options=set(['HIDDEN','SKIP_SAVE','SKIP_PRESET']))
    start: bpy.props.FloatVectorProperty(
        name="Start Point",
        subtype="COORDINATES",
        default=(0.0,0.0,0.0),
        options=set(['HIDDEN','SKIP_SAVE','SKIP_PRESET']))
    end: bpy.props.FloatVectorProperty(
        name="End Point",
        subtype="COORDINATES",
        default=(0.0,0.0,0.0),
        options=set(['HIDDEN','SKIP_SAVE','SKIP_PRESET']))
    grid: bpy.props.FloatProperty(
        name="Grid",
        default=0.1, min=0.0, options=set(),
        description="The grid size used for snapping")
    dissolve_verts: bpy.props.BoolProperty(
        name="Dissolve Verts",
        default=True, options=set(),
        description="Whether to dissolve superfluous vertices on the extruded edge")
    renderer = None

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
            self.end = mouse_position_3d(context, mouse_pos, self.start)
            context.area.tag_redraw()
        elif event.type == 'LEFTMOUSE':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
            self.end = mouse_position_3d(context, mouse_pos, self.start)
            return self.execute(context)
        elif event.type == 'RIGHTMOUSE':
            return {'CANCELLED'}
        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        self.renderer = bpy.types.SpaceView3D.draw_handler_add(self.render, (context,), "WINDOW", "POST_PIXEL")
        return {'RUNNING_MODAL'}

    def execute(self, context):
        start = snap_to_grid(self.start, self.grid)
        end = snap_to_grid(self.end, self.grid)
        mt = MeshTools(context.object)
        res = mt.create_rect(mt.mesh.edges[self.edge], start, end, dissolve_verts=self.dissolve_verts)
        if res is not None:
            mt.select(res[1])
            mt.sync()
        mt.free()
        if self.renderer:
            bpy.types.SpaceView3D.draw_handler_remove(self.renderer, "WINDOW")
            self.renderer = None
        return {'FINISHED'}

    def cancel(self, context):
        if self.renderer:
            bpy.types.SpaceView3D.draw_handler_remove(self.renderer, "WINDOW")
            self.renderer = None

    def render(self, context):
        mesh = context.object.data
        edge = mesh.edges[self.edge]
        a = mesh.vertices[edge.vertices[0]].co
        b = mesh.vertices[edge.vertices[1]].co
        start = line_snap(snap_to_grid(self.start, self.grid), a, b)
        end = snap_to_grid(self.end, self.grid)
        r = line_rotation(a, b)
        diff = r @ (end-start)
        mat = Matrix.Translation(start)
        mat = mat @ r.to_matrix().to_4x4()
        mat = mat @ Matrix.Scale(diff[0], 4, [1,0,0])
        mat = mat @ Matrix.Scale(diff[1], 4, [0,1,0])
        render.rect(context, mat)

class SHIRAKUMO_RECT_G_rectangle_preselect(bpy.types.Gizmo):
    bl_idname = "SHIRAKUMO_RECT_G_rectangle_preselect"
    bl_target_properties = (
        {"id": "edge", "type": 'INT'},
        {"id": "start", "type": 'FLOAT', "array_length": 3},
        {"id": "end", "type": 'FLOAT', "array_length": 3},
        {"id": "grid", "type": 'FLOAT'},
    )

    def setup(self):
        self.line = self.new_custom_shape('LINES', [[0,0,0],[1,0,0]])
        self.point = self.new_custom_shape('POINTS', [[0,0,0]])
        self.color_highlight = 1.0, 1.0, 1.0
        self.alpha_highlight = 0.9
        self.color = 0.5, 0.5, 0.9
        self.alpha = 0.9
        self.edge = None
        self.select = True
        self.edgepoint = None
        self.op = self.target_set_operator("shirakumo_rect.draw_rectangle")
    
    def draw(self, context):
        mat = context.object.matrix_world
        if self.edgepoint is not None:
            mat = Matrix.Translation(self.edgepoint)
            self.draw_custom_shape(self.point, matrix=mat)
        if self.edge is not None:
            r = edge_rotation(self.edge)
            mat = Matrix.Translation(self.edge.verts[0].co)
            mat = mat @ r.to_matrix().to_4x4()
            mat = mat @ Matrix.Scale(self.edge.calc_length(), 4, [1,0,0])
            self.draw_custom_shape(self.line, matrix=mat)

    def test_select(self, context, mouse_pos):
        e,d,p,f = self.group.mt.closest_edge_view(context, mouse_pos)
        self.edgepoint = snap_to_grid(p, module.preferences.grid)
        self.edge = e
        self.op.edge = e.index
        self.op.start = p
        self.op.grid = module.preferences.grid
        context.area.tag_redraw()
        return 0

class SHIRAKUMO_RECT_GG_rectangle(bpy.types.GizmoGroup):
    bl_idname = "SHIRAKUMO_RECT_GG_rectangle"
    bl_label = "Side of Plane Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'SELECT'}
    bl_operator = "shirakumo_rect.draw_rectangle"
    mt = None

    @classmethod
    def poll(cls, context):
        if context.mode != 'EDIT_MESH':
            context.window_manager.gizmo_group_type_unlink_delayed(SHIRAKUMO_RECT_GG_rectangle.bl_idname)
            return False
        return True

    def refresh(self, context):
        self.mt.refresh()

    def setup(self, context):
        if self.mt == None:
            self.mt = MeshTools(context.object)
        self.gizmo_dial = self.gizmos.new("SHIRAKUMO_RECT_G_rectangle_preselect")

    def draw_prepare(self, context):
        pass

class SHIRAKUMO_RECT_WT_rectangle(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'
    bl_idname = 'SHIRAKUMO_rectangle_tools.rectangle_tool'
    bl_label = 'Rectangle Tool'
    bl_description = (
        'Extend geometry via rectangles'
    )
    bl_icon = 'ops.gpencil.primitive_box'
    bl_widget = 'SHIRAKUMO_RECT_GG_rectangle'
    # bl_keymap = (
    #      ("shirakumo_rect.draw_rectangle", {"type": 'LEFTMOUSE', "value": 'RELEASE'},
    #       {"properties": []}),
    # )

    def draw_settings(context, layout, tool):
        group = module.preferences
        layout.prop(group, "grid")

class SHIRAKUMO_RECT_properties(bpy.types.AddonPreferences):
    bl_idname = module.name
    grid: bpy.props.FloatProperty(
        name="Grid",
        default=0.1, min=0.0, options=set(),
        description="The grid size used for snapping.")

registered_classes = [
    SHIRAKUMO_RECT_OT_draw_rectangle,
    SHIRAKUMO_RECT_G_rectangle_preselect,
    SHIRAKUMO_RECT_GG_rectangle,
    SHIRAKUMO_RECT_properties,
]

def register():
    for cls in registered_classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_tool(SHIRAKUMO_RECT_WT_rectangle, after={'builtin.poly_build'})

def unregister():
    bpy.utils.unregister_tool(SHIRAKUMO_RECT_WT_rectangle)
    for cls in registered_classes:
        bpy.utils.unregister_class(cls)
