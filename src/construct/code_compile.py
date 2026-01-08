import os
import subprocess
import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def compile_and_package(task_id, raw_dir, out_class_dir, out_jar_dir):
    source_dir = os.path.join(raw_dir, task_id)
    out_dir = os.path.join(out_class_dir, task_id)
    main_java = os.path.join(source_dir, "Main.java")

    if not os.path.exists(main_java):
        print(f"[SKIP] Main.java not found for {task_id}, skipped.")
        return task_id, None  # None 表示跳过

    ensure_dir(out_dir)
    try:
        subprocess.run(["javac", "-encoding", "UTF-8", "-d", out_dir, main_java], check=True)
        print(f"[COMPILE] {task_id} compiled successfully.")
        jar_path = os.path.join(out_jar_dir, f"{task_id}.jar")
        subprocess.run(["jar", "cf", jar_path, "-C", out_dir, "."], check=True)
        print(f"[JAR] {task_id} packaged as {jar_path}")
        return task_id, True
    except subprocess.CalledProcessError:
        print(f"[ERROR] Compile or package failed for {task_id}")
        return task_id, False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_dir", default="code_s_task_final/rawcode")
    parser.add_argument("--out_class_dir", default="code_s_task_final/out_classes_j11")
    parser.add_argument("--out_jar_dir", default="code_s_task_final/out_jars_j11")
    args = parser.parse_args()

    ensure_dir(args.out_class_dir)
    ensure_dir(args.out_jar_dir)

    all_ids = sorted([
        d for d in os.listdir(args.raw_dir)
        if os.path.isdir(os.path.join(args.raw_dir, d)) and d.isdigit()
    ], key=lambda x: int(x))

    compiled_ids = []
    failed_ids = []
    processed_ids = []

    with ProcessPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(compile_and_package, task_id, args.raw_dir, args.out_class_dir, args.out_jar_dir): task_id
            for task_id in all_ids
        }

        for future in as_completed(futures):
            task_id, result = future.result()
            if result is None:
                continue  # skip
            processed_ids.append(task_id)
            if result is True:
                compiled_ids.append(task_id)
            else:
                failed_ids.append(task_id)

    summary = {
        "total": len(processed_ids),
        "compiled_success": len(compiled_ids),
        "compiled_failed": len(failed_ids),
        "success_ids": compiled_ids,
        "failed_ids": failed_ids
    }

    with open("compile_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[SUMMARY] {summary['compiled_success']} / {summary['total']} tasks compiled successfully.")
    print("[OUTPUT] compile_summary.json written.")

if __name__ == "__main__":
    main()
