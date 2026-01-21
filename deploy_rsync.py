import os
import hashlib
import json
import subprocess
import sys
import shlex

# Configuration via Environment Variables
HOST = os.environ.get('SFTP_HOST')
USER = os.environ.get('SFTP_USER')
PASSWORD = os.environ.get('SFTP_PASS')
PORT = os.environ.get('SFTP_PORT', '22')
REMOTE_BASE_DIR = os.environ.get('TARGET_DIR')
LOCAL_BASE_DIR = 'build/server'
MANIFEST_FILENAME = 'deploy_manifest.json'

def calculate_hash(filepath):
    """Calculates MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_local_files_info(base_dir):
    """
    Scans local directory and returns a dict: 
    { 'relative/path': {'hash': 'md5...', 'size': 1234} }
    """
    files_info = {}
    if not os.path.exists(base_dir):
        print(f"Error: Local directory '{base_dir}' does not exist.")
        sys.exit(1)
        
    for root, _, files in os.walk(base_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_dir).replace(os.path.sep, '/')
            
            # Skip manifest itself if generated locally
            if rel_path == MANIFEST_FILENAME:
                continue
                
            stats = os.stat(full_path)
            file_hash = calculate_hash(full_path)
            
            files_info[rel_path] = {
                'hash': file_hash,
                'size': stats.st_size
            }
    return files_info

def run_cmd(cmd_list, env=None, check=True, capture_output=False):
    """Runs a subprocess command with hidden password in logs."""
    display_cmd = " ".join(cmd_list).replace(PASSWORD, "*****") if PASSWORD else " ".join(cmd_list)
    print(f"Executing: {display_cmd}")
    sys.stdout.flush()

    if capture_output:
        # For capturing output (like getting manifest), we wait for completion
        try:
            result = subprocess.run(
                cmd_list, 
                env=env, 
                check=check, 
                text=True,
                capture_output=True
            )
            return result
        except subprocess.CalledProcessError as e:
            print(f"Command failed with exit code {e.returncode}")
            print(f"Stderr: {e.stderr}")
            if check:
                sys.exit(e.returncode)
            return e
    else:
        # For long running commands (rsync), we stream output
        process = subprocess.Popen(
            cmd_list,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr into stdout
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            print(line, end='')
            sys.stdout.flush()

        process.wait()

        if check and process.returncode != 0:
            print(f"Command failed with exit code {process.returncode}")
            sys.exit(process.returncode)
        
        return process

def main():
    if not all([HOST, USER, PASSWORD, REMOTE_BASE_DIR]):
        print("Error: Missing required environment variables (SFTP_HOST, SFTP_USER, SFTP_PASS, TARGET_DIR).")
        sys.exit(1)

    print(f"Preparing deployment to {HOST}:{PORT}...")
    
    # 1. State Calculation
    print("Scanning local files...")
    local_state = get_local_files_info(LOCAL_BASE_DIR)
    print(f"Found {len(local_state)} local files.")

    # Prepare environment for commands (inject SSHPASS)
    env = os.environ.copy()
    env['SSHPASS'] = PASSWORD
    
    # Common SSH flags
    ssh_opts = ["-p", str(PORT), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15"]
    ssh_base_cmd = ["sshpass", "-e", "ssh"] + ssh_opts + [f"{USER}@{HOST}"]

    # 1.5 Ensure Remote Directory Exists
    print(f"Ensuring remote directory structure: {REMOTE_BASE_DIR}")
    mkdir_cmd = ssh_base_cmd + [f"mkdir -p {shlex.quote(REMOTE_BASE_DIR)}"]
    run_cmd(mkdir_cmd, env=env, check=True)

    # 2. Get Remote Manifest
    manifest_path = f"{REMOTE_BASE_DIR}/{MANIFEST_FILENAME}"
    print(f"Fetching remote manifest from {manifest_path}...")
    
    cat_cmd = ssh_base_cmd + [f"cat {shlex.quote(manifest_path)}"]
    remote_state = {}
    
    res = run_cmd(cat_cmd, env=env, check=False, capture_output=True)
    if res.returncode == 0:
        try:
            remote_state = json.loads(res.stdout)
            print(f"Loaded remote manifest. Known remote files: {len(remote_state)}")
        except json.JSONDecodeError:
            print("Remote manifest corrupted. Proceeding with full sync.")
    else:
        print("Remote manifest not found. Proceeding with full sync.")

    # 3. Calculate Deletions
    # Only delete files that are in the remote manifest (managed by us) but not in local state.
    files_to_delete = []
    for rel_path in remote_state:
        if rel_path not in local_state:
            files_to_delete.append(rel_path)
    
    print(f"Found {len(files_to_delete)} files to delete.")

    # 4. Execute Deletions
    if files_to_delete:
        print("--- Deleting removed files ---")
        # Construct `rm` commands in batches to avoid command length limits
        batch_size = 50
        for i in range(0, len(files_to_delete), batch_size):
            batch = files_to_delete[i:i+batch_size]
            paths_to_remove = [f"{REMOTE_BASE_DIR}/{p}" for p in batch]
            quoted_paths = [shlex.quote(p) for p in paths_to_remove]
            
            rm_cmd = ssh_base_cmd + ["rm -f"] + quoted_paths
            run_cmd(rm_cmd, env=env, check=True)
            print(f"Deleted batch {i // batch_size + 1}")

    # 5. Execute Sync via Rsync (Uploads/Updates)
    print("--- Syncing files via Rsync ---")
    local_dir = LOCAL_BASE_DIR.rstrip('/') + '/'
    
    rsync_ssh_cmd = f"ssh -p {PORT} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    
    # -a: archive
    # -v: verbose
    # -z: compress
    # -c: use checksums (slower but safer)
    # --no-perms: don't error on permission setting failures (common on some FS)
    # --timeout=60: I/O timeout
    rsync_cmd = [
        "sshpass", "-e",
        "rsync",
        "-avzc",
        "--no-perms",
        "--timeout=60",
        "--progress",
        "-e", rsync_ssh_cmd,
        local_dir,
        f"{USER}@{HOST}:{REMOTE_BASE_DIR}/"
    ]
    
    # We do NOT use --delete here because we already handled deletions safely based on the manifest.
    run_cmd(rsync_cmd, env=env, check=True)

    # 6. Upload New Manifest
    print("Updating remote manifest...")
    manifest_local_path = "new_manifest.json"
    with open(manifest_local_path, 'w') as f:
        json.dump(local_state, f)
    
    # Use rsync to upload manifest too, for consistency
    manifest_upload_cmd = [
        "sshpass", "-e",
        "rsync",
        "-avz",
        "-e", rsync_ssh_cmd,
        manifest_local_path,
        f"{USER}@{HOST}:{manifest_path}"
    ]
    
    run_cmd(manifest_upload_cmd, env=env, check=True)
    os.remove(manifest_local_path)
    
    print("Deployment complete.")

if __name__ == "__main__":
    main()
