# Models one sub-area in Blender: terrain draped with the ground photo, and every building cut into smashable chunks
# with a podium, parapet, rooftop plant and facade UVs in world metres; exports site/areas/<id>/scene.glb + meta.json.
# usage: /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/build_area.py -- <area_id> [--preview]
# Blender axes: x east, y north, z up. glTF export turns them into three.js (x, z, -y).
# Materials are exported by name only (no images); the game binds the shared facade textures and the area's ground image.
import bpy, bmesh, json, math, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARGS = sys.argv[sys.argv.index("--") + 1:]
AID, PREVIEW = ARGS[0], "--preview" in ARGS
RAW = ROOT / "raw" / AID
OUT = ROOT / "site" / "areas" / AID
OUT.mkdir(parents=True, exist_ok=True)
prep = json.loads((RAW / "prep.json").read_text(encoding="utf-8"))
SIZE = prep["size"]; HALF = SIZE / 2
CELL, LAYER, PODIUM, PARAPET = 8.0, 7.0, 5.0, 1.0      # chunk width, chunk height (2 storeys), ground floor, parapet
TW, TH, SHOP_W, SHOP_H = 24.0, 28.0, 24.0, 6.0          # metres covered by one facade / shop-front tile
SINK = 3.0                                              # walls reach this far below the lowest ground point
GROUND_IMG = RAW / "aerial.jpg" if (RAW / "aerial.jpg").exists() else RAW / "ground.png"
random.seed(5)

bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, img=None, color=(0.8, 0.8, 0.8, 1), rough=0.85, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if img is not None and pathlib.Path(img).exists():
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(img))
        m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


TEXD = ROOT / "raw" / "tex"
MATS = [material("ground", GROUND_IMG), material("roof", GROUND_IMG),
        material("glass", TEXD / "glass.png", rough=0.25, metal=0.35), material("concrete", TEXD / "concrete.png"),
        material("plaster", TEXD / "plaster.png"), material("shop", TEXD / "shop.png", rough=0.5),
        material("off", TEXD / "off.png"), material("core", TEXD / "core.png"), material("roofkit", TEXD / "roofkit.png"),
        material("roofplain", color=(0.55, 0.57, 0.58, 1))]
MI = {m.name: i for i, m in enumerate(MATS)}

# ---------- geometry helpers ----------
bm = bmesh.new()
UV = bm.loops.layers.uv.new("UVMap")
CH = bm.verts.layers.float.new("_chunk")


def face(pts, uvs, mat, cid):
    vs = [bm.verts.new(p) for p in pts]
    for v in vs: v[CH] = cid
    try:
        f = bm.faces.new(vs)
    except ValueError:
        return None
    f.material_index = MI[mat]
    for loop, uv in zip(f.loops, uvs): loop[UV].uv = uv
    return f


def guv(x, y):                       # ground / roof photo UV
    return ((x + HALF) / SIZE, (y + HALF) / SIZE)


def rot(p, c, s):
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def clip(poly, x0, y0, x1, y1):
    # Sutherland–Hodgman against an axis-aligned rectangle
    def cut(pts, inside, inter):
        out = []
        for i, cur in enumerate(pts):
            prev = pts[i - 1]
            if inside(cur):
                if not inside(prev): out.append(inter(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(inter(prev, cur))
        return out
    def ix(a, b, x): t = (x - a[0]) / (b[0] - a[0]); return (x, a[1] + (b[1] - a[1]) * t)
    def iy(a, b, y): t = (y - a[1]) / (b[1] - a[1]); return (a[0] + (b[0] - a[0]) * t, y)
    p = poly
    for inside, inter in [(lambda q: q[0] >= x0, lambda a, b: ix(a, b, x0)), (lambda q: q[0] <= x1, lambda a, b: ix(a, b, x1)),
                          (lambda q: q[1] >= y0, lambda a, b: iy(a, b, y0)), (lambda q: q[1] <= y1, lambda a, b: iy(a, b, y1))]:
        if not p: break
        p = cut(p, inside, inter)
    # drop repeated points
    q = []
    for v in p:
        if not q or abs(v[0] - q[-1][0]) > 1e-4 or abs(v[1] - q[-1][1]) > 1e-4: q.append(v)
    if len(q) > 1 and abs(q[0][0] - q[-1][0]) < 1e-4 and abs(q[0][1] - q[-1][1]) < 1e-4: q.pop()
    return q


def parea(r):
    return sum(r[i - 1][0] * r[i][1] - r[i][0] * r[i - 1][1] for i in range(len(r))) / 2


def on_ring(p, ring, cum):
    # returns the perimeter coordinate s if p lies on the footprint boundary, else None
    best = None
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-9: continue
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        qx, qy = a[0] + dx * t, a[1] + dy * t
        d = math.hypot(p[0] - qx, p[1] - qy)
        if d < 0.06 and (best is None or d < best[0]): best = (d, cum[i] + t * math.sqrt(L2))
    return None if best is None else best[1]


def wall_kind(b):
    return {"glass": "glass", "concrete": "concrete", "plaster": "plaster"}.get(b["kind"], "off")


# ---------- buildings ----------
chunks, meta_b = [], []
for b in prep["buildings"]:
    ring = [tuple(p) for p in b["ring"]]
    n = len(ring)
    cum = [0.0]
    for i in range(n): cum.append(cum[-1] + math.dist(ring[i], ring[(i + 1) % n]))
    base, h, minh = b["base"], b["h"], b["minh"]
    zbot = base + minh if minh > 0 else base - SINK
    ztop = base + h
    kind = b["kind"]
    mb = {"id": b["id"], "name": b["name"], "kind": kind, "smash": b["smash"], "h": h, "c0": len(chunks)}

    if not b["smash"]:
        # off-limits or canopy: one static block (chunk id -1), never cut
        cid = -1.0
        if kind == "canopy": zbot = ztop - 0.6
        for i in range(n):
            a, c = ring[i], ring[(i + 1) % n]
            u0, u1 = cum[i] / 12, cum[i + 1] / 12
            face([(a[0], a[1], zbot), (c[0], c[1], zbot), (c[0], c[1], ztop), (a[0], a[1], ztop)],
                 [(u0, zbot / 12), (u1, zbot / 12), (u1, ztop / 12), (u0, ztop / 12)], "off" if kind == "off" else "core", cid)
        face([(x, y, ztop) for x, y in ring], [guv(x, y) for x, y in ring], "roof", cid)
        if kind == "canopy": face([(x, y, zbot) for x, y in reversed(ring)], [guv(x, y) for x, y in reversed(ring)], "core", cid)
        mb["c1"] = len(chunks)
        meta_b.append(mb)
        continue

    # cut along the longest edge's direction so chunks follow the building's grid
    li = max(range(n), key=lambda i: math.dist(ring[i], ring[(i + 1) % n]))
    ang = math.atan2(ring[(li + 1) % n][1] - ring[li][1], ring[(li + 1) % n][0] - ring[li][0])
    co, si = math.cos(-ang), math.sin(-ang)
    loc = [rot(p, co, si) for p in ring]
    xs = [p[0] for p in loc]; ys = [p[1] for p in loc]
    nx_, ny_ = max(1, round((max(xs) - min(xs)) / CELL)), max(1, round((max(ys) - min(ys)) / CELL))
    sx_, sy_ = (max(xs) - min(xs)) / nx_, (max(ys) - min(ys)) / ny_
    # layers: podium, then 7 m layers; a last sliver under 2.5 m joins the layer below
    zs = [zbot]
    z = base + PODIUM if minh <= 0 else zbot + LAYER
    while z < ztop - 2.5:
        zs.append(z); z += LAYER
    zs.append(ztop)
    wk = wall_kind(b)
    col = 0
    for gi in range(nx_):
        for gj in range(ny_):
            piece = clip(loc, min(xs) + gi * sx_ - 1e-6, min(ys) + gj * sy_ - 1e-6,
                         min(xs) + (gi + 1) * sx_ + 1e-6, min(ys) + (gj + 1) * sy_ + 1e-6)
            if len(piece) < 3 or abs(parea(piece)) < 1.0: continue
            co2, si2 = math.cos(ang), math.sin(ang)
            P = [rot(p, co2, si2) for p in piece]
            if parea(P) < 0: P = P[::-1]
            A = abs(parea(P))
            cx = sum(p[0] for p in P) / len(P); cy = sum(p[1] for p in P) / len(P)
            # which edges of this piece are on the outside of the building, and their perimeter coordinates
            edges = []
            for i in range(len(P)):
                a, c = P[i], P[(i + 1) % len(P)]
                mid = ((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
                ext = on_ring(mid, ring, cum) is not None
                sa = on_ring(a, ring, cum) if ext else None
                sc = on_ring(c, ring, cum) if ext else None
                if ext and sa is not None and sc is not None and sc < sa and sa - sc > cum[-1] / 2: sc += cum[-1]
                edges.append((a, c, ext, sa, sc))
            for li2 in range(len(zs) - 1):
                z0, z1 = zs[li2], zs[li2 + 1]
                top = li2 == len(zs) - 2
                cid = float(len(chunks))
                for a, c, ext, sa, sc in edges:
                    if ext and sa is not None and sc is not None:
                        if li2 == 0 and minh <= 0:
                            m_, u0, u1, v0, v1 = "shop", sa / SHOP_W, sc / SHOP_W, (z0 - base) / SHOP_H, (z1 - base) / SHOP_H
                        else:
                            zb = base + PODIUM
                            m_, u0, u1, v0, v1 = wk, sa / TW, sc / TW, (z0 - zb) / TH, (z1 - zb) / TH
                        face([(a[0], a[1], z0), (c[0], c[1], z0), (c[0], c[1], z1), (a[0], a[1], z1)],
                             [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], m_, cid)
                        if top and h > 9:     # parapet: outer face continues the facade, inner face is plain
                            zp = z1 + PARAPET
                            face([(a[0], a[1], z1), (c[0], c[1], z1), (c[0], c[1], zp), (a[0], a[1], zp)],
                                 [(u0, v1), (u1, v1), (u1, v1 + PARAPET / TH), (u0, v1 + PARAPET / TH)],
                                 "core" if wk == "glass" else wk, cid)
                            face([(c[0], c[1], z1), (a[0], a[1], z1), (a[0], a[1], zp), (c[0], c[1], zp)],
                                 [(0, 0), (1, 0), (1, 0.1), (0, 0.1)], "core", cid)
                    else:
                        L = math.dist(a, c)
                        face([(a[0], a[1], z0), (c[0], c[1], z0), (c[0], c[1], z1), (a[0], a[1], z1)],
                             [(0, z0 / 4), (L / 4, z0 / 4), (L / 4, z1 / 4), (0, z1 / 4)], "core", cid)
                if top:
                    face([(x, y, z1) for x, y in P], [guv(x, y) for x, y in P],
                         "roofplain" if (h >= 60 and kind == "glass") else "roof", cid)
                    if h > 28 and A > 40 and random.random() < 0.45:      # rooftop plant box
                        s = min(6.0, math.sqrt(A) * 0.45) / 2; hh = random.uniform(1.8, 3.6)
                        bx = [(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s), (cx - s, cy + s)]
                        for i in range(4):
                            a, c = bx[i], bx[(i + 1) % 4]
                            face([(a[0], a[1], z1), (c[0], c[1], z1), (c[0], c[1], z1 + hh), (a[0], a[1], z1 + hh)],
                                 [(0, 0), (s / 2, 0), (s / 2, hh / 4), (0, hh / 4)], "roofkit", cid)
                        face([(x, y, z1 + hh) for x, y in bx], [(0, 0), (1, 0), (1, 1), (0, 1)], "roofkit", cid)
                else:
                    face([(x, y, z1) for x, y in P], [(x / 4, y / 4) for x, y in P], "core", cid)
                if li2 > 0:
                    face([(x, y, z0) for x, y in reversed(P)], [(x / 4, y / 4) for x, y in reversed(P)], "core", cid)
                chunks.append({"b": b["id"], "col": col, "l": li2,
                               "c": [round(cx, 2), round((z0 + z1) / 2, 2), round(-cy, 2)],    # three.js coords
                               "r": round(math.sqrt(A) / 2, 2), "hh": round((z1 - z0) / 2, 2),
                               "v": round(A * (z1 - z0))})
            col += 1
    mb["c1"] = len(chunks)
    meta_b.append(mb)

mesh = bpy.data.meshes.new("city")
bm.to_mesh(mesh)
bm.free()
for m in MATS: mesh.materials.append(m)
city = bpy.data.objects.new("city", mesh)
bpy.context.collection.objects.link(city)

# ---------- terrain ----------
nx = prep["nx"]; G = prep["grid"]; T = prep["terrain"]
tb = bmesh.new()
tuv = tb.loops.layers.uv.new("UVMap")
tch = tb.verts.layers.float.new("_chunk")
verts = []
for j in range(nx):
    for i in range(nx):
        v = tb.verts.new((-HALF + i * G, -HALF + j * G, T[j * nx + i]))
        v[tch] = -1.0
        verts.append(v)
for j in range(nx - 1):
    for i in range(nx - 1):
        q = [verts[j * nx + i], verts[j * nx + i + 1], verts[(j + 1) * nx + i + 1], verts[(j + 1) * nx + i]]
        f = tb.faces.new(q)
        f.material_index = 0
        for loop in f.loops: loop[tuv].uv = guv(loop.vert.co.x, loop.vert.co.y)
gm = bpy.data.meshes.new("ground")
tb.to_mesh(gm); tb.free()
gm.materials.append(MATS[0])
ground = bpy.data.objects.new("ground", gm)
bpy.context.collection.objects.link(ground)

# ---------- export ----------
bpy.ops.export_scene.gltf(filepath=str(OUT / "scene.glb"), export_format="GLB", export_attributes=True,
                          export_image_format="NONE", export_yup=True, export_texcoords=True, export_normals=True,
                          export_materials="EXPORT", export_cameras=False, export_lights=False)
meta = {"id": AID, "size": SIZE, "lat": prep["lat"], "lon": prep["lon"], "buildings": meta_b, "chunks": chunks}
(OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
ntri = sum(len(p.vertices) - 2 for p in mesh.polygons) + sum(len(p.vertices) - 2 for p in gm.polygons)
print(f"{AID}: {len(meta_b)} buildings, {len(chunks)} chunks, ~{ntri} triangles, scene.glb "
      f"{(OUT / 'scene.glb').stat().st_size / 1e6:.1f} MB")

# ---------- preview render (Blender's own look, for checking the model) ----------
if PREVIEW:
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try: sc.render.engine = eng; break
        except TypeError: pass
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.62, 0.72, 0.85, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), 0, math.radians(135))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = 35; cam.data.clip_end = 5000
    cam.location = (420, -520, 360)
    d = -cam.location.normalized() if hasattr(cam.location, "normalized") else None
    import mathutils
    cam.rotation_euler = (mathutils.Vector((40, 60, 20)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(cam); sc.camera = cam
    sc.render.filepath = str(RAW / "preview.png")
    bpy.ops.render.render(write_still=True)
    print("preview:", RAW / "preview.png")
