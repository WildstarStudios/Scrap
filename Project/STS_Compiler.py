#!/usr/bin/env python3
"""
Scrap Build System – automatic transpilation + compilation.
Dynamically discovers library files, compiles them from source if missing,
and links everything together. No static mappings.
Usage: python STS_Compiler.py [--fresh] input.scrap output.exe
"""
import os, sys, shutil, subprocess, re
from pathlib import Path

# -------------------------------------------------------------------
# 1. find all import lib paths from the Scrap source
# -------------------------------------------------------------------
def find_imported_headers(scrap_file):
    with open(scrap_file, "r") as f:
        content = f.read()
    return re.findall(r'import\s+lib\s+"([^"]+)"', content)

# -------------------------------------------------------------------
# 2. find all import scrap files
# -------------------------------------------------------------------
def find_imported_scrap_files(scrap_file):
    with open(scrap_file, "r") as f:
        content = f.read()
    return re.findall(r'import scrap\s+"([^"]+)"', content)

# -------------------------------------------------------------------
# 3. gather source files (C and C++) from a library root
# -------------------------------------------------------------------
def gather_source_files(lib_root: Path):
    """
    Return (c_files, cpp_files) – lists of C and C++ source files.
    Exclude demo, test, example, shell, and other standalone programs.
    """
    exclude_patterns = ['demo', 'test', 'example', 'shell', 'fuzz', 'mptest']
    c_files = []
    cpp_files = []

    for ext in ('*.c', '*.cpp', '*.cxx', '*.cc'):
        for f in lib_root.rglob(ext):
            fname_lower = f.name.lower()
            if any(p in fname_lower for p in exclude_patterns):
                continue
            if ext in ('*.c',):
                c_files.append(str(f))
            else:
                cpp_files.append(str(f))

    return sorted(set(c_files)), sorted(set(cpp_files))

# -------------------------------------------------------------------
# 4. dynamically discover pre‑built library files (.lib, .a, .so, .dylib)
# -------------------------------------------------------------------
def gather_library_files(lib_root: Path):
    lib_exts = (".lib", ".a", ".so", ".dylib")
    library_files = []
    library_dirs = set()
    for f in lib_root.rglob("*"):
        if f.suffix in lib_exts:
            library_files.append(str(f))
            library_dirs.add(str(f.parent))
    return library_files, sorted(library_dirs)

# -------------------------------------------------------------------
# 5. compile a library from its source files (if no pre‑built exists)
# -------------------------------------------------------------------
def compile_library_from_source(lib_root: Path, include_dirs, force=False):
    """
    Compile all C/C++ sources in lib_root into a static library.
    Returns (library_file_path, library_dir) or (None, None) on failure.
    """
    c_files, cpp_files = gather_source_files(lib_root)
    if not c_files and not cpp_files:
        return None, None   # nothing to compile

    # Determine output library name
    lib_name = lib_root.name
    # We'll place the library inside a build directory inside the lib root
    build_dir = lib_root / "build_lib"
    build_dir.mkdir(exist_ok=True)

    # On MinGW we can create a static library with 'ar rcs'
    ar = shutil.which('ar') or 'ar'
    lib_file = build_dir / f"lib{lib_name}.a"

    # If library exists and not forced, skip
    if lib_file.exists() and not force:
        # Optional: check timestamps vs sources – for simplicity, we trust existence
        return str(lib_file), str(build_dir)

    # Compile all sources to object files
    objects = []
    gcc = shutil.which('gcc') or 'gcc'
    gpp = shutil.which('g++') or 'g++'

    # C files
    for c_file in c_files:
        obj_file = build_dir / (Path(c_file).stem + ".o")
        print(f"  [CC] {c_file} -> {obj_file}")
        cmd = [gcc, '-c', '-DNDEBUG', '-O2']
        for inc in include_dirs:
            cmd.append(f'-I{inc}')
        cmd += [c_file, '-o', str(obj_file)]
        if subprocess.run(cmd).returncode != 0:
            return None, None
        objects.append(str(obj_file))

    # C++ files
    for cpp_file in cpp_files:
        obj_file = build_dir / (Path(cpp_file).stem + ".o")
        print(f"  [CXX] {cpp_file} -> {obj_file}")
        cmd = [gpp, '-c', '-DNDEBUG', '-O2', '-std=c++17']
        for inc in include_dirs:
            cmd.append(f'-I{inc}')
        cmd += [cpp_file, '-o', str(obj_file)]
        if subprocess.run(cmd).returncode != 0:
            return None, None
        objects.append(str(obj_file))

    # Archive into static library
    print(f"  [AR] Creating {lib_file}")
    cmd_ar = [ar, 'rcs', str(lib_file)] + objects
    if subprocess.run(cmd_ar).returncode != 0:
        return None, None

    # Clean up object files (optional)
    for obj in objects:
        try:
            os.unlink(obj)
        except OSError:
            pass

    return str(lib_file), str(build_dir)

# -------------------------------------------------------------------
# 6. main build logic
# -------------------------------------------------------------------
def build(scrap_file, output_exe, fresh=False):
    # ---------- Transpile ----------
    print(f"Transpiling main: {scrap_file} …")
    main_cpp = "main_output.cpp"
    ret = subprocess.run(["python", "scrap.py", scrap_file, main_cpp])
    if ret.returncode != 0:
        print("Transpilation failed.")
        return 1

    imported_scraps = set()
    to_process = find_imported_scrap_files(scrap_file)
    while to_process:
        sf = to_process.pop()
        abs_sf = os.path.abspath(sf)
        if abs_sf in imported_scraps:
            continue
        imported_scraps.add(abs_sf)
        gen_cpp = os.path.splitext(abs_sf)[0] + "_generated.cpp"
        print(f"Transpiling import: {sf} → {gen_cpp}")
        ret = subprocess.run(["python", "scrap.py", sf, gen_cpp])
        if ret.returncode != 0:
            print(f"Failed to transpile {sf}")
            return 1
        nested = find_imported_scrap_files(sf)
        to_process.extend(nested)

    # ---------- Collect headers and sources ----------
    headers = find_imported_headers(scrap_file)
    for sf in imported_scraps:
        headers += find_imported_headers(sf)

    all_cpp_sources = {main_cpp}
    all_c_sources = set()
    include_dirs = set()
    library_files = []
    library_dirs = set()

    for h in headers:
        h_abs = os.path.abspath(h)
        if not os.path.exists(h_abs):
            print(f"Warning: header not found: {h}")
            continue

        include_dirs.add(os.path.dirname(h_abs))
        header_path = Path(h_abs).resolve()
        project_root = Path('.').resolve()
        rel = header_path.relative_to(project_root)
        parts = rel.parts
        if len(parts) > 1 and parts[0] == 'libs':
            lib_root = project_root / 'libs' / parts[1]
        else:
            lib_root = header_path.parent

        # --- Libraries: pre‑built or compile from source ---
        lib_files, lib_dirs = gather_library_files(lib_root)
        if lib_files:
            # Pre‑built found – use it
            library_files.extend(lib_files)
            library_dirs.update(lib_dirs)
        else:
            # No pre‑built library – try to compile the library from source
            c_files, cpp_files = gather_source_files(lib_root)
            if c_files or cpp_files:
                print(f"  No pre‑built library found for {lib_root.name}, compiling from source...")
                new_lib, new_dir = compile_library_from_source(
                    lib_root, include_dirs, force=fresh
                )
                if new_lib:
                    library_files.append(new_lib)
                    library_dirs.add(new_dir)
                    print(f"  Successfully compiled {new_lib}")
                else:
                    print(f"  Failed to compile library for {lib_root.name}.")
                    # Continue without – the link step might fail later, but we give a chance
            else:
                # No source files either – possibly header‑only library, nothing to link
                pass

        # Always gather C/C++ sources from the project (e.g., sqlite3.c in lib root)
        # We need to add them if the library was not pre‑built?
        # Actually, if we're using the pre‑built library we do NOT add sources.
        # But if we compile from source, the compilation step builds the .a and we don't
        # need to add the sources again. So we only add sources when there is NO library
        # AND we failed to compile one? Or maybe the user wants to compile everything together.
        # For robustness, we'll add sources if we are NOT using a pre‑built library AND
        # we did not succeed in building a static library. That way, as a last resort,
        # we compile the sources directly into the final executable.
        if not library_files:   # No pre‑built and no .a built (maybe user wants direct compilation)
            c_files, cpp_files = gather_source_files(lib_root)
            all_c_sources.update(c_files)
            all_cpp_sources.update(cpp_files)

    # Ensure the libs/ directory itself is in the include path for libraries with nested includes (e.g., rapidfuzz)
    if os.path.isdir('libs'):
        include_dirs.add('libs')

    # Add generated cpp from scrap imports
    for sf in imported_scraps:
        gen_cpp = os.path.splitext(sf)[0] + "_generated.cpp"
        if os.path.exists(gen_cpp):
            all_cpp_sources.add(gen_cpp)

    # ---------- Compile C sources (if any) ----------
    gcc = shutil.which('gcc') or 'gcc'
    gpp = shutil.which('g++') or 'g++'
    object_files = []

    build_dir = Path("build_objs")
    build_dir.mkdir(exist_ok=True)

    for c_file in sorted(all_c_sources):
        obj_name = build_dir / (Path(c_file).stem + ".o")
        print(f"  [C] {c_file} -> {obj_name}")
        cmd_cc = [gcc, '-c', '-DNDEBUG', '-O3', c_file, '-o', str(obj_name)]
        for d in sorted(include_dirs):
            cmd_cc.append(f'-I{d}')
        cmd_cc.append('-I.')
        if subprocess.run(cmd_cc).returncode != 0:
            print(f"Failed to compile {c_file}")
            return 1
        object_files.append(str(obj_name))

    for cpp_file in sorted(all_cpp_sources):
        obj_name = build_dir / (Path(cpp_file).stem + ".o")
        print(f"  [C++] {cpp_file} -> {obj_name}")
        cmd_cxx = [gpp, '-c', '-DNDEBUG', '-O3', '-std=c++17', cpp_file, '-o', str(obj_name)]
        for d in sorted(include_dirs):
            cmd_cxx.append(f'-I{d}')
        cmd_cxx.append('-I.')
        if subprocess.run(cmd_cxx).returncode != 0:
            print(f"Failed to compile {cpp_file}")
            return 1
        object_files.append(str(obj_name))

    # ---------- Link ----------
    cmd_link = [gpp, '-static', '-s',
                '-ffunction-sections', '-fdata-sections'] + object_files

    for d in sorted(library_dirs):
        cmd_link.append(f'-L{d}')
    cmd_link.extend(library_files)

    cmd_link.extend(['-Wl,--gc-sections', '-o', output_exe])

    print("Linking with:\n" + ' '.join(cmd_link))
    result = subprocess.run(cmd_link)
    if result.returncode != 0:
        print("Build failed.")
    else:
        print(f"Successfully built {output_exe}")
    return result.returncode

# -------------------------------------------------------------------
# main entry
# -------------------------------------------------------------------
if __name__ == '__main__':
    fresh = False
    args = sys.argv[1:]

    # Check for --fresh flag
    if '--fresh' in args:
        fresh = True
        args.remove('--fresh')

    if len(args) != 2:
        print("Usage: python STS_Compiler.py [--fresh] input.scrap output.exe")
        sys.exit(1)

    input_scrap, output_exe = args
    sys.exit(build(input_scrap, output_exe, fresh=fresh))