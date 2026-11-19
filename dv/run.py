#!/usr/bin/env python3
"""Build and run the intact PULP DUT. Run from any directory with Python 3.9+."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter

from results import DIRECTED, NEGATIVE, SEEDS, combine, inspect_run, native_counts

ROOT = Path(__file__).resolve().parents[1]
DV = ROOT / "dv"
UVM_URL = "https://github.com/verilator/uvm.git"
UVM_COMMIT = "656f20d087370a7c742e00188d20bbf30fa95339"
PULP_COMMIT = "dfad6e04d19cc9481d3cd2750b45b970dc61271b"
FLAGS = ["--binary", "--timing", "--assert", "--coverage-user", "--timescale", "1ns/1ps",
         "-Wno-fatal", "--top-module", "tb_top", "+define+UVM_NO_DPI"]
MAKE_FLAGS = ["--verilate-jobs", "1", "--output-groups", "40", "--output-split", "12000",
              "-MAKEFLAGS", "OPT_FAST=-O0 OPT_SLOW=-O0"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def key(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True)+"\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def output(args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def checkout_metadata():
    if not (ROOT/".git").exists():
        return dict(source_form="source tree without .git", git_head=None, git_branch=None, git_dv_status=None)
    return dict(source_form="git checkout", git_head=output(["git","rev-parse","HEAD"]),
                git_branch=output(["git","branch","--show-current"]),
                git_dv_status=output(["git","status","--short","--untracked-files=normal","--","dv","rtl/vendor"]))


def sources():
    paths = [(ROOT / p) for p in (DV / "files.f").read_text().splitlines() if p.strip()]
    paths += list((DV / "uvm").glob("*.svh"))
    paths += [DV / "files.f", DV / "run.py", DV / "results.py"]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def dependency(work):
    specified = os.environ.get("UVM_HOME")
    path = Path(specified).expanduser().resolve() if specified else work / "deps" / "uvm"
    if not specified and not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
            clone = Path(tmp) / "uvm"
            for args in (["git", "init", "-q", str(clone)],
                         ["git", "-C", str(clone), "fetch", "-q", "--depth=1", UVM_URL, UVM_COMMIT],
                         ["git", "-C", str(clone), "checkout", "-q", "--detach", "FETCH_HEAD"]):
                try:
                    subprocess.run(args, check=True, timeout=90)
                except (subprocess.SubprocessError, OSError) as exc:
                    raise ValueError(f"UVM fetch failed. Set UVM_HOME to a clean checkout of {UVM_URL} at {UVM_COMMIT}.") from exc
            if not path.exists():
                clone.rename(path)
    require((path / "src/uvm_pkg.sv").is_file(), f"Missing UVM source in {path}; set UVM_HOME at {UVM_COMMIT}")
    require(output(["git", "rev-parse", "HEAD"], path) == UVM_COMMIT, "Wrong UVM revision")
    require(not output(["git", "status", "--porcelain", "--untracked-files=all", "--", "src"], path),
            "UVM sources differ from the pinned checkout")
    return path, output(["git", "rev-parse", "HEAD:src"], path)


def eda_prefix():
    if os.environ.get("IC_EDA"):
        return [str(Path(os.environ["IC_EDA"]).expanduser().resolve())]
    if shutil.which("verilator"):
        return []
    wrapper = Path.home() / ".local/bin/ic-eda"
    require(wrapper.is_file(), "Place verilator and z3 on PATH or set IC_EDA to an environment wrapper")
    return [str(wrapper)]


def pack(src, dst):
    with src.open("rb") as f, dst.open("wb") as dest:
        with gzip.GzipFile(filename="", fileobj=dest, mode="wb", mtime=0) as g:
            shutil.copyfileobj(f, g)


def build(work, jobs, prefix, uvm, tree, inputs):
    versions = {tool: output(prefix+[tool, "--version"]).splitlines()[0] for tool in ("verilator", "z3", "g++", "make")}
    hdl = {p: h for p, h in inputs.items() if not p.endswith(".py")}
    settings = dict(sources=hdl, versions=versions, uvm_src_tree=tree, flags=FLAGS+MAKE_FLAGS, jobs=jobs)
    build_id = key(settings)
    directory = work / "builds" / build_id
    binary = directory / "obj/Vtb_top"
    record = directory / "build.json"
    if record.exists():
        meta = read(record)
        require(meta["settings"] == settings and meta["id"] == build_id and meta["returncode"] == 0
                and meta["uvm_commit"] == UVM_COMMIT, f"Invalid cached build metadata in {directory}")
        require(sha(binary) == meta["binary_sha256"] and sha(directory/"build.log") == meta["log_sha256"],
                f"Cached binary or compile log changed in {directory}; choose a fresh --work directory")
        return binary, meta
    require(not directory.exists() or not any(directory.iterdir()),
            f"Unsealed or interrupted build cache in {directory}; choose a fresh --work directory")
    directory.mkdir(parents=True, exist_ok=True)
    cmd = prefix + ["verilator"] + FLAGS + [
        f"+incdir+{uvm}/src", "+incdir+dv/uvm", str(uvm/"src/uvm_pkg.sv"),
        "-f", "dv/files.f", "--Mdir", str(binary.parent), "--build-jobs", str(jobs)] + MAKE_FLAGS
    log_path = directory / "build.log"
    print(f"Compiling with {jobs} build jobs → {log_path}", flush=True)
    start = time.monotonic()
    with log_path.open("wb") as log:
        rc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    if rc:
        print(log_path.read_text(errors="replace")[-2400:], file=sys.stderr)
        raise ValueError(f"Compiler exit {rc}, full transcript in {log_path}")
    require(sources() == inputs, "Source changed while compiling")
    require(dependency(work) == (uvm, tree), "UVM changed while compiling")
    meta = dict(id=build_id, settings=settings, command=cmd, cwd=str(ROOT), returncode=rc,
                seconds=round(time.monotonic()-start, 3), binary_sha256=sha(binary),
                log_sha256=sha(log_path), uvm_commit=UVM_COMMIT, uvm_url=UVM_URL)
    save(record, meta)
    return binary, meta


def run_one(out, work, binary, prefix, manifest, case, seed, role, inject=None):
    name = f"{case}-{seed}" + ("" if role == "normal" else f"-{inject or role}")
    log_path = out / (name + ".log")
    with tempfile.TemporaryDirectory(dir=work) as tmp:
        raw_cov = Path(tmp)/"coverage.dat"
        cmd = prefix + [str(binary), f"+CASE={case}", f"+SEED={seed}", f"+verilator+seed+{seed}",
                        f"+verilator+coverage+file+{raw_cov}"]
        if inject:
            cmd.append("+NEG_"+inject.upper())
        start = time.monotonic()
        with log_path.open("wb") as log:
            log.write(f"EVIDENCE|source={manifest['source_key']}|build={manifest['build_id']}|run={name}\n".encode())
            log.flush()
            try:
                rc = subprocess.run(cmd, cwd=tmp, stdout=log, stderr=subprocess.STDOUT, timeout=60).returncode
            except subprocess.TimeoutExpired:
                rc = 124
        row = inspect_run(log_path.read_text(errors="replace"), case, seed, inject, rc)
        row.update(name=name, case=case, seed=seed, role=role, inject=inject, sim_returncode=rc,
                   command=cmd, seconds=round(time.monotonic()-start, 3), log=log_path.name,
                   native_coverage=None)
        if raw_cov.is_file() and raw_cov.stat().st_size:
            packed = out / (name + ".coverage.dat.gz")
            pack(raw_cov, packed)
            row["native_coverage"] = packed.name
        elif not inject:
            row["verdict"] = "FAIL"
            row["problems"].append("native user coverage file missing")
    print(f"{row['verdict']:8s} {name:22s} rc={rc:3d}  {row['scoreboard']}  {' '.join(row['problems'])}", flush=True)
    return row


def replay_agrees(rows):
    normal = [r for r in rows if r["case"] == "random" and r["role"] == "normal"]
    replay = next(r for r in rows if r["role"] == "replay")
    first = next(r for r in normal if r["seed"] == replay["seed"])
    fields = ("stimulus_sha256", "scoreboard", "bins", "bus")
    return (all(first[f] == replay[f] for f in fields) and first["stimulus_sha256"]
            and len({r["stimulus_sha256"] for r in normal}) == len(SEEDS))


def suite():
    return ([(c, 17, "normal", None) for c in DIRECTED] +
            [("random", s, "normal", None) for s in SEEDS] +
            [("random", SEEDS[0], "replay", None)] +
            [("baud", 17, "control", fault) for fault in NEGATIVE])


def write_seal(directory):
    entries = [f"{sha(p)}  {p.name}" for p in sorted(directory.iterdir()) if p.is_file() and p.name != "SHA256SUMS"]
    (directory/"SHA256SUMS").write_text("\n".join(entries)+"\n", encoding="ascii")


def merged_native(directory, rows):
    counts = Counter()
    for row in rows:
        if not row["inject"] and row["native_coverage"]:
            native = native_counts(gzip.decompress((directory / row["native_coverage"]).read_bytes()), row["bins"])
            if row["role"] == "normal" and row["verdict"] == "PASS":
                counts.update(native)
    groups = {}
    for name, count in counts.items():
        point, label = name.rsplit(".", 1)
        groups.setdefault(point, {})[label] = count
    return {point: dict(hit=sum(v > 0 for v in bins.values()), total=len(bins), samples=sum(bins.values()), bins=bins)
            for point, bins in groups.items()}


def verify(directory):
    actual = {p.name: sha(p) for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS"}
    seal = {}
    for line in (directory/"SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        require(name not in seal, f"Repeated hash for {name}")
        seal[name] = digest
    require(actual == seal, "Evidence file set or SHA-256 mismatch")
    m, report = read(directory/"manifest.json"), read(directory/"regression.json")
    meta = read(directory/"build.json")
    require(m["sources"] == sources() and m["source_key"] == key(sources()), "DUT/TB/runner differs from evidence")
    require(meta["settings"]["sources"] == {p: d for p,d in m["sources"].items() if not p.endswith(".py")}
            and meta["id"] == key(meta["settings"]) == m["build_id"] and meta["uvm_commit"] == UVM_COMMIT
            and m["binary_sha256"] == meta["binary_sha256"], "Build identity mismatch")
    require(hashlib.sha256(gzip.decompress((directory/"build.log.gz").read_bytes())).hexdigest() == meta["log_sha256"],
            "Raw compile log mismatch")
    for r in report["runs"]:
        raw = (directory/r["log"]).read_text(errors="replace")
        require(raw.splitlines()[0] == f"EVIDENCE|source={m['source_key']}|build={m['build_id']}|run={r['name']}",
                f"Run/log identity mismatch for {r['name']}")
        decoded = inspect_run(raw, r["case"], r["seed"], r["inject"], r["sim_returncode"])
        require(all(r[f] == value for f, value in decoded.items()), f"Report/log disagreement for {r['name']}")
        require(r["verdict"] in {"PASS", "DETECTED"}, f"Failed run {r['name']}")
        if not r["inject"]:
            require(r["native_coverage"] in seal, "Missing native covergroup evidence")
    require(report["groups"] == combine(report["runs"]), "Merged bins differ from raw reports")
    require(report["native"] == merged_native(directory, report["runs"]), "Native covergroup totals differ")
    if m["action"] == "regress":
        require([(r["case"],r["seed"],r["role"],r["inject"]) for r in report["runs"]] == suite(), "Incomplete regression matrix")
        require(replay_agrees(report["runs"]), "Replay differs or seeds generated identical stimulus")
        require(all(g["hit"] == g["total"] for g in report["groups"].values()), "A declared functional bin is unhit")
    print(f"Verified {len(seal)} SHA-256 entries, source key, compiler log, and {len(report['runs'])} decoded run logs.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("regress","run","verify"))
    p.add_argument("--work", type=Path, default=DV/".work", help="UVM cache, C++ objects and default run outputs")
    p.add_argument("--out", type=Path, help="empty evidence destination, or existing evidence for verify")
    p.add_argument("--case", choices=DIRECTED+("random",), default="baud")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--inject", choices=tuple(NEGATIVE), help="single baud run; shell exit 1 on detected mismatch")
    p.add_argument("--jobs", type=int, choices=(1,2,3), default=2)
    args = p.parse_args()
    if args.action == "verify":
        verify((args.out or DV/"evidence").resolve())
        return 0
    require(0 < args.seed < 2**31, "--seed must be between 1 and 2147483647")
    require(not args.inject or (args.action == "run" and args.case == "baud"), "Use --inject with run --case baud")
    work = args.work.expanduser().resolve()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = (args.out or work/"runs"/stamp).resolve()
    require(not out.exists() or not any(out.iterdir()), f"Evidence destination must be empty: {out}")
    out.mkdir(parents=True,exist_ok=True)
    work.mkdir(parents=True,exist_ok=True)
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, resource.getrlimit(resource.RLIMIT_CORE)[1]))
    inputs = sources()
    prefix = eda_prefix()
    uvm, tree = dependency(work)
    binary, meta = build(work, args.jobs, prefix, uvm, tree, inputs)
    manifest = dict(schema=1, action=args.action, utc=stamp, **checkout_metadata(), pulp_commit=PULP_COMMIT,
                    source_key=key(inputs), sources=inputs, binary_sha256=sha(binary), build_id=meta["id"],
                    invocation=sys.argv, cwd=os.getcwd())
    save(out/"manifest.json", manifest)
    save(out/"build.json", meta)
    pack(binary.parent.parent/"build.log", out/"build.log.gz")
    cases = suite() if args.action == "regress" else [(args.case,args.seed,"control" if args.inject else "normal",args.inject)]
    rows = [run_one(out,work,binary,prefix,manifest,*case) for case in cases]
    require(inputs == sources() and dependency(work) == (uvm,tree) and sha(binary) == manifest["binary_sha256"],
            "Simulation inputs changed during execution")
    groups = combine(rows)
    save(out/"regression.json", dict(runs=rows,groups=groups,native=merged_native(out,rows)))
    write_seal(out)
    print(f"Evidence: {out}")
    verify(out)
    if args.action == "regress":
        for name, g in groups.items():
            print(f"{name:8s} {g['hit']}/{g['total']} bins; {g['samples']} samples")
    return 1 if args.inject else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"DV failed: {error}", file=sys.stderr)
        sys.exit(2)
