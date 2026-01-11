#!/usr/bin/env python3
import os
import shutil
import sys
import argparse
import fnmatch

# Configuration
CLIENT_FILES_IGNORE = '.client_files'
PACK_IGNORE = '.packignore'
SERVER_PACK_DIR = 'server_pack'
DEFAULT_BUILD_DIR = 'build'

def load_ignore_patterns(root_dir, file_names):
    """
    Loads ignore patterns from specific files.
    """
    patterns = []
    for file_name in file_names:
        file_path = os.path.join(root_dir, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
    return patterns

def is_ignored(rel_path, patterns):
    """
    Checks if a relative path matches any of the ignore patterns.
    Implements a simplified version of gitignore logic.
    """
    # Normalize path separator to /
    path = rel_path.replace(os.sep, '/')
    ignored = False
    
    for pattern in patterns:
        negate = False
        current_pattern = pattern
        
        if current_pattern.startswith('!'):
            negate = True
            current_pattern = current_pattern[1:]
            
        should_ignore = False
        
        # Directory-specific match (trailing slash)
        match_dir_only = current_pattern.endswith('/')
        if match_dir_only:
            current_pattern = current_pattern[:-1]
            
        if '/' in current_pattern:
            # Path match
            if current_pattern.startswith('/'):
                current_pattern = current_pattern[1:]
                
            if fnmatch.fnmatch(path, current_pattern):
                should_ignore = True
            elif path.startswith(current_pattern + '/'):
                should_ignore = True
        else:
            # Filename match (anywhere)
            if fnmatch.fnmatch(os.path.basename(path), current_pattern):
                should_ignore = True
            # Also check if any component of the path matches
            # e.g. pattern "bin" should match "foo/bin/bar"
            # simple fnmatch on basename handles "bin", but strictly gitignore handles "bin/" differently?
            # We'll stick to simple logic: match basename or match full path against pattern
        
        if should_ignore:
            ignored = not negate
            
    return ignored

def copy_tree(src, dst, ignore_patterns=[], keep_structure_only_dirs=[]):
    """
    Copies files from src to dst, respecting ignore patterns.
    """
    if not os.path.exists(dst):
        os.makedirs(dst)
        
    for item in os.listdir(src):
        src_path = os.path.join(src, item)
        dst_path = os.path.join(dst, item)
        
        rel_path = os.path.relpath(src_path, start=os.getcwd())
        
        # Hardcoded specific ignores for tool operational files
        # We don't want to copy the usage files themselves into the build
        if item in ['.git', '.github', '.idea', 'build', '__pycache__', CLIENT_FILES_IGNORE, PACK_IGNORE, SERVER_PACK_DIR, os.path.basename(__file__)]:
            continue
            
        if is_ignored(rel_path, ignore_patterns):
            # print(f"Ignored: {rel_path}")
            continue
            
        if os.path.isdir(src_path):
            copy_tree(src_path, dst_path, ignore_patterns)
        else:
            shutil.copy2(src_path, dst_path)

def merge_tree(src, dst):
    """
    Merges content from src to dst, overwriting existing files.
    """
    if not os.path.exists(src):
        print(f"Warning: Source directory for merge '{src}' does not exist. Skipping.")
        return

    if not os.path.exists(dst):
        os.makedirs(dst)

    for item in os.listdir(src):
        src_path = os.path.join(src, item)
        dst_path = os.path.join(dst, item)
        
        if os.path.isdir(src_path):
            merge_tree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)

def build_mode(mode, root_dir, output_dir=None):
    if output_dir:
        target_dir = output_dir
    else:
        target_dir = os.path.join(root_dir, DEFAULT_BUILD_DIR, mode)

    # 1. Prepare Output Directory
    if os.path.exists(target_dir):
        print(f"Cleaning output directory: {target_dir}")
        shutil.rmtree(target_dir)
    os.makedirs(target_dir)

    # 2. Determine Ignore Patterns
    # Base ignores: .packignore
    ignore_patterns = load_ignore_patterns(root_dir, [PACK_IGNORE])
    
    if mode == 'server':
        # Server ignores: .packignore AND .client_files
        ignore_patterns.extend(load_ignore_patterns(root_dir, [CLIENT_FILES_IGNORE]))
        
    print(f"Building {mode} pack to {target_dir}...")
    
    # 3. Copy Base Files
    print("Copying base files...")
    copy_tree(root_dir, target_dir, ignore_patterns)
    
    # 4. Server Specific: Overlay server_pack
    if mode == 'server':
        server_pack_path = os.path.join(root_dir, SERVER_PACK_DIR)
        print(f"Overlaying {SERVER_PACK_DIR}...")
        merge_tree(server_pack_path, target_dir)

def main():
    parser = argparse.ArgumentParser(description='Minecraft Modpack Builder')
    parser.add_argument('mode', nargs='?', choices=['client', 'server'], help='Build mode: client, server, or both (default)')
    parser.add_argument('--output', '-o', default=None, help='Output directory (only used when building specific mode)')
    
    args = parser.parse_args()
    
    root_dir = os.getcwd()
    
    if args.mode:
        build_mode(args.mode, root_dir, args.output)
    else:
        if args.output:
            print("Warning: --output argument is ignored when building both modes.")
        
        build_mode('client', root_dir)
        print("-" * 20)
        build_mode('server', root_dir)
        
    print("Done!")

if __name__ == '__main__':
    main()
