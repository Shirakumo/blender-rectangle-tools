import bpy
import bmesh
from bl_ui.space_toolsystem_toolbar import VIEW3D_PT_tools_active as tools
from mathutils import Vector, Matrix
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
    grid_basis: bpy.props.EnumProperty(
        name="Basis",
        items=[
            ("GLOBAL", "Global", "Snap to global coordinates", "ORIENTATION_GLOBAL", 1),
            ("VIEW", "View", "Snap to the view plane", "ORIENTATION_VIEW", 2),
            ("LOCAL", "Local", "Snap to the object's transform", "ORIENTATION_LOCAL", 3),
            ("NORMAL", "Normal", "Snap to the normal of the adjacent face", "ORIENTATION_NORMAL", 4),
        ],
        default="GLOBAL",
        description="The basis to grid snap relative to")
    dissolve_verts: bpy.props.BoolProperty(
        name="Dissolve Verts",
        default=True, options=set(),
        description="Whether to dissolve superfluous vertices on the extruded edge")
    renderer = None

    @classmethod
    def poll(cls, context):
        if context.area.type == 'VIEW_3D':
            return True
        return False

    def snap(self, thing):
        basis = Matrix.Identity(4)
        if self.grid_basis == "VIEW":
            basis = bpy.context.region_data.view_matrix
        if self.grid_basis == "LOCAL":
            basis = bpy.context.object.matrix_world
        if self.grid_basis == "NORMAL":
            raise Exception("IMPLEMENT ME!")
        return snap_to_grid(thing, self.grid, basis)

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
        edit_type = context.scene.transform_orientation_slots[0].type
        if edit_type in ['GLOBAL', 'VIEW', 'LOCAL', 'NORMAL']:
            self.grid_basis = edit_type
        self.renderer = bpy.types.SpaceView3D.draw_handler_add(self.render, (context,), "WINDOW", "POST_VIEW")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        start = self.snap(self.start)
        end = self.snap(self.end)
        mt = MeshTools(context.object)
        res = mt.create_rect(mt.mesh.edges[self.edge], start, end, dissolve_verts=self.dissolve_verts)
        if res is not None:
            mt.select(res[1])
        mt.free(sync=True)
        if self.renderer:
            bpy.types.SpaceView3D.draw_handler_remove(self.renderer, "WINDOW")
            self.renderer = None
        return {'FINISHED'}

    def cancel(self, context):
        if self.renderer:
            bpy.types.SpaceView3D.draw_handler_remove(self.renderer, "WINDOW")
            self.renderer = None

    def render(self, context):
        if context.object.data.is_editmode:
            mesh = bmesh.from_edit_mesh(context.object.data)
        else:
            mesh = bmesh.new()
            mesh.from_mesh(context.object.data)
        mesh.edges.ensure_lookup_table()
        edge = mesh.edges[self.edge]
        c1 = edge_snap(edge, self.snap(self.start))
        c3 = self.snap(self.end)
        c2 = edge_snap(edge, c3)
        c4 = c3+(c1-c2)
        render.rect(context, [*c1, *c2, *c3, *c4])
        mesh.free()

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

    def exit(self, context, cancel):
        self.edge = None
        self.edgepoint = None
    
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

    def refresh(self, context):
        if self.mt != None:
        if self.mt is not None:
            self.mt.refresh()

    def setup(self, context):
        if self.mt is None:
            self.mt = MeshTools(context.object)
        self.gizmo_dial = self.gizmos.new("SHIRAKUMO_RECT_G_rectangle_preselect")

    def draw_prepare(self, context):
        ## KLUDGE: Check if our tool is no longer active and deregister if so.
        ##         Otherwise our tool is going to be active all while another is going on, too!
        ##         There is no actual hook for when the tool is disabled, lmao.
        if context.space_data and tools.tool_active_from_context(bpy.context).idname != SHIRAKUMO_RECT_WT_rectangle.bl_idname:
            context.window_manager.gizmo_group_type_unlink_delayed(SHIRAKUMO_RECT_GG_rectangle.bl_idname)

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

    def draw_settings(context, layout, tool):
        group = module.preferences
        layout.prop(group, "grid")

class SHIRAKUMO_RECT_WT_rectangle_OBJECT(SHIRAKUMO_RECT_WT_rectangle):
    bl_context_mode = 'OBJECT'

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
    ## KLUDGE: Can't seem to enter the tool after the group builtin.primitive_cube_add creates, it just
    ##         always wants to insert the tool into that group. Fun. I could make it into a group, but
    ##         then it would be a pointless group with nothing else.
    bpy.utils.register_tool(SHIRAKUMO_RECT_WT_rectangle_OBJECT, after={'builtin.measure'}, separator=True)

def unregister():
    bpy.utils.unregister_tool(SHIRAKUMO_RECT_WT_rectangle)
    bpy.utils.unregister_tool(SHIRAKUMO_RECT_WT_rectangle_OBJECT)
    for cls in registered_classes:
        bpy.utils.unregister_class(cls)
