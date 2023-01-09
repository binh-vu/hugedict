from __future__ import print_function
import os, subprocess, re
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


homes = {}
if "PYTHON_HOME" in os.environ:
    home = os.environ["PYTHON_HOME"]
    homes[home] = get_python_version(home)[0]
elif "PYTHON_HOMES" in os.environ:
    lst = os.environ["PYTHON_HOMES"].split(":")
    for path in lst:
        if is_python_home(path):
            # is the python directory
            homes[path] = get_python_version(path)[0]
        else:
            subhomes = {}
            for subpath in os.listdir(path):
                home = os.path.join(path, subpath)
                if not is_python_home(home):
                    continue

                version, pytype = get_python_version(home)

                # do not keep different patches (only keep major.minor)
                mm_version = ".".join(version.split(".")[:2])
                subhomes[mm_version, pytype] = (home, version)

            for home, version in subhomes.values():
                homes[home] = version

if "PYTHON_VERSIONS" in os.environ:
    versions = os.environ["PYTHON_VERSIONS"].split(",")
    filtered_homes = []
    for home, home_version in homes.items():
        for version in versions:
            if home_version.startswith(version):
                filtered_homes.append(home)
                break

    homes = {h: homes[h] for h in filtered_homes}


if "MINIMUM_PYTHON_VERSION" in os.environ:
    minimum_version = [int(d) for d in os.environ["MINIMUM_PYTHON_VERSION"].split(".")]
    filtered_homes = []
    for home, home_version in homes.items():
        pyversion = home_version.split(".")
        if all(
            int(pyversion[i]) >= minimum_version[i] for i in range(len(minimum_version))
        ):
            filtered_homes.append(home)

    homes = {h: homes[h] for h in filtered_homes}

print(":".join(homes))
exit(0)
