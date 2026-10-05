"""Real-engine review, isolated from the user's Quake installation."""
import hashlib
import html
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

from .cli import save_json
from .format import load
from .materials import resolve_texture, write_tga
from .quality import inspect
from .png import changed_pixels
from .math3 import cross, dot, unit
from .studio import brush, nearest, palette_from, texture, write_wad

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(command, cwd, log, timeout=120, env=None):
    try:
        result = subprocess.run([str(x) for x in command], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or b""
        log.write_text(output.decode(errors="replace") if isinstance(output, bytes) else output)
        raise ValueError(f"command timed out; see {log}") from exc
    log.write_text(result.stdout)
    if result.returncode:
        raise ValueError(f"command failed ({result.returncode}); see {log}\n{result.stdout[-2000:]}")
    return result.stdout

def stage_paks(basedir, engine, runtime):
    id1 = runtime/"id1"
    id1.mkdir()
    found = False
    for name in ("pak0.pak", "pak1.pak"):
        source = basedir/"id1"/name
        if source.is_file():
            (id1/name).symlink_to(source)
            found = True
    if not found:
        raise ValueError("--basedir must contain a licensed Quake id1/pak0.pak")
    for name in ("qssm.pak", "quakespasm.pak"):
        source = engine.parent/name
        if source.is_file():
            (runtime/name).symlink_to(source)

def cameras(model):
    lo, hi = model.frames[0]["min"], model.frames[0]["max"]
    dims = [b-a for a, b in zip(lo, hi)]
    span = max(*dims, 16)
    target = (0, 0, dims[2]/2)
    origin = (-(lo[0]+hi[0])/2, -(lo[1]+hi[1])/2, -lo[2])
    corners = [(x+origin[0], y+origin[1], z+origin[2]) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    tan_horizontal = math.tan(math.radians(75/2))
    tan_vertical = tan_horizontal*720/1280
    result = []
    for name, delta in (("front", (span*.9, 0, span*.12)),
                        ("back", (-span*.9, 0, span*.12)),
                        ("quarter", (span*.95, -span*.65, span*.4)),
                        ("detail", (max(span*.22, 24), 0, span*.05))):
        aim = (0, dims[1]*.43, dims[2]*.64) if name == "detail" else target
        if name != "detail":
            outward = unit(delta)
            right = unit(cross((0, 0, 1), outward))
            up = cross(outward, right)
            distance = 24
            for corner in corners:
                relative = tuple(a-b for a, b in zip(corner, aim))
                distance = max(distance, dot(relative, outward)+max(abs(dot(relative, right))/tan_horizontal, abs(dot(relative, up))/tan_vertical))
            delta = tuple(x*distance*1.15 for x in outward)
        position = tuple(a+b for a, b in zip(aim, delta))
        direction = tuple(a-b for a, b in zip(aim, position))
        angles = (-math.degrees(math.atan2(direction[2], math.hypot(*direction[:2]))),
                  math.degrees(math.atan2(direction[1], direction[0])), 0)
        result.append((name, position, angles))
    return origin, result

def qc_source(model, origin, views):
    def vector(v):
        return "'"+" ".join(f"{x:.6f}" for x in v)+"'"
    branches = "\n".join(f"    if (cvar(\"harness_view\") == {i}) {{ setorigin(self, {vector(p)}); self.angles = {vector(a)}; }}" for i, (_, p, a) in enumerate(views))
    low = tuple(min(f["min"][a] for f in model.frames) for a in range(3))
    high = tuple(max(f["max"][a] for f in model.frames) for a in range(3))
    return f'''// SPDX-License-Identifier: GPL-2.0-or-later
entity review_model;
.float review_started;
.float review_ready;
.float captured;
void() main = {{}};
void() StartFrame = {{
    local float pose;
    if (!review_model) return;
    pose = cvar("harness_frame");
    if (cvar("harness_animate")) {{
        pose = floor(time * cvar("harness_fps"));
        pose = pose - floor(pose / {len(model.frames)}) * {len(model.frames)};
    }}
    review_model.frame = pose;
}};
void() ClientConnect = {{}};
void() ClientDisconnect = {{}};
void() ClientKill = {{}};
void() SetNewParms = {{}};
void() SetChangeParms = {{}};
void() PlayerPreThink = {{}};
void() worldspawn = {{
    precache_model("progs/review.md3");
    lightstyle(0, "m");
    review_model = spawn();
    review_model.classname = "md3harness_model";
    setmodel(review_model, "progs/review.md3");
    setsize(review_model, {vector(low)}, {vector(high)});
    setorigin(review_model, {vector(origin)});
    review_model.frame = cvar("harness_frame");
    review_model.movetype = MOVETYPE_NONE;
    review_model.solid = SOLID_NOT;
    dprint("MD3HARNESS MODEL progs/review.md3 FRAME ", ftos(review_model.frame), "\\n");
}};
void() info_player_start = {{}};
void() light = {{ remove(self); }};
void() PutClientInServer = {{
    self.movetype = MOVETYPE_NONE;
    if (!cvar("harness_capture")) self.movetype = MOVETYPE_NOCLIP;
    self.solid = SOLID_NOT;
    self.health = 100;
    self.view_ofs = '0 0 0';
    self.weaponmodel = "";
    self.review_started = time;
    self.review_ready = 1;
    self.captured = 0;
{branches}
    self.fixangle = 1;
    self.v_angle = self.angles;
}};
void() PlayerPostThink = {{
    if (!self.review_ready || !cvar("harness_capture")) return;
    if (time - self.review_started > 0.8 && !self.captured) {{
        dprint("MD3HARNESS CAPTURE frame=", ftos(review_model.frame), " view=", ftos(cvar("harness_view")), "\\n");
        stuffcmd(self, "screenshot png\\n");
        self.captured = 1;
    }}
    if (time - self.review_started > 1.05 && self.captured == 1) {{
        stuffcmd(self, "r_drawentities 0\\n");
        self.captured = 2;
    }}
    if (time - self.review_started > 1.3 && self.captured == 2) {{
        dprint("MD3HARNESS BASELINE\\n");
        stuffcmd(self, "screenshot png\\n");
        self.captured = 3;
    }}
    if (time - self.review_started > 1.8) {{
        dprint("MD3HARNESS COMPLETE\\n");
        localcmd("quit\\n");
    }}
}};
'''

def studio_map(wad):
    lines = ['{', '"classname" "worldspawn"', '"message" "MD3 Harness / Studio"',
             f'"wad" "{wad.name}"', '"_minlight" "80"']
    walls = [((-2048, -2048, -64), (2048, 2048, 0)),
             ((-2080, -2080, -64), (-2048, 2080, 2048)),
             ((2048, -2080, -64), (2080, 2080, 2048)),
             ((-2048, -2080, -64), (2048, -2048, 2048)),
             ((-2048, 2048, -64), (2048, 2080, 2048)),
             ((-2048, -2048, 2048), (2048, 2048, 2080))]
    lines.extend(brush(a, b, "studio_floor" if i == 0 else "studio_wall") for i, (a, b) in enumerate(walls))
    lines.append('}')
    lines.append('{\n"classname" "info_player_start"\n"origin" "256 0 96"\n}')
    for origin in ("180 -240 380", "-180 240 300", "0 0 700"):
        lines.append('{\n"classname" "light"\n"origin" "'+origin+'"\n"light" "650"\n}')
    return "\n".join(lines)+"\n"

def preview(args):
    args.model = args.model.resolve()
    args.asset_root = args.asset_root.resolve()
    args.output = args.output.resolve()
    for name in ("engine", "basedir", "fteqcc", "qbsp", "vis", "light"):
        setattr(args, name, getattr(args, name).resolve())
    quality = inspect(args.model, args.asset_root)
    if not quality["passed"]:
        raise ValueError("model fails quality checks; run check before preview")
    model = load(args.model)
    frames = list(dict.fromkeys(int(x) for x in args.frames.split(",")))
    if not frames or any(x < 0 or x >= len(model.frames) for x in frames):
        raise ValueError("requested capture frame outside the model")
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("review output must be empty; choose a new directory to avoid stale captures")
    args.output.mkdir(parents=True, exist_ok=True)
    work = args.output/"work"
    work.mkdir()
    runtime = args.output/"runtime"
    runtime.mkdir()
    game = runtime/"md3review"
    (game/"progs").mkdir(parents=True)
    (game/"maps").mkdir()
    shutil.copyfile(args.model, game/"progs/review.md3")
    if digest(game/"progs/review.md3") != quality["sha256"]:
        raise ValueError("model changed after inspection; start a fresh review")
    model = load(game/"progs/review.md3")
    for shader in quality["textures"]:
        path = resolve_texture(args.asset_root, shader)
        target = game/path.relative_to(args.asset_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if digest(target) != quality["textures"][shader]["sha256"]:
            raise ValueError("texture changed after inspection; start a fresh review")
    stage_paks(args.basedir, args.engine, runtime)
    palette = palette_from(args.basedir)
    textures = {}
    for name, colour in (("studio_floor", (146, 151, 152)), ("studio_wall", (176, 184, 186))):
        rgba = [(tuple(max(0, c-(4 if (x//16+y//16)%2 else 0)) for c in colour)+(255,)) for y in range(64) for x in range(64)]
        textures[name] = texture(name, 64, 64, [nearest(palette, p[:3]) for p in rgba])
        write_tga(game/"textures/md3studio"/(name+".tga"), 64, 64, rgba)
    wad = work/"studio.wad"
    write_wad(wad, textures)
    mapfile = work/"md3studio.map"
    mapfile.write_text(studio_map(wad))
    origin, views = cameras(model)
    shutil.copyfile(Path(__file__).parent/"qc/defs.qc", work/"defs.qc")
    (work/"studio.qc").write_text(qc_source(model, origin, views))
    (work/"progs.src").write_text(str(game/"progs.dat")+"\ndefs.qc\nstudio.qc\n")
    output = run([args.fteqcc, "-Wall", "-srcfile", "progs.src"], work, args.output/"qc.log")
    if re.search(r"\b(warning|error)\b", output, re.I):
        raise ValueError("preview QuakeC emitted diagnostics; see qc.log")
    bsp = game/"maps/md3studio.bsp"
    run([args.qbsp, "-nopercent", "-leaktest", mapfile, bsp], work, args.output/"qbsp.log")
    run([args.vis, "-threads", "2", bsp], work, args.output/"vis.log")
    run([args.light, "-threads", "2", "-extra4", bsp], work, args.output/"light.log")
    summary = dict(schema="md3harness.preview.v1", complete=False, quality=quality,
                   engine_sha256=digest(args.engine), model_sha256=digest(game/"progs/review.md3"),
                   progs_sha256=digest(game/"progs.dat"), bsp_sha256=digest(bsp), captures=[])
    save_json(args.output/"review.json", summary)
    (game/"studio-live.cfg").write_text("set harness_capture 0\nset harness_frame 0\nset harness_animate 0\nset harness_fps 10\nviewsize 120\ncrosshair 0\nr_drawviewmodel 0\nmap md3studio\n")
    env = dict(os.environ, SDL_VIDEO_DRIVER="offscreen", SDL_AUDIO_DRIVER="dummy", LIBGL_ALWAYS_SOFTWARE="1", LP_NUM_THREADS="2")
    for f in frames:
        for view, (name, _, _) in enumerate(views):
            if f != frames[0] and name != "quarter":
                continue
            label = f"pose{f:03d}-{name}"
            cfg = dict(developer=1, host_framerate=.02, host_maxfps=100, viewsize=120, crosshair=0,
                       r_drawviewmodel=0, r_drawentities=1, r_shadows=0, r_lerpmodels=0, scr_showfps=0, scr_showclock=0, scr_sbaralpha=0,
                       harness_frame=f, harness_view=view, harness_capture=1, harness_animate=0, fov=75, gamma=1, contrast=1,
                       con_notifytime=0, con_notifylines=0, scr_fade=0, scr_conspeed=100000)
            (game/"fixture.cfg").write_text("".join(f"set {key} {value}\n" for key, value in cfg.items())+"map md3studio\n")
            existing = set((game/"screenshots").glob("*.png"))
            output = run([args.engine, "-basedir", runtime, "-game", "md3review", "-nohome", "-nolan", "-noudp",
                          "-window", "-width", "1280", "-height", "720", "-nojoy", "-nomouse", "-fsaa", "4", "+exec", "fixture.cfg"],
                         runtime, args.output/(label+".log"), args.timeout, env)
            required = ("SpawnServer: md3studio", f"MD3HARNESS MODEL progs/review.md3 FRAME {f}",
                        f"MD3HARNESS CAPTURE frame={f} view={view}", "MD3HARNESS BASELINE", "MD3HARNESS COMPLETE")
            if any(x not in output for x in required) or re.search(r"Playing demo|Host_Error|Sys_Error|Program error|Mod_LoadMD3Model:|(?:Couldn't|could not) load[^\n]*progs/review", output, re.I):
                raise ValueError(f"{label}: target scene/model was not confirmed; inspect its log")
            images = set((game/"screenshots").glob("*.png"))-existing
            if len(images) != 2:
                raise ValueError(f"{label}: expected a new model capture and baseline")
            capture, baseline = sorted(images)
            width, height = struct.unpack_from(">II", capture.read_bytes(), 16)
            if (width, height) != (1280, 720):
                raise ValueError(f"{label}: unexpected capture size {width}x{height}")
            destination = args.output/(label+".png")
            shutil.copyfile(capture, destination)
            difference = changed_pixels(capture, baseline)
            if difference < 25:
                raise ValueError(f"{label}: only {difference} foreground pixels; model is absent or unreadable")
            background = args.output/(label+"-baseline.png")
            shutil.copyfile(baseline, background)
            summary["captures"].append(dict(frame=f, view=name, file=destination.name, sha256=digest(destination),
                                            foreground_pixels=difference, baseline=background.name, baseline_sha256=digest(background)))
            save_json(args.output/"review.json", summary)
            print(f"Captured {label}", flush=True)
    summary["complete"] = True
    save_json(args.output/"review.json", summary)
    cards = "".join(f'<figure><a href="{html.escape(c["file"])}"><img src="{html.escape(c["file"])}" loading="lazy"></a><figcaption>Pose {c["frame"]} · {html.escape(c["view"])}</figcaption></figure>' for c in summary["captures"])
    (args.output/"index.html").write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MD3 Harness review</title>
<style>body{{font:16px system-ui;background:#111b24;color:#e6edf1;margin:3vw}}h1{{font-weight:500}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:20px}}figure{{margin:0;background:#1c2b35;border-radius:8px;overflow:hidden}}img{{width:100%;display:block}}figcaption{{padding:14px}}a{{color:#92d1ff}}code{{word-break:break-all}}</style>
<h1>{html.escape(args.model.name)}</h1><p>Actual QSS-M renders · {len(model.frames)} poses · {len(model.surfaces)} surfaces · <a href="review.json">Quality and provenance report</a></p><p>Model SHA-256: <code>{summary["model_sha256"]}</code></p><main>{cards}</main></html>''')
