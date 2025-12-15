import os
import subprocess
import argparse

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def write_proguard_config(task_id, jar_dir, obf_jar_dir, config_dir, java_path):
    config_path = os.path.join(config_dir, f"{task_id}.pro")
    input_jar = os.path.join(jar_dir, f"{task_id}.jar")
    output_jar = os.path.join(obf_jar_dir, f"{task_id}-obf.jar")
    content = f"""-injars ../../{input_jar}
-outjars ../../{output_jar}
-libraryjars {java_path}

-dontwarn
-overloadaggressively
-dontnote jdk.internal.**
-dontwarn jdk.internal.**

-keep public class * {{
    public static void main(java.lang.String[]);
}}

-keep class * {{
    public static void main(java.lang.String[]);
}}"""
    with open(config_path, "w") as f:
        f.write(content)
    return config_path

def obfuscate(task_id, proguard_jar, jar_dir, obf_jar_dir, config_dir, java_path):
    config_path = os.path.basename(write_proguard_config(
        task_id, jar_dir, obf_jar_dir, config_dir, java_path))
    ensure_dir(obf_jar_dir)
    try:
        subprocess.run([
            "java", "-jar", proguard_jar, f"@{config_path}"
        ], check=True, cwd=config_dir)
        return True
    except subprocess.CalledProcessError:
        print(f"[ERROR] Obfuscation failed for {task_id}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jar_dir", default="code_s_task_new/out_jars_j11", help="Directory of original jars")
    parser.add_argument("--obf_jar_dir", default="code_s_task_new/obfuscated_jars_j11_proguard", help="Output directory for obfuscated jars")
    parser.add_argument("--config_dir", default="code_s_task_new/obfuscated_configs_proguard", help="Directory to store proguard config files")
    parser.add_argument("--java_path", default="/usr/lib/jvm/java-11-openjdk-amd64/jmods/java.base.jmod", help="Path to java.base.jmod")
    parser.add_argument("--proguard_jar", default="/home/cike/ytc/code_rewrite/proguard-7.7.0/lib/proguard.jar", help="Path to proguard.jar")
    args = parser.parse_args()

    ensure_dir(args.config_dir)
    ensure_dir(args.obf_jar_dir)

    jar_files = sorted([
        f for f in os.listdir(args.jar_dir)
        if f.endswith(".jar") and f[:-4].isdigit()
    ], key=lambda x: int(x[:-4]))

    for jar_file in jar_files:
        task_id = jar_file[:-4]
        print(f"[OBFUSCATE] Processing {task_id}...")
        obfuscate(task_id, args.proguard_jar, args.jar_dir, args.obf_jar_dir, args.config_dir, args.java_path)

if __name__ == "__main__":
    main()
