import bpy

name = __name__
name = name[:len(name) - len(".module")]

def __getattr__(attr):
    if attr == 'preferences':
        return bpy.context.preferences.addons[name].preferences
    raise AttributeError(f"module '{__name__}' has no attribute '{attr}'")

