# Office weapon props for SMASH 회사, modelled in Blender and exported as site/props.glb (one node per prop).
# usage: /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/build_props.py -- [--preview]
# Sizes are in metres at "normal" scale; the game scales them (a thrown envelope is ~3 m, the falling stamp ~14 m).
#   envelope  사직서 봉투      centred, lies in the XZ plane (Blender XY), thickness along up
#   wig       부장님 가발      pivot (grip) at the origin, length along +X (the engine's bat axis)
#   stamp     결재 도장        rubber face at the origin pointing down (-Z), handle up
#   badge     사원증           card centred, lanyard loop above, face toward -Y
import bpy, bmesh, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREVIEW = "--preview" in sys.argv
FONT = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
bpy.ops.wm.read_factory_settings(use_empty=True)
font = bpy.data.fonts.load(FONT)


def mat(name, rgb, rough=0.8, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


PAPER, FLAP, INK = mat("paper", srgb("#f3eee1")), mat("flap", srgb("#e2dccb")), mat("ink", srgb("#1f2228"))
HAIR, HAIR2 = mat("hair", srgb("#3b2a20"), 0.6), mat("hair_hi", srgb("#5a4030"), 0.55)
RED, REDD, WOOD = mat("stamp_red", srgb("#c0392b"), 0.45), mat("stamp_rubber", srgb("#8e1f17"), 0.9), mat("wood", srgb("#a8794d"), 0.6)
CARD, BLUE, GREY = mat("card", srgb("#f7f7f4"), 0.4), mat("badge_blue", srgb("#2f6db5"), 0.5), mat("photo", srgb("#9aa3ab"), 0.7)


def box(name, sx, sy, sz, loc=(0, 0, 0), m=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    if m: o.data.materials.append(m)
    return o


def text(name, body, size, loc, rot, m, extrude=0.01):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    o = bpy.context.object; o.name = name
    o.data.body = body; o.data.font = font; o.data.size = size; o.data.extrude = extrude
    o.data.align_x = "CENTER"; o.data.align_y = "CENTER"
    o.data.resolution_u = 2                      # Hangul glyph curves are heavy; 2 steps per segment is enough at game size
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.object
    o.data.materials.clear(); o.data.materials.append(m)
    return o


def join(name, objs, origin=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.object; o.name = name
    for p in o.data.polygons: p.use_smooth = False
    return o


# ---------- 사직서 envelope: 2.2 x 1.4 m, flap, red seal line, black title ----------
env = [box("e_body", 2.2, 1.4, 0.06, m=PAPER)]
bm = bmesh.new()
v = [bm.verts.new(p) for p in [(-1.1, 0.7, 0.031), (1.1, 0.7, 0.031), (0, 0.05, 0.031)]]
bm.faces.new(v); me = bpy.data.meshes.new("flap"); bm.to_mesh(me); bm.free()
flap = bpy.data.objects.new("e_flap", me); bpy.context.collection.objects.link(flap); flap.data.materials.append(FLAP)
mod = flap.modifiers.new("t", "SOLIDIFY"); mod.thickness = 0.01
bpy.context.view_layer.objects.active = flap; bpy.ops.object.modifier_apply(modifier="t")
env += [flap, text("e_title", "사 직 서", 0.36, (0, -0.25, 0.035), (0, 0, 0), INK, 0.006)]
envelope = join("envelope", env)

# ---------- 부장님 가발: an elongated combover hairpiece, grip at the origin, 4.8 m long along +X ----------
bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=14, radius=1, location=(2.4, 0, 0))
cap = bpy.context.object; cap.scale = (2.5, 1.05, 0.55); bpy.ops.object.transform_apply(scale=True)
bm = bmesh.new(); bm.from_mesh(cap.data)
bmesh.ops.delete(bm, geom=[v_ for v_ in bm.verts if v_.co.z < -0.05], context="VERTS")      # keep the dome
bm.to_mesh(cap.data); bm.free(); cap.data.materials.append(HAIR)
wig = [cap]
for k in range(9):                                                      # combed strands lying on the dome
    y = -0.84 + k * 0.21
    half = 2.5 * math.sqrt(max(0.0, 1 - (y / 1.05) ** 2)) * 0.96
    pts = []
    for i in range(25):
        x = 2.4 - half + 2 * half * i / 24
        q = 1 - ((x - 2.4) / 2.5) ** 2 - (y / 1.05) ** 2
        pts.append((x, y + 0.06 * math.sin(i * 0.5 + k), 0.55 * math.sqrt(max(q, 0.0)) + 0.035))
    cu = bpy.data.curves.new(f"strand{k}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.075; cu.bevel_resolution = 1
    sp = cu.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for pt, c in zip(sp.points, pts): pt.co = (*c, 1)
    so = bpy.data.objects.new(f"strand{k}", cu); bpy.context.collection.objects.link(so)
    bpy.ops.object.select_all(action="DESELECT"); so.select_set(True); bpy.context.view_layer.objects.active = so
    bpy.ops.object.convert(target="MESH")
    so = bpy.context.object; so.data.materials.append(HAIR2 if k % 2 else HAIR); wig.append(so)
bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.16, depth=0.5, location=(0.12, 0, 0.12), rotation=(0, math.radians(90), 0))
grip = bpy.context.object; grip.data.materials.append(HAIR); wig.append(grip)
wigo = join("wig", wig)

# ---------- 결재 도장: red stamp, rubber face at z=0 pointing down, total ~3 m tall ----------
st = [box("s_pad", 2.0, 2.0, 0.3, (0, 0, 0.15), REDD), box("s_body", 2.2, 2.2, 0.9, (0, 0, 0.75), RED)]
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.38, depth=1.4, location=(0, 0, 1.9)); h = bpy.context.object; h.data.materials.append(WOOD); st.append(h)
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.62, location=(0, 0, 2.75)); k_ = bpy.context.object; k_.data.materials.append(WOOD); st.append(k_)
# the seal text is cut in mirror on the rubber face, so it reads correctly when stamped
t = text("s_text", "반려", 0.9, (0, 0, -0.005), (math.radians(180), 0, 0), REDD, 0.02); st.append(t)
stamp = join("stamp", st)

# ---------- 사원증: ID card 1.6 x 2.4 m with a blue band, photo, name lines and a lanyard ----------
bd = [box("b_card", 1.6, 0.05, 2.4, (0, 0, 0), CARD), box("b_band", 1.6, 0.06, 0.5, (0, -0.002, 0.95), BLUE),
      box("b_photo", 0.7, 0.06, 0.85, (0, -0.004, 0.2), GREY), box("b_line1", 1.0, 0.06, 0.1, (0, -0.004, -0.55), INK),
      box("b_line2", 0.7, 0.06, 0.08, (0, -0.004, -0.8), GREY)]
bd.append(text("b_title", "사원증", 0.3, (0, -0.04, 0.95), (math.radians(90), 0, 0), CARD, 0.006))
bpy.ops.mesh.primitive_torus_add(major_radius=0.9, minor_radius=0.05, location=(0, 0, 2.1), rotation=(math.radians(90), 0, 0))
ly = bpy.context.object; ly.scale = (0.6, 1, 1.0); bpy.ops.object.transform_apply(scale=True); ly.data.materials.append(BLUE); bd.append(ly)
badge = join("badge", bd)

# lay them out side by side for the preview; the game reads each node by name and resets its position
for o, x in [(envelope, -6), (wigo, -3.5), (stamp, 3.5), (badge, 7)]: o.location.x += x
ROOT.joinpath("site").mkdir(exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(ROOT / "site" / "props.glb"), export_format="GLB", export_yup=True,
                          export_apply=True, export_cameras=False, export_lights=False)
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (envelope, wigo, stamp, badge))
print("props.glb", (ROOT / "site" / "props.glb").stat().st_size // 1024, "KB,", tris, "triangles")

if PREVIEW:
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try: sc.render.engine = eng; break
        except TypeError: pass
    sc.render.resolution_x, sc.render.resolution_y = 1600, 700
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.16, 0.15, 0.18, 1)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 4
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30)); sc.collection.objects.link(sun)
    import mathutils
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); cam.data.lens = 40
    cam.location = (0.5, -16, 8)
    cam.rotation_euler = (mathutils.Vector((0.5, 0, 0.8)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(cam); sc.camera = cam
    sc.render.filepath = str(ROOT / "raw" / "props_preview.png")
    bpy.ops.render.render(write_still=True)
    print("preview:", sc.render.filepath)
