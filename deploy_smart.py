import os
import hashlib
import json
import paramiko
import sys
import logging
import time
from stat import S_ISDIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger("DeploySmart")

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
            logger.info(f"Creating remote directory: {current_path}")
            sftp.mkdir(current_path)

def create_progress_callback(filename):
    start_time = time.time()
    last_log_time = start_time
    
    def progress_callback(transferred, total):
        nonlocal last_log_time
        current_time = time.time()
        
        # Log every 5 seconds or on completion
        if current_time - last_log_time > 5 or transferred == total:
            percentage = (transferred / total) * 100 if total > 0 else 0
            elapsed = current_time - start_time
            speed = (transferred / 1024 / 1024) / elapsed if elapsed > 0 else 0
            logger.info(f"Transferring {filename}: {percentage:.1f}% ({transferred}/{total} bytes) - {speed:.2f} MB/s")
            last_log_time = current_time
            
    return progress_callback

def main():
    logger.info(f"Connecting to {HOST}:{PORT} as {USER}...")
    
    try:
        transport = paramiko.Transport((HOST, PORT))
        transport.set_keepalive(15) 
        
        # Tweak transport settings to avoid MTU/Window hangs on VPNs (like WireGuard)
        # Using conservative values to prevent packet fragmentation/dropping
        # MTU is likely ~1420 or lower. We use 1024 bytes per packet to be safe.
        transport.default_window_size = 8192 # 8KB Window
        transport.default_max_packet_size = 1024 # 1KB Packet limit (Fits 1420 MTU)
        
        transport.connect(username=USER, password=PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        sys.exit(1)

    # 1. Calculate Local state
    logger.info("Scanning local files and calculating hashes...")
    local_state = get_local_files_info(LOCAL_BASE_DIR)
    logger.info(f"Found {len(local_state)} local files.")

    # 2. Get Remote Manifest
    remote_state = {}
    manifest_path = f"{REMOTE_BASE_DIR}/{MANIFEST_FILENAME}"
    logger.info(f"Checking for remote manifest at {manifest_path}...")
    try:
        with sftp.open(manifest_path, 'r') as f:
            remote_state = json.load(f)
        logger.info(f"Loaded remote manifest. Known remote files: {len(remote_state)}")
    except (IOError, json.JSONDecodeError):
        logger.warning("Remote manifest not found or invalid. Performing full sync.")

    # 3. Compare & Plan Uploads
    files_to_upload = []
    force_full = os.environ.get('FORCE_FULL', 'false').lower() == 'true'
    
    if force_full:
        logger.info("!!! FORCED FULL DEPLOY ACTIVATED !!!")

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

    logger.info(f"Summary: {len(files_to_upload)} files to upload, {len(files_to_delete)} files to delete.")

    # 5. Execute Delete
    if files_to_delete:
        logger.info("--- Deleting removed files ---")
        for i, rel_path in enumerate(files_to_delete):
            remote_path = f"{REMOTE_BASE_DIR}/{rel_path}"
            logger.info(f"[{i+1}/{len(files_to_delete)}] Deleting: {rel_path}")
            try:
                sftp.remove(remote_path)
            except IOError as e:
                logger.error(f"Failed to delete {remote_path}: {e}")

    # 6. Execute Upload
    if files_to_upload:
        logger.info("--- Uploading files ---")
        for i, rel_path in enumerate(files_to_upload):
            local_path = os.path.join(LOCAL_BASE_DIR, rel_path)
            remote_path = f"{REMOTE_BASE_DIR}/{rel_path}"
            remote_dir = os.path.dirname(remote_path)
            
            try:
                sftp.stat(remote_path)
                # sftp.posix_rename(remote_path, remote_path) # check exists cheap
            except IOError:
                 ensure_remote_dir(sftp, remote_dir)

            logger.info(f"[{i+1}/{len(files_to_upload)}] Uploading: {rel_path} (Size: {local_state[rel_path]['size']} bytes)")
            
            try:
                callback = create_progress_callback(rel_path)
                sftp.put(local_path, remote_path, callback=callback)
                logger.info(f"Finished uploading {rel_path}")
            except Exception as e:
                logger.error(f"Failed to upload {rel_path}: {e}")
                # Don't break immediately, or do? If network is dead, next one will tail too.
                # Usually best to raise to fail the CI
                raise e
    else:
        logger.info("No files to upload.")

    # 7. Upload New Manifest
    logger.info("Updating remote manifest...")
    # Using local_state as the new manifest effectively
    with open('new_manifest.json', 'w') as f:
        json.dump(local_state, f)
    
    try:
        sftp.put('new_manifest.json', manifest_path)
        logger.info("Manifest updated successfully.")
    except Exception as e:
         logger.error(f"Failed to upload manifest: {e}")

    os.remove('new_manifest.json')

    sftp.close()
    transport.close()
    logger.info("Deployment complete.")

if __name__ == "__main__":
    main()
