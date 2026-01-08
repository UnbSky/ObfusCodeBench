import os
import subprocess
import argparse
from multiprocessing import Pool

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def decompile_cfr(task_id, obf_jar_path, decomp_dir, cfr_jar):
    out_dir = os.path.join(decomp_dir, task_id)
    ensure_dir(out_dir)
    try:
        subprocess.run(["java", "-jar", cfr_jar, obf_jar_path, "--outputdir", out_dir], check=True)
        with open(os.path.join(out_dir, "DECOMPILER.txt"), "w") as f:
            f.write("cfr\n")
        return task_id, True
    except subprocess.CalledProcessError:
        return task_id, False

def decompile_jadx(task_id, obf_jar_path, decomp_dir, jadx_jar):
    out_dir = os.path.join(decomp_dir, task_id)
    ensure_dir(out_dir)
    try:
        subprocess.run([
            "java",
            "-cp", jadx_jar,
            "jadx.cli.JadxCLI",
            "-d", out_dir,
            obf_jar_path
        ], check=True)
        with open(os.path.join(out_dir, "DECOMPILER.txt"), "w") as f:
            f.write("jadx\n")
        return task_id, True
    except subprocess.CalledProcessError:
        return task_id, False

def decompile_worker(args):
    task_id, obf_jar_path, decomp_dir, decompiler, cfr_jar, jadx_jar = args
    if decompiler == "cfr":
        return decompile_cfr(task_id, obf_jar_path, decomp_dir, cfr_jar)
    elif decompiler == "jadx":
        return decompile_jadx(task_id, obf_jar_path, decomp_dir, jadx_jar)
    else:
        return task_id, False

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--obf_jar_dir", default="./code_s_task_final/obfuscated_jars_j11_obfuscator_junk")
    p.add_argument("--decomp_dir", default="./code_s_task_final/decompiled_jars_j11_obfuscator_junk")
    p.add_argument("--cfr_jar", default="cfr-0.152.jar")
    p.add_argument("--jadx_jar", default="jadx-1.5.2-all.jar")
    p.add_argument("--decompiler", choices=["cfr", "jadx"], default="jadx")
    p.add_argument("--num_workers", type=int, default=10, help="Number of parallel decompilation workers")
    args = p.parse_args()

    ensure_dir(args.decomp_dir)

    ids = sorted(
        os.path.splitext(f)[0].replace("-obf", "")
        for f in os.listdir(args.obf_jar_dir)
        if f.endswith("-obf.jar") and os.path.splitext(f)[0].replace("-obf", "").isdigit()
    )

    tasks = [
        (task_id,
         os.path.join(args.obf_jar_dir, f"{task_id}-obf.jar"),
         args.decomp_dir,
         args.decompiler,
         args.cfr_jar,
         args.jadx_jar)
        for task_id in ids
    ]

    with Pool(processes=args.num_workers) as pool:
        results = pool.map(decompile_worker, tasks)

    for task_id, success in results:
        if success:
            print(f"[DONE] {task_id}")
        else:
            print(f"[SKIP] {task_id} (decompilation failed)")

if __name__ == "__main__":
    main()
