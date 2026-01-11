import os
import hashlib
import json
import paramiko
import sys
from stat import S_ISDIR

# Configuration via Environment Variables
HOST = os.environ.get('SFTP_HOST')
USER = os.environ.get('SFTP_USER')
PASSWORD = os.environ.get('SFTP_PASS')
PORT = int(os.environ.get('SFTP_PORT', 22))
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

def sftp_walk(sftp, remote_path):
    """Non-recursive helper to verify directory existence (not used for diffing anymore)."""
    try:
        sftp.stat(remote_path)
        return True
    except IOError:
        return False

def ensure_remote_dir(sftp, remote_path):
    """Recursively creates remote directories."""
    dirs = remote_path.split('/')
    current_path = ""
    for dir_part in dirs:
        if not dir_part: continue
        current_path += "/" + dir_part
        try:
            sftp.stat(current_path)
        except IOError:
            sftp.mkdir(current_path)

def main():
    print(f"Connecting to {HOST}:{PORT} as {USER}...")
    transport = paramiko.Transport((HOST, PORT))
    transport.connect(username=USER, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(transport)

    # 1. Calculate Local state
    print("Scanning local files and calculating hashes...")
    local_state = get_local_files_info(LOCAL_BASE_DIR)
    print(f"Found {len(local_state)} local files.")

    # 2. Get Remote Manifest
    remote_state = {}
    manifest_path = f"{REMOTE_BASE_DIR}/{MANIFEST_FILENAME}"
    print(f"Checking for remote manifest at {manifest_path}...")
    try:
        with sftp.open(manifest_path, 'r') as f:
            remote_state = json.load(f)
        print(f"Loaded remote manifest. Known remote files: {len(remote_state)}")
    except (IOError, json.JSONDecodeError):
        print("Remote manifest not found or invalid. Performing full sync.")

    # 3. Compare & Plan Uploads
    files_to_upload = []
    force_full = os.environ.get('FORCE_FULL', 'false').lower() == 'true'
    
    if force_full:
        print("!!! FORCED FULL DEPLOY ACTIVATED !!!")

    for rel_path, info in local_state.items():
        need_upload = False
        reason = ""
        
        if rel_path not in remote_state:
            need_upload = True 
            reason = "New file"
        elif force_full:
            need_upload = True
            reason = "Forced full"
        elif remote_state[rel_path]['hash'] != info['hash']:
            need_upload = True
            reason = "Hash mismatch"
        
        if need_upload:
            files_to_upload.append(rel_path)
    
    # 4. Compare & Plan Deletions (Safe Delete)
    # Only delete files that are in the remote manifest (we put them there) 
    # BUT are no longer in the local build.
    files_to_delete = []
    for rel_path in remote_state:
        if rel_path not in local_state:
            files_to_delete.append(rel_path)

    print(f"Summary: {len(files_to_upload)} files to upload, {len(files_to_delete)} files to delete.")

    # 5. Execute Delete
    if files_to_delete:
        print("--- Deleting removed files ---")
        for i, rel_path in enumerate(files_to_delete):
            remote_path = f"{REMOTE_BASE_DIR}/{rel_path}"
            print(f"[{i+1}/{len(files_to_delete)}] Deleting: {rel_path}")
            try:
                sftp.remove(remote_path)
            except IOError as e:
                print(f"Failed to delete {remote_path}: {e}")

    # 6. Execute Upload
    if files_to_upload:
        print("--- Uploading files ---")
        for i, rel_path in enumerate(files_to_upload):
            local_path = os.path.join(LOCAL_BASE_DIR, rel_path)
            remote_path = f"{REMOTE_BASE_DIR}/{rel_path}"
            remote_dir = os.path.dirname(remote_path)
            
            try:
                sftp.posix_rename(remote_path, remote_path) # check exists cheap
            except IOError:
                 ensure_remote_dir(sftp, remote_dir)

            print(f"[{i+1}/{len(files_to_upload)}] Uploading: {rel_path}")
            sftp.put(local_path, remote_path)
    else:
        print("No files to upload.")

    # 7. Upload New Manifest
    print("Updating remote manifest...")
    # Using local_state as the new manifest effectively
    with open('new_manifest.json', 'w') as f:
        json.dump(local_state, f)
    
    sftp.put('new_manifest.json', manifest_path)
    os.remove('new_manifest.json')

    sftp.close()
    transport.close()
    print("Deployment complete.")

if __name__ == "__main__":
    main()
