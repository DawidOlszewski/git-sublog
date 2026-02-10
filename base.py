#!/usr/bin/env python3

from dataclasses import dataclass
from subprocess import run, DEVNULL
import os
import re
from  enum import StrEnum
import io
import sys
from typing import Iterator, List, NoReturn, Optional, Set, Tuple, cast
from collections import namedtuple

Ref = str

COMMIT_SHORT=8

class Mode(StrEnum):
    Submodule = "160000"
    File = "100000"
    Commit= "commit??:P"

executed_git_cmds = []

def cprint(*args, fg_color="default", bg_color="default", **kwargs):
    colors = {
        "black":   0,
        "red":     1,
        "green":   2,
        "yellow":  3,
        "blue":    4,
        "magenta": 5,
        "cyan":    6,
        "white":   7,
    }

    start = ""
    if fg_color != "default":
        try:
            start += f"\033[{30 + colors[fg_color]}m"
        except:
            raise Exception("bad fg color")
    
    if bg_color != "default":
        try:
            start += f"\033[{40 + colors[bg_color]}m"
        except:
            raise Exception("bad bg color")
    
    reset = "\033[0m"

    print(start, end="")
    print(*args, **kwargs)
    print(reset, end="")

# its the main reason of delay
def main_branch(git):
    # Below approach doesn't always work
    # try:
    #     r = git("symbolic-ref", f"refs/remotes/{git.remote}/HEAD")
    #     return r.split("/")[-1][:-1]
    # except:
    #     r = git("ls-remote","--symref",git.remote,"HEAD")
    #     return r.split("\n")[0].split("/")[-1].split("\t")[0]
    #FIXME: for git_factory
    return "main"

def git_factory(path=".", current=None, baseline=None, target=None, parent_current_ptr=None, parent_target_ptr=None):
    def git(*args, env=None, allow_fail=False):
        arr = ["git", "-C", git.path, *args]
        executed_git_cmds.append(arr)
        environ = os.environ.copy()
        if env:
            environ.update(env)
        p = run(arr,capture_output=True, text=True, env=environ)
        if p.returncode != 0 and not allow_fail:
            raise Exception("return code != 0", executed_git_cmds, git.path)
        return p.stdout
    
    git.path = path
    
    def parse_config_file(path) -> Tuple[Optional[Ref], Optional[Ref], Optional[Ref], Optional[Ref]]:
        config_current, config_baseline, config_target, config_remote = None, None, None, None
        try:
            with open(path + "/.sublog") as conf:
                for l in conf:
                    if (m:= re.match(r"^current=(?P<current>\w+)$", l, re.IGNORECASE)) is not None:
                        config_current = cast(str,m.group("current"))
                    elif (m:= re.match(r"^baseline=(?P<baseline>\w+)$", l, re.IGNORECASE)) is not None:
                        config_baseline = cast(str, m.group("baseline"))
                    elif (m:= re.match(r"^target=(?P<target>\w+)$", l, re.IGNORECASE)) is not None:
                        config_target = cast(str, m.group("target"))
                    elif (m:= re.match(r"^remote=(?P<remote>\w+)$", l, re.IGNORECASE)) is not None:
                        config_remote = cast(str, m.group("remote"))

        except OSError:
            pass
        return config_current, config_baseline, config_target, config_remote

    config_current, config_baseline, config_target, config_remote = parse_config_file(path=path)
    current = current or config_current or "HEAD"
    try:
        baseline = baseline or config_baseline or main_branch(git)
    except Exception as e:
        e.add_note(f"Baseline ref in config file and main branch in repo are not set, so baseline branch is not chosen")
        raise
    remote = config_remote or "origin"
    target = target or \
            config_target or \
            f"{remote}/{baseline}"
    
    git.current = current
    git.baseline = baseline
    git.target = target
    
    git.remote = remote

    git.parent_current_ptr = parent_current_ptr
    git.parent_target_ptr = parent_target_ptr
    return git

# TODO:verify_commit
#git rev-parse --verify <commit-sha>^{commit}

git = git_factory()
    
def git_C(path, current=None, baseline=None, target=None, parent_target_ptr=None, parent_current_ptr=None, git=git):
    return git_factory(git.path + "/" + path, current=current, baseline=baseline, target=target, parent_target_ptr=parent_target_ptr, parent_current_ptr=parent_current_ptr)

def curr_branch(git=git):
    b = git("branch", "--show-current").strip()
    if b == "\n":
        return None
    return b

def git_fetch(git=git):
    git("fetch", allow_fail=True)

def remote_repo(git=git):
    r = git("remote", "-v").split("\n")[0].split("\t")[1].split(" ")[0]
    return r

def remote_repo_name(git=git):
    r = remote_repo(git=git)
    return r.split(":")[1].split(".")[0]

#order of args
def submodules(git=git, commit=None):
    submods = []
    if commit is not None:
        git_read_tree(commit, git)
        for i, submodule_line in enumerate(git("submodule", "status", "--cached").split("\n")[:-1]):
            submodule_raw = submodule_line.strip().split(" ")
            submodule =  [submodule_raw[1], submodule_raw[0]]
            submods.append(submodule)
    else: 
        for i, submodule_line in enumerate(git("submodule", "status").split("\n")[:-1]):
            submodule_raw = submodule_line.strip().split(" ")
            submodule =  [submodule_raw[1], submodule_raw[0]]
            submods.append(submodule)
    return submods
    
def submodule_down_top(func, git=git, lvl=0):
    for submod in submodules(git):
        path,_ = submod
        submodule_down_top(func, git=git_C(path,git=git), lvl=lvl+1)
    func(git,lvl)

def submodule_top_down(func, git=git, lvl=0):
    if func(git,lvl) != False:
        for submod in submodules(git):
            path,_ = submod
            submodule_top_down(func, git=git_C(path,git=git), lvl=lvl+1)

def _git_fetch(git_path):
    git_fetch(git_factory(git_path))

def _main_branch(git_path):
    return [git_path, main_branch(git=git_factory(git_path))]

def get_cmt_by_msg(msg, descendant, git=git):
    res = git("log", descendant,  f"--grep=^{msg}$", '--pretty=%H')
    return res.split('\n')[0]

def git_read_tree(cmt, git):
    git("read-tree", cmt)

def git_write_tree(git):
    res = git("write-tree")
    return res.split("\n")[0]

def get_msg_of_cmt(cmt, git):
    res = git("show", "--quiet", "--format=%s", cmt)
    return res[:-1]

def git_commit_tree(tree, msg, parent, git):
    res = git("commit-tree", tree, "-m", msg, "-p", parent)
    return res.split("\n")[0]

def get_parent_cmt(sha, git):
    res = git("rev-parse", sha + "^")
    return res.split("\n")[0]

def git_checkout(ref, git):
    git("checkout", ref)

def _subupdate_execute(state_list: list[tuple[str, dict]], git=git):
    parent = get_parent_cmt(state_list[0][0], git)
    prev = parent
    for cmt, submodule_dict in state_list:
        git_read_tree(cmt, git)
        for submodule, sha in submodule_dict.items():
            subchange(submodule, sha, git)
        new_tree_hash = git_write_tree(git)
        prev = git_commit_tree(new_tree_hash, get_msg_of_cmt(cmt, git), prev, git)
    return prev

def _subupdate_get_change_list(cmts, git):
    # take commits -> cmts
    # returns new state of submodules as a list [(sha, {submodule->new_sha})] 
    change_list = []
    for cmt in cmts:
        changed = changed_submodules(cmt, git)
        change_list.append((cmt, changed))
    return change_list

def _subupdate_get_state_list(change_list, git):
    # if len(cmts) # do sth
    parent_cmt = get_parent_cmt(change_list[0][0], git)
    submodule_state = dict(submodules(git,parent_cmt))
    state_list = []
    for sha, change_entry in change_list:
        submodule_state = {**submodule_state, **change_entry}
        state_list.append((sha, submodule_state))
    return state_list

def _subupdate_update_changed_list(changed_list, git):
    updated_changed_list = []
    for cmt, changed_submodules in changed_list:
        updated_state = {}
        for submodule, sha in changed_submodules.items():
            git_sub = git_C(submodule, git=git)
            updated_sha = get_cmt_by_msg(get_msg_of_cmt(sha, git_sub), git_sub.current, git_sub)
            updated_state[submodule] = updated_sha
        updated_changed_list.append((cmt, updated_state))
    return updated_changed_list

def get_cmt_range(fr, to, git):
    res = git("log", "--pretty=%H", "--reverse", f"{fr}..{to}")
    return res.split("\n")[:-1]

def get_lca(ref1, ref2, git=git):
    res = git("merge-base", ref1, ref2)
    return res[:-1]

def _subupdate_rec(git, lvl):
    cmts = get_cmt_range(git.baseline, git.current, git)
    change_list = _subupdate_get_change_list(cmts, git)
    if all(len(change[1]) == 0 for change in change_list):
        print("leaving as it is:", git.path)
        return 
    updated_change_list = _subupdate_update_changed_list(change_list, git)
    state_list = _subupdate_get_state_list(updated_change_list, git)
    new_ref = _subupdate_execute(state_list)
    git_checkout(new_ref, git)

def subupdate(git=git):
    submodule_down_top(_subupdate_rec, git)

#origin
def subfiles(git=git):
    files = set()
    def callback(git, lvl):
        nonlocal files 
        files = files.union(get_files(git.baseline, git.current, git))
    submodule_down_top(callback, git=git)
    print(*files, sep="\n")

def raw_line(line: str):
    if line.startswith(":"):
        m = re.match(r"^:(\w+) (\w+) (\w+) (\w+) (.{1,4})\t(.+)\t?(.*)$", line)
        if m is None:
            raise Exception(f"'{line}' does not match pattern")
        mode_old = m.group(1)
        mode_new = m.group(2)
        sha1_old = m.group(3)
        sha1_new = m.group(4)
        status =  m.group(5)
        path = m.group(6)
        new_path = m.group(7) # only in C(opy) and R(aname)
        if mode_new in ["100" + f"{i}{j}{k}" for i in range(8) for j in range(8) for k in range(8)]:
            if status[:1] in ["A", "M"]:
                return { "type": Mode.File.name, "path": path }
            if status[:1] in ["R", "C"]:
                return { "type": Mode.File.name, "path": new_path }
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

def print_changes_bothsides(current: Ref, baseline: Ref, target: Ref, parent_current_ref: Optional[Ref] = None, parent_target_ref: Optional[Ref] = None, git=git) -> int:
    current_changes = get_submodule_changes(baseline, current , git=git)
    target_changes = get_submodule_changes(baseline, target, git=git)
    
    current_changes_mark = [False] * len(current_changes)
    mark = False
    for i in reversed(range(len(current_changes_mark))):
        mark = mark or current_changes[i].sha == parent_current_ref
        current_changes_mark[i] = mark
    current_changes_marked = list(
        cast(Iterator[Tuple[bool, SubmoduleChange]],
        zip(current_changes_mark, current_changes))
        )

    target_changes_mark = [False] * len(target_changes)
    mark = False
    for i in reversed(range(len(target_changes_mark))):
        mark = mark or target_changes[i].sha == parent_target_ref
        target_changes_mark[i] = mark
    target_changes_marked = list(
                                    cast(Iterator[Tuple[bool, SubmoduleChange]], 
                                 zip(target_changes_mark, target_changes, strict = True))
    )

    first_diverged_index = 0
    for i in range(min(len(current_changes), len(target_changes))):
        if current_changes[i].sha != target_changes[i].sha:
            first_diverged_index = i
            break

    only_current_changes = current_changes_marked[first_diverged_index:]
    only_target_changes = target_changes_marked[first_diverged_index:]
    only_common_changes = current_changes_marked[:first_diverged_index]

    def _print_change_range(changes: list[Tuple[bool, SubmoduleChange]], fg: str):
        for marked, change in changes:
            bg = "blue" if marked else "default"
            print_submodule_change(change, fg = fg, bg = bg)

    _print_change_range(only_current_changes, "green")
    _print_change_range(only_common_changes, "magenta")
    _print_change_range(only_target_changes, "red")
    if only_target_changes:
        # its written twice on purpose
        _print_change_range(only_common_changes, "magenta")

    return len(current_changes + target_changes)


@dataclass
class SubmoduleChange:
    sha: Ref
    msg: str
    changed_submodules: list[Tuple[str, Tuple[Ref, str], Tuple[Ref, str]]]

def print_submodule_change(submodule_change: SubmoduleChange, fg: str, bg: str):
    cprint(submodule_change.sha, submodule_change.msg, fg_color=fg)
    for changed_submodule in submodule_change.changed_submodules:
        cprint(changed_submodule[0], fg_color="yellow", end=" ")
        f_sub_sha, f_sub_color = changed_submodule[1]
        cprint(f_sub_sha, fg_color=f_sub_color, end="")
        print(" -> ", end="")
        t_sub_sha, t_sub_color = changed_submodule[2]
        cprint(t_sub_sha, fg_color=t_sub_color)



# def print_curr_changes(git=git):
#     return print_changes_bothsides(git.current, , git=git, color_subrefs=True)


def get_files(f: Ref, t: Ref, which="modified",git=git) -> Set[str]:
    modified_args = ["--diff-filter=ARM"] if which == "modified" else []
    res = git("diff", f"{f}..{t}", "--name-only", *modified_args)
    files = set(res[:-1].split("\n"))
    return files

def get_submodule_changes(f: Ref, t: Ref, git=git):
    res = git("log", f"{f}..{t}", "--raw", "--pretty=oneline")
    submodule_changes: list[SubmoduleChange] = []
    last_cmt: Optional[SubmoduleChange] = None # invariant: first line of raw-log is about commit
    git_sub = None
    for line in res.split("\n")[:-1]:
        hline = raw_line(line)
        if hline["type"] == Mode.Commit.name:
            if last_cmt is not None:
                submodule_changes.append(last_cmt)
            last_cmt = SubmoduleChange(hline["sha"][:COMMIT_SHORT], hline["msg"], [])
        if hline["type"] == Mode.Submodule.name:
            sub_path: str = hline["path"]
            assert isinstance(sub_path, str)
            sub_f_sha = hline['f'][:COMMIT_SHORT]
            assert isinstance(sub_f_sha, str)
            sub_t_sha: str = hline['t'][:COMMIT_SHORT]
            assert isinstance(sub_t_sha, str)
            git_sub = git_C(hline["path"], git=git)
            try: sub_f_color = "cyan" if is_ancestor(sub_f_sha, git_sub.current, git_sub) else "magenta"
            except: sub_f_color = "red"
            try: sub_t_color = "cyan" if is_ancestor(sub_t_sha, git_sub.current, git_sub) else "magenta"
            except: sub_t_color = "red"
            assert last_cmt is not None
            last_cmt.changed_submodules.append(
                (sub_path, \
                (sub_f_sha, sub_f_color), \
                (sub_t_sha, sub_t_color)))
    return submodule_changes

def changed_submodules(cmt, git=git):
    res = git("log", cmt, "-1", "--raw", "--pretty=")
    changed_submods = {}
    for line in res.split("\n")[:-1]:
        hline = raw_line(line)
        if hline["type"] == Mode.Submodule.name:
            sub_path = hline["path"]
            sub_t_sha = hline['t'][:COMMIT_SHORT]
            changed_submods[sub_path] = sub_t_sha
    return changed_submods

def rev_parse(module_ref, git=git):
    return git("rev-parse", module_ref).strip()

# currently the only correct way of using this is by being in root dir of git
def subchange(module_path, module_ref, git=git):
    module_full_sha = rev_parse(module_ref, git_C(module_path, git=git))
    git("update-index", "--cacheinfo",  f"{Mode.Submodule.value},{module_full_sha},{module_path}")

def subsha(ref, module_path, git=git):
    return git("ls-tree", ref, module_path).split("\t")[-2].split(" ")[-1]

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
    "subsha": lambda module_path: print(subsha(git.current, module_path, git=git)),
    "submsg": lambda module_path: print(submsg(module_path, git=git)),
    "subfiles": lambda : subfiles(git=git),
    "subupdate": lambda : subupdate(git=git)
}

def usage() -> NoReturn:
    for i in executed_git_cmds:
        print(" ".join(i))
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