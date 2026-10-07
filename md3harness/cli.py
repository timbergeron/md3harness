import argparse
import hashlib
import json
from pathlib import Path
import sys

from .format import encode_scene, loads
from .quality import check, inspect

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2)+"\n")

def export_scene(scene, output, asset_root=None, manifest=None, strict=False, profile=None):
    profile = profile or scene.get("profile", "portable")
    data = encode_scene(scene, profile)
    report = check(loads(data, profile), asset_root, manifest)
    report.update(model=Path(output).name, sha256=hashlib.sha256(data).hexdigest())
    if not report["passed"] or (strict and report["issues"]):
        raise ValueError("export rejected:\n"+"\n".join(f"{i['code']}: {i['message']} ({i.get('surface', '')}, pose {i.get('frame', '-')})" for i in report["issues"]))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix+".tmp")
    temporary.write_bytes(data)
    temporary.replace(output)
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(description="Author and inspect MD3 assets for QSS-M")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("check", help="Inspect every pose in an exported MD3")
    p.add_argument("model", type=Path)
    p.add_argument("--asset-root", type=Path, help="Game root containing shader textures")
    p.add_argument("--manifest", type=Path)
    p.add_argument("--json", type=Path, help="Write a machine-readable quality report")
    p.add_argument("--strict", action="store_true", help="Treat review warnings as failures")
    p.add_argument("--profile", choices=("portable", "qssm"), default="qssm", help="Binary limits to accept")
    p = commands.add_parser("build", help="Export a versioned scene JSON file")
    p.add_argument("scene", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--asset-root", type=Path)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--profile", choices=("portable", "qssm"), help="Export limits; defaults to scene profile or portable")
    p = commands.add_parser("preview", help="Build an isolated Quake studio and capture actual QSS-M views")
    p.add_argument("--manifest", type=Path, help="Asset contract for the exact model under review")
    p.add_argument("model", type=Path)
    p.add_argument("--asset-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True, help="New, empty review directory")
    p.add_argument("--engine", type=Path, required=True)
    p.add_argument("--basedir", type=Path, required=True)
    for name in ("fteqcc", "qbsp", "light", "vis"):
        p.add_argument("--"+name, type=Path, required=True)
    p.add_argument("--frames", default="0", help="Comma-separated pose indices to capture")
    p.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            from .preview import preview
            preview(args)
            print(f"Review: {args.output.resolve() / 'index.html'}")
            return 0
        manifest = json.loads(args.manifest.read_text()) if args.manifest else None
        if args.command == "build":
            report = export_scene(json.loads(args.scene.read_text()), args.output, args.asset_root, manifest, args.strict, args.profile)
            print(f"Exported {args.output}: {report['frames']} poses, {len(report['surfaces'])} surfaces")
            return 0
        report = inspect(args.model, args.asset_root, manifest, args.profile)
        if args.json:
            save_json(args.json, report)
        passed = report['passed'] and not (args.strict and report['issues'])
        print(f"{'PASS' if passed else 'FAIL'} {args.model}: {report['frames']} poses, {len(report['surfaces'])} surfaces")
        for issue in report["issues"]:
            print(f"  {issue['severity']}: {issue['code']}: {issue['message']} {issue.get('surface', '')}")
        return 0 if passed else 1
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        print(f"md3harness: {exc}", file=sys.stderr)
        return 1
