from __future__ import print_function
import os, subprocess, re, argparse
from typing import Tuple


def is_python_home(dir: str):
    return any(
        os.path.exists(os.path.join(dir, "bin", name))
        for name in ["python", "python2", "python3"]
    )


def get_python(home: str):
    for name in ["python", "python2", "python3"]:
        path = os.path.join(home, "bin", name)
        if os.path.exists(path):
            return path
    raise ValueError("python not found in {}".format(home))


def get_python_version(home: str) -> Tuple[str, str]:
    """Get python's version and whether it is cpython or pypy."""
    output = subprocess.check_output([get_python(home), "-V"]).decode().strip()
    m = re.match("Python ([\d\.)]+)", output)
    assert m is not None
    version = m.group(1)
    type = "pypy" if output.find("PyPy") != -1 else "cpython"
    return version, type


parser = argparse.ArgumentParser(prog="discover installed python")
parser.add_argument("--min-version")
parser.add_argument("--select-versions")
parser.add_argument("--root-dir", required=True)
parser.add_argument("--delimiter", default=" ", help="delimiter to separate pythons")

args = parser.parse_args()

rootdir = os.path.abspath(args.root_dir)
if rootdir.find(" ") != -1:
    paths = rootdir.split(" ")
else:
    paths = [rootdir]

homes = {}
for path in paths:
    if is_python_home(path):
        # is the python directory
        homes[path] = get_python_version(path)[0]
    else:
        subpaths = [os.path.join(path, subpath) for subpath in os.listdir(path)]
        if not any(is_python_home(subpath) for subpath in subpaths):
            subpaths = [
                os.path.join(subpath, subsubpath)
                for subpath in subpaths
                if os.path.isdir(subpath)
                for subsubpath in os.listdir(subpath)
            ]
        subhomes = {}
        for home in subpaths:
            if not is_python_home(home):
                continue
            version, pytype = get_python_version(home)

            # do not keep different patches (only keep major.minor)
            mm_version = ".".join(version.split(".")[:2])
            subhomes[mm_version, pytype] = (home, version)

        for home, version in subhomes.values():
            homes[home] = version

if args.select_versions is not None:
    versions = args.select_versions.split(",")
    filtered_homes = []
    for home, home_version in homes.items():
        for version in versions:
            if home_version.startswith(version):
                filtered_homes.append(home)
                break

    homes = {h: homes[h] for h in filtered_homes}


if args.min_version is not None:
    minimum_version = [int(d) for d in args.min_version.split(".")]
    filtered_homes = []
    for home, home_version in homes.items():
        pyversion = home_version.split(".")
        if all(
            int(pyversion[i]) >= minimum_version[i] for i in range(len(minimum_version))
        ):
            filtered_homes.append(home)

    homes = {h: homes[h] for h in filtered_homes}

print(args.delimiter.join([get_python(home) for home in homes]))
exit(0)
