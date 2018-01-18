#!/usr/bin/env python
#
#  This file is part of oh-my-tuna
#  Copyright (c) 2018 oh-my-tuna's authors
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import subprocess
import os
import argparse
import re
from six.moves import input
from contextlib import contextmanager

mirror_root = "mirrors.tuna.tsinghua.edu.cn"
always_yes = False
verbose = False

os_release_regex = re.compile(r"^ID=\"?([^\"\n]+)\"?$", re.M)


@contextmanager
def cd(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def sh(command):
    try:
        if verbose:
            print('$ %s' % command)
        return subprocess.check_output(
            command.split()).decode('utf-8').rstrip()
    except Exception as e:
        return None


def user_prompt():
    global always_yes
    if always_yes:
        return True
    
    ans = input('Do you wish to proceed(y/n/a):')
    if ans == 'a':
        always_yes = True
    return ans != 'n'


def ask_if_change(name, expected, command_read, command_set):
    current = sh(command_read)
    if current != expected:
        print('%s Before:' % name)
        print(current)
        print('%s After:' % name)
        print(expected)
        if user_prompt():
            sh(command_set)
            print('Command %s succeeded' % command_set)
            return True
        else:
            return False
    else:
        print('%s is already configured to TUNA mirrors' % name)
        return True


def get_os_name():
        os_release = sh('cat /etc/os-release')
        if not os_release:
            return None
        match = re.findall(os_release_regex, os_release)
        if len(match) != 1:
            return None
        return match[0]


class Base(object):
    """
    Name of this mirror/module
    """
    def name():
        raise NotImplementedError
    
    """
    Returns whether this mirror is applicable
    """
    def is_applicable():
        return False

    """
    Returns whether this mirror is already up
    """
    def is_online():
        raise NotImplementedError

    """
    Activate this mirror
    Returns True if this operation is completed, False otherwise
    Caller should never invoke this method when is_online returns True
    """
    def up():
        raise NotImplementedError

    """
    Deactivate this mirror
    Returns True if this operation is completed, False otherwise
    Caller should never invoke this method when is_online returns False
    """
    def down():
        raise NotImplementedError

    """
    Print a log entry with the name of this mirror/module
    """
    @classmethod
    def log(cls, msg):
        print('[%s]: %s' % (cls.name(), msg))


class ArchLinux(Base):
    def name():
        return 'Arch Linux'

    def is_applicable():
        return os.path.isfile('/etc/pacman.d/mirrorlist') and get_os_name() == 'arch'

    def is_online():
        mirror_re = re.compile(
                r" *Server *= *(http|https)://%s/archlinux/\$repo/os/\$path\n" % mirror_root,
                re.M)
        ml = open('/etc/pacman.d/mirrorlist', 'r')
        lines = ml.readlines()
        result = map(lambda l: re.match(mirror_re, l), lines)
        result = any(result)
        ml.close()
        return result

    def up():
        # Match commented or not
        mirror_re = re.compile(
                r" *(# *)?Server *= *(http|https)://%s/archlinux/\$repo/os/\$path\n" % mirror_root,
                re.M)
        banner = '# Generated and managed by the awesome oh-my-tuna\n'
        target = "Server = https://%s/archlinux/$repo/os/$path\n\n" % mirror_root

        print('This operation will insert the following line into the beginning of your pacman mirrorlist:\n%s' % target[:-2])
        if not user_prompt():
            return False

        ml = open('/etc/pacman.d/mirrorlist', 'r')
        lines = ml.readlines()

        # Remove all
        lines = filter(lambda l: re.match(mirror_re, l) is None, lines)

        # Remove banner
        lines = filter(lambda l: l != banner, lines)

        # Finish reading
        lines = list(lines)

        # Remove padding newlines
        k = 0
        while k < len(lines) and lines[k] == '\n':
            k += 1


        ml.close()
        ml = open('/etc/pacman.d/mirrorlist', 'w')
        # Add target
        ml.write(banner)
        ml.write(target)
        ml.writelines(lines[k:])
        ml.close()
        return True

    def down():
        print('This action will comment out TUNA mirrors from your pacman mirrorlist, if there is any.')
        if not user_prompt():
            return False

        # Simply remove all matched lines
        mirror_re = re.compile(
                r" *Server *= *(http|https)://%s/archlinux/\$repo/os/\$path\n" % mirror_root,
                re.M)

        ml = open('/etc/pacman.d/mirrorlist', 'r')
        lines = ml.readlines()
        lines = list(map(lambda l: l if re.match(mirror_re, l) is None else '# ' + l, lines))
        ml.close()
        ml = open('/etc/pacman.d/mirrorlist', 'w')
        ml.writelines(lines)
        ml.close()
        return True 

class Homebrew(Base):
    def name():
        return 'Homebrew'
    
    def is_applicable():
        return sh('brew --repo') is not None

    def is_online():
        repo = sh('brew --repo')
        return repo == 'https://%s/git/homebrew/brew.git' % mirror_root

    def up():
        with cd(repo):
            ask_if_change(
                'Homebrew repo',
                'https://%s/git/homebrew/brew.git' % mirror_root,
                'git remote get-url origin',
                'git remote set-url origin https://%s/git/homebrew/brew.git' %
                mirror_root)
        for tap in ('homebrew-core', 'homebrew-python', 'homebrew-science'):
            tap_path = '%s/Library/Taps/homebrew/%s' % (repo, tap)
            if os.path.isdir(tap_path):
                with cd(tap_path):
                    ask_if_change(
                        'Homebrew tap %s' % tap,
                        'https://%s/git/homebrew/%s.git' % (mirror_root, tap),
                        'git remote get-url origin',
                        'git remote set-url origin https://%s/git/homebrew/%s.git'
                        % (mirror_root, tap))
        return True

class CTAN(Base):
    def nam():
        return 'CTAN'

    def is_applicable():
        return sh('tlmgr --version') is not None

    def is_online():
        return sh('tlmgr option repository') == 'Default package repository (repository): http://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet'

    def up():
        return ask_if_change(
            'CTAN mirror',
            'Default package repository (repository): http://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet',
            'tlmgr option repository',
            'tlmgr option repository https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet'
        )

MODULES = [ArchLinux, Homebrew, CTAN]

def main():
    parser = argparse.ArgumentParser(
        description='Use TUNA mirrors everywhere when applicable')
    parser.add_argument('subcommand', nargs='?', metavar='SUBCOMMAND', choices=['up', 'down', 'status'], default='up')
    parser.add_argument(
        '-v', '--verbose', help='verbose output', action='store_true')
    parser.add_argument(
        '-y',
        '--yes',
        help='always answer yes to questions',
        action='store_true')


    args = parser.parse_args()
    global verbose
    verbose = args.verbose
    global always_yes
    always_yes = args.yes

    if args.subcommand == 'up':
        for m in MODULES:
            if m.is_applicable():
                if not m.is_online():
                    m.log('Activating...')
                    try:
                        result = m.up()
                        if not result:
                            m.log('Operation cancled')
                        else:
                            m.log('Mirror has been activated')
                    except NotImplementedError:
                        m.log('Mirror doesn\'t support activation. Please activate manually')

    if args.subcommand == 'down':
        for m in MODULES:
            if m.is_applicable():
                if m.is_online():
                    m.log('Deactivating...')
                    try:
                        result = m.down()
                        if not result:
                            m.log('Operation cancled')
                        else:
                            m.log('Mirror has been deactivated')
                    except NotImplementedError:
                        m.log('Mirror doesn\'t support deactivation. Please deactivate manually')

    if args.subcommand == 'status':
        for m in MODULES:
            if m.is_applicable():
                if m.is_online():
                    m.log('Online')
                else:
                    m.log('Offline')


if __name__ == "__main__":
    main()
