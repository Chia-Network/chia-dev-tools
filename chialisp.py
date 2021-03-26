import os
import sys
import shutil
from pathlib import Path
import hashlib
import re
import subprocess

from clvm_tools.clvmc import compile_clvm

def dev_util(args=sys.argv):
    cmd = args[1].lower()
    project_path = Path.cwd()
    script_root = Path(__file__).parent
    #Initialize a new project
    if cmd == "init" :
        project_path_lib = Path(project_path).joinpath("lib")
        project_path_std = Path(project_path_lib).joinpath("std")
        if not project_path_lib.exists():
            os.mkdir(project_path_lib)
        if project_path_std.exists() :
            shutil.rmtree(project_path_std)
        shutil.copytree(Path(script_root).joinpath("std"),project_path_std)
        hello_world_py = project_path_std.joinpath("examples","helloworld.py")
        hello_world_clvm = project_path_std.joinpath("clvm","helloworld.clvm")
        shutil.copy(hello_world_py,project_path)
        shutil.copy(hello_world_clvm,project_path)
        print("Run 'chialisp build' and then 'py helloworld.py'")
    if cmd == "build" :
        clvm_files = list(Path(project_path).rglob("*.[cC][lL][vV][mM]"))
        if (cmd == "build") & (len(args) > 2):
            clvm_files = list(filter(lambda e: e.name in args, clvm_files))
        already_compiled = []
        for filename in clvm_files:
            filehash = ""
            with open(filename, "rb") as afile:
                buf = afile.read()
                afile.close()
                filehash = hashlib.sha256(buf).hexdigest()
            hex_file_name = (filename.name + "." + filehash + ".hex") #upper needs to come out here after one run
            full_hex_file_name = Path(filename.parent).joinpath(hex_file_name)
            already_compiled.append(full_hex_file_name)
            if not full_hex_file_name.exists():
                outfile = str(filename) + "." + filehash + ".hex"
                compile_clvm(str(filename),outfile)
        garbage_files = list(Path(project_path).rglob("*.[hH][eE][xX]"))
        garbage_files = list(filter(lambda e: e not in already_compiled, garbage_files))
        for file in garbage_files:
            file.unlink()
