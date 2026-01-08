import os
import subprocess
import argparse
import shutil

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def obfuscate_with_obfuscator(task_id, obfuscator_jar, jar_in, jar_out_dir, config_path):
    ensure_dir(jar_out_dir)
    jar_out = os.path.join(jar_out_dir, f"{task_id}-obf.jar")

    cmd = [
        "java",
        "-jar", obfuscator_jar,
        "--jar", jar_in,
        "--config", config_path,
    ]

    try:
        subprocess.run(cmd, check=True)
        
        default_generated = f"{task_id}_obf.jar"
        # print(default_generated)
        if os.path.exists(default_generated):
            shutil.move(default_generated, jar_out)
        
        print(f"[SUCCESS] Obfuscated {task_id} → {jar_out}")
        return jar_out
    except subprocess.CalledProcessError:
        print(f"[ERROR] Obfuscator failed for {task_id}")
        return None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jar_dir", default="code_s_task_final/out_jars_j11", help="Directory of original jars")
    p.add_argument("--obf_jar_dir", default="code_s_task_final/obfuscated_jars_j11_obfuscator_full", help="Output directory for obfuscated jars")
    p.add_argument("--obfuscator_jar", default="jar-obfuscator-2.0.0-RC3.jar", help="Path to Obfuscator jar")
    p.add_argument("--config", default="oconfigs/jconfig.yaml", help="Path to obfuscator config file")
    args = p.parse_args()

    ensure_dir(args.obf_jar_dir)

    ids = sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(args.jar_dir)
        if f.endswith(".jar") and os.path.splitext(f)[0].isdigit()
    )

    for task_id in ids:
        jar_in = os.path.join(args.jar_dir, f"{task_id}.jar")
        print(f"[OBF] Obfuscating {task_id}")
        obfuscated_jar = obfuscate_with_obfuscator(
            task_id, args.obfuscator_jar, jar_in, args.obf_jar_dir, args.config
        )
        if not obfuscated_jar:
            continue

if __name__ == "__main__":
    main()
