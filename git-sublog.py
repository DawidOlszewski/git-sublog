#!/usr/bin/python3

# input: number of commits in the main repo

# print all submodules with changes

from subprocess import run, DEVNULL
import os
import re
from  enum import StrEnum
import io
import sys

COMMIT_SHORT=8

class Mode(StrEnum):
    Submodule = "160000"
    Commit= "commit??:P"

executed_git_cmds = []

def cprint(*args, color="white", **kwargs):
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "reset": "\033[0m"
    }
    print(colors.get(color, ""), end="")
    print(*args, **kwargs)
    print(colors.get("reset", ""), end="")

def git_factory(path="."):
    def git(*args):
        arr = ["git", "-C", git.path, *args]
        executed_git_cmds.append(arr)
        p = run(arr,capture_output=True, text=True)
        if p.returncode != 0:
            raise Exception("return code != 0")
        return p.stdout
    git.path = path
    return git

git = git_factory()
    
def git_C(path, git=git):
    return git_factory(git.path + "/" + path)

def curr_branch(git=git):
    b = git("branch", "--show-current").strip()
    if b == "\n":
        return None
    return b

def git_fetch(git=git):
    git("fetch")

def remote_repo(git=git):
    r = git("remote", "-v").split("\n")[0].split("\t")[1].split(" ")[0]
    return r

def remote_repo_name(git=git):
    r = remote_repo(git=git)
    return r.split(":")[1].split(".")[0]

def submodules(git=git):
    submods = []
    for i, submodule_line in enumerate(git("submodule", "status").split("\n")[:-1]):
        submodule_raw = submodule_line.strip().split(" ")
        submodule =  [submodule_raw[1], submodule_raw[0]]
        submods.append(submodule)
    return submods
    
def submodule_down_top(func, git=git, lvl=0):
    print(remote_repo(git))
    for submod in submodules(git):
        path,_ = submod
        submodule_down_top(func, git=git_C(path,git=git), lvl=lvl+1)
    func(git,lvl)

def sublog(git=git):
    git_fetch(git)
    first_module = True
    buffer = io.StringIO()
    sys.stdout = buffer
    diff_size = print_curr_changes(git)
    sys.stdout = sys.__stdout__
    if diff_size > 0:
        if first_module:
            first_module = False
        else:
            print()
        cprint(remote_repo_name(git).center(65,"-"),color="yellow")
        print(buffer.getvalue(), end="")
        for submod in submodules(git):
            path,_ = submod
            sublog(git=git_C(path, git=git))

def raw_line(line: str):
    if line.startswith(":"):
        m = re.match(r"^:(\w+) (\w+) (\w+) (\w+) (.)\t(.+)$", line)
        if m is None:
            raise Exception(f"'{line}' does not match pattern")
        mode_old = m.group(1)
        mode_new = m.group(2)
        sha1_old = m.group(3)
        sha1_new = m.group(4)
        status =  m.group(5)
        path = m.group(6)
        if status == "M" and mode_new == Mode.Submodule.value:
            return {"type": Mode.Submodule.name, "f": sha1_old, "t": sha1_new, "path": path}
        return {"type": "unknown"}
    else:
        m = re.match(r"^(\w+) (.+)$", line)
        if m is None:
            raise Exception(f"'{line}' does not match pattern")
        sha = m.group(1)
        msg = m.group(2)
        return {"type": Mode.Commit.name, "sha": sha, "msg": msg}

def print_changes_bothsides(f,t , git=git):
    commit_amount = 0
    commit_amount += print_changes(f,t, color="green",git=git)
    commit_amount += print_changes(t, f, color="red",git=git)
    return commit_amount

# its the main reason of delay
def main_branch(git=git):
    # Below approach doesn't always work
    # r = git("symbolic-ref", "refs/remotes/origin/HEAD") # refs/remotes/origin/(master|main)
    # return r.split("/")[-1][:-1]
    r = git("ls-remote","--symref","origin","HEAD")
    return r.split("\n")[0].split("/")[-1].split("\t")[0]


def print_curr_changes(git=git):
    return print_changes_bothsides("origin/"+ main_branch(git=git),"HEAD", git=git)

def print_changes(f,t, color="green", git=git):
    fst = True
    res = git("log", f"{f}..{t}", "--raw", "--pretty=oneline")
    commit_amount = 0
    for line in res.split("\n")[:-1]:
        hline = raw_line(line)
        if hline["type"] == Mode.Commit.name:
            commit_amount += 1
            if fst:
                fst = False
            else:
                pass
            cprint(hline["sha"][:COMMIT_SHORT] ,hline["msg"], color=color)
        if hline["type"] == Mode.Submodule.name:
            cprint(hline["path"], f"{hline['f'][:COMMIT_SHORT]} -> {hline['t'][:COMMIT_SHORT]}")
    return commit_amount

def rev_parse(module_ref, git=git):
    return git("rev-parse", module_ref).strip()

# currently the only correct way of using this is by being in root dir of git
def subchange(module_path, module_ref, git=git):
    module_full_sha = rev_parse(module_ref, git_C(module_path, git=git))
    git("update-index", "--cacheinfo",  f"{Mode.Submodule.value},{module_full_sha},{module_path}")

def subsha(module_path, git=git):
    return git("ls-tree","HEAD", module_path).split("\t")[-2].split(" ")[-1]

def submsg(module_path, git=git):
    return  git_C(module_path,git=git)("log", subsha(module_path, git), "-1", "--pretty=%s").strip()

def is_ancestor(child_ref, parent_ref, git=git):
    executed_cmd = ["git", "-C", git.path, "merge-base", "--is-ancestor", child_ref, parent_ref]
    executed_git_cmds.append(executed_cmd)
    p = run(executed_cmd, stdout=DEVNULL,stdin=DEVNULL)
    if p.returncode == 128:
        raise Exception("bad ref")
    return not int(p.returncode)

cmd_dict = {
    "sublog": lambda : sublog(git=git),
    "subchange": lambda module_path, module_ref: subchange(module_path, module_ref, git=git),
    "subsha": lambda module_path: print(subsha(module_path, git=git)),
    "submsg": lambda module_path: print(submsg(module_path, git=git))
}

def usage():
    raise Exception("Usage: git", f"({'|'.join(cmd_dict.keys())})", sys.argv)


if __name__ == "__main__":
    match = re.match(r".*-(.*)", sys.argv[0])
    if not match:
        usage()

    cmd_name = match.group(1)
    try:
        cmd = cmd_dict[cmd_name]
        cmd(*sys.argv[1:])
    except:
        usage()