import bpy
import gpu
from gpu_extras.batch import batch_for_shader

vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
vert_out.smooth('VEC3', "pos")

shader_info = gpu.types.GPUShaderCreateInfo()
shader_info.push_constant('MAT4', "u_ViewProjectionMatrix")
shader_info.push_constant('VEC4', "u_Color")
shader_info.vertex_in(0, 'VEC3', "position")
shader_info.vertex_out(vert_out)
shader_info.fragment_out(0, 'VEC4', "FragColor")

shader_info.vertex_source(
    "void main()"
    "{"
    "  gl_Position = u_ViewProjectionMatrix * vec4(position, 1.0f);"
    "}"
)

shader_info.fragment_source(
    "void main()"
    "{"
    "  FragColor = u_Color;"
    "}"
)

shader = gpu.shader.create_from_info(shader_info)
del vert_out
del shader_info

batch = batch_for_shader(shader, 'TRIS', {
    "position": [(0, 0, 0),(1, 0, 0),(1, 1, 0),
                 (0, 0, 0),(1, 1, 0),(0, 1, 0)]
})

def rect(context, model_matrix):
    view_matrix = context.region_data.perspective_matrix
    shader.bind()
    shader.uniform_float("u_ViewProjectionMatrix", view_matrix @ model_matrix)
    shader.uniform_float("u_Color", (0.5,0.5,0.9,0.5))
    batch.draw(shader)
