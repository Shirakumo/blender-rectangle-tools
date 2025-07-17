import bpy
from mathutils import Vector, Matrix, Quaternion
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
    
    def free(self):
        self.mt.free()
        return {'FINISHED'}
    
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        elif event.type == 'LEFTMOUSE':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
            point = snap_to_grid(mouse_position_3d(context, mouse_pos), self.grid, self.basis)
            res = self.mt.create_rect(self.edge, self.start, point)
            if res is not None:
                self.mt.select(edge_between(res[0],res[1]))
                bmesh.update_edit_mesh(context.object.data)
                self.free()
                return {'FINISHED'}
            self.free()
            return {'CANCELLED'}
        elif event.type == 'RIGHTMOUSE':
            self.free()
            return {'CANCELLED'}
        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        self.grid = 0.0
        self.basis = Matrix.Identity(4)
        self.mt = MeshTools(context.object)
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        (e,_,p,f) = self.mt.closest_edge_view(context, mouse_pos)
        self.start = snap_to_grid(p, self.grid, self.basis)
        self.edge = e
        self.face = f
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class SHIRAKUMO_RECT_G_rectangle_preselect(bpy.types.Gizmo):
    bl_idname = "SHIRAKUMO_RECT_G_rectangle_preselect"
    
    def draw(self, context):
        mat = context.object.matrix_world
        if self.edge is not None:
            zero = Vector([1,0,0])
            dir = self.edge.verts[1].co - self.edge.verts[0].co
            mat = Matrix.Translation(self.edge.verts[0].co)
            mat = mat @ zero.rotation_difference(dir).to_matrix().to_4x4()
            mat = mat @ Matrix.Scale(self.edge.calc_length(), 4, [1,0,0])
            self.draw_custom_shape(self.line, matrix=mat)
        if self.edgepoint is not None:
            mat = Matrix.Translation(self.edgepoint)
            self.draw_custom_shape(self.point, matrix=mat)

    def setup(self):
        self.line = self.new_custom_shape('LINES', [[0.0, 0.0, 0.0],[1.0,0.0,0.0]])
        self.point = self.new_custom_shape('POINTS', [[0.0, 0.0, 0.0]])
        self.select = True
        self.color = 0.3, 0.3, 0.9
        self.edge = None
        self.edgepoint = None

    def invoke(self, context, event):
        print("Gizmo invoke")
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        print("Gizmo Exit")

    def test_select(self, context, mouse_pos):
        e,d,p,f = self.group.mt.closest_edge_view(context, mouse_pos)
        self.edgepoint = p
        self.edge = e
        context.area.tag_redraw()
        return -1

    def modal(self, context, event, tweak):
        print('Gizmo modal')
        return {'RUNNING_MODAL'}

class SHIRAKUMO_RECT_GG_rectangle(bpy.types.GizmoGroup):
    bl_idname = "SHIRAKUMO_RECT_GG_rectangle"
    bl_label = "Side of Plane Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'SELECT'}
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
    bl_keymap = (
        ("shirakumo_rect.draw_rectangle", {"type": 'LEFTMOUSE', "value": 'PRESS'},
         {"properties": []}),
    )

    grid: bpy.props.FloatProperty(
        name="Grid",
        default=0.0, options=set(),
        description="The grid size used for snapping.")

registered_classes = [
    SHIRAKUMO_RECT_OT_draw_rectangle,
    SHIRAKUMO_RECT_G_rectangle_preselect,
    SHIRAKUMO_RECT_GG_rectangle,
]

def register():
    for cls in registered_classes:
        bpy.utils.register_class(cls)
    bpy.utils.register_tool(SHIRAKUMO_RECT_WT_rectangle, after={'builtin.poly_build'})

def unregister():
    bpy.utils.unregister_tool(SHIRAKUMO_RECT_WT_rectangle)
    for cls in registered_classes:
        bpy.utils.unregister_class(cls)
