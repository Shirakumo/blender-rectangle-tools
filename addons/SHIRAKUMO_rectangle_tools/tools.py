import bpy
import math
import bmesh
import heapq
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix, Quaternion
from mathutils.kdtree import KDTree
from collections import defaultdict

def line_factor(p, a, b, clamp=False):
    s = b - a
    w = p - a
    ps = w.dot(s)
    if ps <= 0 and clamp:
        return 0.0
    l2 = s.dot(s)
    if ps >= l2 and clamp:
        closest = 1.0
    else:
        closest = ps / l2
    return closest

def snap_to_line(p, a, b, clamp=False):
    s = b - a
    return a + line_factor(p, a, b, clamp) * s

def snap_to_grid(p, grid=0.1, basis=Matrix.Identity(4)):
    if grid == 0.0:
        return p
    p = basis.inverted_safe() @ p
    r = [*p]
    for i in range(len(r)):
        r[i] = round((r[i])/grid)*grid
    return basis @ Vector(r)

def edge_segment(edge):
    return (edge.verts[0].co, edge.verts[1].co)

def edge_distance(edge, p, clamp=True):
    x = snap_to_line(p, *edge_segment(edge), clamp)
    return (x-p).length

def closest_edge(face, point):
    e = face.edges[0]
    d = edge_distance(e, point)
    for i in range(1, len(face.edges)):
        dt = edge_distance(face.edges[i], point)
        if dt < d:
            d = dt
            e = face.edges[i]
    return (e,d)

def edge_face(edge):
    pass

def edge_basis(edge, origin):
    pass

def mouse_position_3d(context, mouse_pos):
    region = context.region
    region3D = context.space_data.region_3d
    return view3d_utils.region_2d_to_location_3d(region, region3D, mouse_pos, Vector([0.0,0.0,0.0]))

def position_3d_mouse(context, pos):
    return view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d, pos)

class MeshTools():
    def __init__(self, object):
        self.object = object
        self.mesh = None
        self.refresh()

    def closest_edge_view(self, context, mouse_pos):
        return self.closest_edge(mouse_position_3d(context, mouse_pos))

    def closest_edge(self, point):
        _,f,fd = self.kd.find(point)
        e,d = closest_edge(self.mesh.faces[f], point)
        p = snap_to_line(point, *edge_segment(e))
        return (e,d,p)

    def project_to_plane(self, face, context, mouse_pos):
        region = context.region
        region3D = context.space_data.region_3d
        view_vector = view3d_utils.region_2d_to_vector_3d(region, region3D, mouse_pos)
        ## TODO: this

    def closest_connected_edge(self, edge, point):
        pass

    def edge_between(self, a, b):
        for e in a.link_edges:
            if e.other_vert(a) == b:
                return e
        return None

    def edge_path(self, start, end):
        ## KLUDGE: this is really terrible, but we're essentially doing a dijkstra
        visited = set()
        prev = {}
        queue = []
        dist = defaultdict(lambda: math.inf)
        dist[start] = 0.0
        heapq.heappush(queue, (0.0, start))
        while queue:
            _, u = heapq.heappop(queue)
            visited.add(u)
            for e in u.link_edges:
                v = e.other_vert(u)
                if v in visited:
                    continue
                alt = dist[u] + (v.co-start.co).length
                if dist[v] > alt:
                    prev[v] = (u,e)
                    dist[v] = alt
                    heapq.heappush(queue, (alt, v))
        edges = []
        u = end
        while u is not None:
            u = prev.get(u)
            if u is not None:
                (u,e) = u
                edges.append(e)
        return edges

    def refresh(self):
        if self.mesh is not None:
            self.mesh.free()
        self.mesh = bmesh.from_edit_mesh(self.object.data)
        self.kd = KDTree(len(self.mesh.faces))
        for i,f in enumerate(self.mesh.faces):
            self.kd.insert(f.calc_center_median(), i)
        self.kd.balance()

    def free(self, sync=False):
        if self.mesh is not None:
            if sync:
                bmesh.update_edit_mesh(self.object)
            self.mesh.free()
        self.mesh = None

    def select(self, thing):
        for face in self.mesh.faces:
            face.select = False
        for edge in self.mesh.edges:
            edge.select = False
        for vertex in self.mesh.verts:
            vertex.select = False
        if hasattr(thing, '__iter__'):
            for e in thing:
                e.select = True
        else:
            thing.select = True
        self.mesh.select_flush(True)

class SHIRAKUMO_RECT_OT_draw_rectangle(bpy.types.Operator):
    bl_idname = "shirakumo_rect.draw_rectangle"
    bl_label = "Draw rectangle"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Draw a rectangle"
    
    def free(self):
        self.mt.free()
        return {'FINISHED'}
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        if event.type == 'MOUSEMOVE':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)

        elif event.type == 'LEFTMOUSE':
            mouse_pos = (event.mouse_region_x, event.mouse_region_y)
            point = snap_to_grid(mouse_position_3d(context, mouse_pos), self.grid, self.basis)
            end = None

            ## TODO: This sucks, it fails when there's splits in between our source and target etc.
            ##       We should instead use the starting edge as the direction to guide our end path.
            ##       Meaning: follow along connected edges in direction of the starting edge until
            ##       distance to our target decreases again or we have no edge in that direction.
            ##       Then we project our target onto that final edge and do the rest.
            if len(self.start.link_edges) == 2:
                ## Check the two connected edges from the start segment we created
                e = self.start.link_edges[0]
                f = line_factor(point, *edge_segment(e))
                if (f < 0 or 1 < f):
                    e = self.start.link_edges[1]
                    f = line_factor(point, *edge_segment(e))
                if (0 < f and f < 1):
                    ## We split in an existing edge
                    if e.verts[0] != self.start:
                        f = 1-f
                    e,end = bmesh.utils.edge_split(e, self.start, f)
                else:
                    ## We split outside our edge, so extrude the endpoint.
                    v = e.verts[0] if f < 0 else e.verts[1]
                    v = bmesh.ops.extrude_vert_indiv(self.mt.mesh, verts=[v])['verts'][0]
                    v.co = end
                    end = v
            elif len(self.start.link_edges) == 1:
                (e,_,end) = self.mt.closest_edge_view(context, mouse_pos)
                end = snap_to_grid(end, self.grid, self.basis)
                f = line_factor(end, *edge_segment(e))
                if (0 < f and f < 1):
                    ## We split in an existing edge
                    e,end = bmesh.utils.edge_split(e, e.verts[0], f)
                else:
                    ## We split outside an existing edge again
                    v = e.verts[0] if f < 0 else e.verts[1]
                    v = bmesh.ops.extrude_vert_indiv(self.mt.mesh, verts=[v])['verts'][0]
                    v.co = end
                    end = v

            if end is not None:
                es = self.mt.edge_path(self.start, end)
                ## Perform the edge extrusion
                data = bmesh.ops.extrude_edge_only(self.mt.mesh, edges=es)['geom']
                v = [ x for x in data if isinstance(x, bmesh.types.BMVert) ]
                if 2 < len(v):
                    bmesh.ops.dissolve_verts(self.mt.mesh, verts=v[1:-1])
                a = v[-1]
                b = v[0]
                diff = b.co-a.co
                a.co = point
                b.co = a.co+diff
                ## Flush the edit
                self.mt.select(self.mt.edge_between(a,b))
                bmesh.update_edit_mesh(context.object.data)
            return self.free()

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
        (e,d,start) = self.mt.closest_edge_view(context, mouse_pos)
        start = snap_to_grid(start, self.grid, self.basis)
        f = line_factor(start, *edge_segment(e))
        if (0 < f and f < 1):
            _,start = bmesh.utils.edge_split(e, e.verts[0], f)
        elif 0 == f:
            start = e.verts[0]
        elif 1 == f:
            start = e.verts[1]
        else:
            v = e.verts[0] if f < 0 else e.verts[1]
            v = bmesh.ops.extrude_vert_indiv(self.mt.mesh, verts=[v])['verts'][0]
            v.co = start
            start = v
        self.start = start
        self.edge = e
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
        e,d,p = self.group.mt.closest_edge_view(context, mouse_pos)
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
