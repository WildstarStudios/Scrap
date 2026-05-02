#!/usr/bin/env python3
"""
Scrap Build System – automatic transpilation + compilation.
Usage: python STS_Compiler.py [--fresh] [--tiny] [--single] input.scrap output.exe
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
    exclude_patterns = ['demo', 'test', 'example', 'shell', 'fuzz', 'mptest']
    c_files = []
    cpp_files = []

    for ext in ('*.c', '*.cpp', 'cxx', '*.cc'):
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
# 4. discover pre‑built library files (.lib, .a, .so, .dylib)
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
# 5. compile a library from its source files (with flag retry)
#    Only used when --single is NOT specified.
# -------------------------------------------------------------------
def compile_library_from_source(lib_root: Path, include_dirs, force=False, tiny=False):
    c_files, cpp_files = gather_source_files(lib_root)
    if not c_files and not cpp_files:
        return None, None

    lib_name = lib_root.name
    build_dir = lib_root / "build_lib"
    build_dir.mkdir(exist_ok=True)

    ar = shutil.which('ar') or 'ar'
    lib_file = build_dir / f"lib{lib_name}.a"

    if lib_file.exists() and not force:
        return str(lib_file), str(build_dir)

    gcc = shutil.which('gcc') or 'gcc'
    gpp = shutil.which('g++') or 'g++'

    base_cflags = ['-c', '-DNDEBUG', '-O2', '-ffunction-sections', '-fdata-sections']
    base_cxxflags = ['-c', '-DNDEBUG', '-O2', '-std=c++17', '-ffunction-sections', '-fdata-sections']
    if tiny:
        base_cflags += ['-flto']
        base_cxxflags += ['-flto']

    # Define flag sets to try, in order
    if tiny:
        flag_combos = [
            ['-fno-exceptions', '-fno-rtti'],
            ['-fno-exceptions'],
            ['-fno-rtti'],
            []
        ]
    else:
        flag_combos = [
            ['-fno-exceptions', '-fno-rtti'],
            []
        ]

    for extra_flags in flag_combos:
        objects = []
        try:
            cflags = base_cflags + extra_flags
            cxxflags = base_cxxflags + extra_flags

            for c_file in c_files:
                obj_file = build_dir / (Path(c_file).stem + ".o")
                label = f"[CC{' ' + ','.join(extra_flags) if extra_flags else ''}]"
                print(f"  {label} {c_file} -> {obj_file}")
                cmd = [gcc] + cflags
                for inc in include_dirs:
                    cmd.append(f'-I{inc}')
                cmd += [c_file, '-o', str(obj_file)]
                if subprocess.run(cmd).returncode != 0:
                    raise RuntimeError("C compile failed")
                objects.append(str(obj_file))

            for cpp_file in cpp_files:
                obj_file = build_dir / (Path(cpp_file).stem + ".o")
                label = f"[CXX{' ' + ','.join(extra_flags) if extra_flags else ''}]"
                print(f"  {label} {cpp_file} -> {obj_file}")
                cmd = [gpp] + cxxflags
                for inc in include_dirs:
                    cmd.append(f'-I{inc}')
                cmd += [cpp_file, '-o', str(obj_file)]
                if subprocess.run(cmd).returncode != 0:
                    raise RuntimeError("C++ compile failed")
                objects.append(str(obj_file))

            print(f"  [AR] Creating {lib_file}")
            cmd_ar = [ar, 'rcs', str(lib_file)] + objects
            if subprocess.run(cmd_ar).returncode != 0:
                raise RuntimeError("Archive failed")

            for obj in objects:
                try:
                    os.unlink(obj)
                except OSError:
                    pass

            return str(lib_file), str(build_dir)

        except RuntimeError:
            for obj in objects:
                try:
                    os.unlink(obj)
                except OSError:
                    pass
            # try next flag combo
            continue

    print(f"  Failed to compile library {lib_name} with all flag combinations.")
    return None, None

# -------------------------------------------------------------------
# 6. main build logic
# -------------------------------------------------------------------
def build(scrap_file, output_exe, fresh=False, tiny=False, single=False):
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
    direct_sources = []   # used only when --single is True

    gcc = shutil.which('gcc') or 'gcc'
    gpp = shutil.which('g++') or 'g++'

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

        if single:
            # --single mode: collect source files directly (no archives)
            c_files, cpp_files = gather_source_files(lib_root)
            if c_files or cpp_files:
                print(f"  [--single] Adding sources from {lib_root.name}")
                direct_sources.extend(c_files)
                direct_sources.extend(cpp_files)
            # Also, if there are pre‑built libraries, we may still need them
            lib_files, lib_dirs = gather_library_files(lib_root)
            if lib_files:
                print(f"  [--single] Also linking pre‑built libraries for {lib_root.name}")
                library_files.extend(lib_files)
                library_dirs.update(lib_dirs)
        else:
            # Normal mode: use static archive if possible, else compile
            lib_files, lib_dirs = gather_library_files(lib_root)
            if lib_files:
                library_files.extend(lib_files)
                library_dirs.update(lib_dirs)
            else:
                c_files, cpp_files = gather_source_files(lib_root)
                if c_files or cpp_files:
                    print(f"  No pre‑built library found for {lib_root.name}, compiling from source...")
                    new_lib, new_dir = compile_library_from_source(
                        lib_root, include_dirs, force=fresh, tiny=tiny
                    )
                    if new_lib:
                        library_files.append(new_lib)
                        library_dirs.add(new_dir)
                        print(f"  Successfully compiled {new_lib}")
                    else:
                        print(f"  Failed to compile library for {lib_root.name}.")
                else:
                    pass

    if os.path.isdir('libs'):
        include_dirs.add('libs')

    for sf in imported_scraps:
        gen_cpp = os.path.splitext(sf)[0] + "_generated.cpp"
        if os.path.exists(gen_cpp):
            all_cpp_sources.add(gen_cpp)

    # ---------- Compile & Link ----------
    if single:
        # --- SINGLE‑COMMAND BUILD with flag retry ---
        all_sources = list(all_cpp_sources) + list(all_c_sources) + direct_sources
        if not all_sources:
            print("Error: no source files to compile")
            return 1

        # Define flag combos to try (same as normal mode)
        if tiny:
            flag_combos = [
                ['-fno-exceptions', '-fno-rtti'],
                ['-fno-exceptions'],
                ['-fno-rtti'],
                []
            ]
        else:
            flag_combos = [
                ['-fno-exceptions', '-fno-rtti'],
                []
            ]

        # Build base flags
        base_flags = ['-static', '-s', '-ffunction-sections', '-fdata-sections']
        if tiny:
            base_flags += ['-flto', '-O3']
        else:
            base_flags += ['-O2']

        success = False
        for extra_flags in flag_combos:
            cmd = [gpp] + base_flags + extra_flags
            for d in sorted(include_dirs):
                cmd.append(f'-I{d}')
            cmd.append('-I.')
            cmd.extend(all_sources)
            for d in sorted(library_dirs):
                cmd.append(f'-L{d}')
            cmd.extend(library_files)
            cmd.extend(['-Wl,--gc-sections', '-o', output_exe])

            print(f"Trying flags: {extra_flags if extra_flags else 'none'}")
            print("Command:\n" + ' '.join(cmd))
            result = subprocess.run(cmd)
            if result.returncode == 0:
                success = True
                break
            else:
                print(f"Failed with flags {extra_flags}, trying next...\n")

        if success:
            print(f"Successfully built {output_exe}")
            return 0
        else:
            print("Build failed with all flag combinations.")
            return 1

    else:
        # NORMAL MODE: compile objects separately, then link
        object_files = []
        used_extra_flags = []

        build_dir = Path("build_objs")
        build_dir.mkdir(exist_ok=True)

        if tiny:
            flag_combos = [
                ['-fno-exceptions', '-fno-rtti'],
                ['-fno-exceptions'],
                ['-fno-rtti'],
                []
            ]
        else:
            flag_combos = [
                ['-fno-exceptions', '-fno-rtti'],
                []
            ]

        compiled_successfully = False
        for extra_flags in flag_combos:
            objects = []
            ok = True
            cc_flags = ['-c', '-DNDEBUG', '-O3', '-ffunction-sections', '-fdata-sections'] + extra_flags
            cxx_flags = ['-c', '-DNDEBUG', '-O3', '-std=c++17', '-ffunction-sections', '-fdata-sections'] + extra_flags
            if tiny:
                cc_flags += ['-flto']
                cxx_flags += ['-flto']

            for c_file in sorted(all_c_sources):
                obj_name = build_dir / (Path(c_file).stem + ".o")
                print(f"  [C{' (' + ','.join(extra_flags) + ')' if extra_flags else ''}] {c_file} -> {obj_name}")
                cmd_cc = [gcc] + cc_flags + [c_file, '-o', str(obj_name)]
                for d in sorted(include_dirs):
                    cmd_cc.append(f'-I{d}')
                cmd_cc.append('-I.')
                if subprocess.run(cmd_cc).returncode != 0:
                    ok = False
                    break
                objects.append(str(obj_name))

            if ok:
                for cpp_file in sorted(all_cpp_sources):
                    obj_name = build_dir / (Path(cpp_file).stem + ".o")
                    print(f"  [C++{' (' + ','.join(extra_flags) + ')' if extra_flags else ''}] {cpp_file} -> {obj_name}")
                    cmd_cxx = [gpp] + cxx_flags + [cpp_file, '-o', str(obj_name)]
                    for d in sorted(include_dirs):
                        cmd_cxx.append(f'-I{d}')
                    cmd_cxx.append('-I.')
                    if subprocess.run(cmd_cxx).returncode != 0:
                        ok = False
                        break
                    objects.append(str(obj_name))

            if ok:
                object_files = objects
                used_extra_flags = extra_flags
                compiled_successfully = True
                break
            else:
                for obj in objects:
                    try:
                        os.unlink(obj)
                    except OSError:
                        pass

        if not compiled_successfully:
            print("Error: program compilation failed.")
            return 1

        # Link
        link_flags = [gpp, '-static', '-s',
                      '-ffunction-sections', '-fdata-sections']
        link_flags += used_extra_flags
        if tiny:
            link_flags += ['-flto', '-O3']

        cmd_link = link_flags + object_files
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
    tiny = False
    single = False
    args = sys.argv[1:]

    if '--fresh' in args:
        fresh = True
        args.remove('--fresh')
    if '--tiny' in args:
        tiny = True
        args.remove('--tiny')
    if '--single' in args:
        single = True
        args.remove('--single')

    if len(args) != 2:
        print("Usage: python STS_Compiler.py [--fresh] [--tiny] [--single] input.scrap output.exe")
        sys.exit(1)

    input_scrap, output_exe = args
    sys.exit(build(input_scrap, output_exe, fresh=fresh, tiny=tiny, single=single))