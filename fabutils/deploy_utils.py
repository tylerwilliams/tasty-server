import os
import shutil
import random
import string
import getpass
import tempfile
import contextlib
import fabric

from fabric.api import env
from fabric.api import roles
from fabric.api import task
from fabric.api import settings
from fabric.api import hide
from fabric.api import lcd
from fabric.api import local
from fabric.api import prefix
from fabric.api import parallel
from fabric.api import execute
from fabric.api import hide
from fabric.api import puts

from fabric.api import run as remote_run
from fabric.api import cd as remote_cd
from fabric.api import prompt as orig_prompt
from fabric.api import sudo as orig_sudo

from fabric.colors import red, green, blue
from fabric.contrib import files
from fabric.contrib.project import rsync_project

def safe_sudo(*args):
    return orig_sudo(*args, pty=True)

# basic commands that form the basis of all tasks
run = remote_run
cd = remote_cd
sudo = safe_sudo

@contextlib.contextmanager
def local_commands():
    global run, cd, sudo
    # capture existing
    prev_run, prev_cd, prev_sudo = run, cd, sudo
    # set local
    run, cd, sudo = local, lcd, local
    yield
    # restore previous
    run, cd, sudo = prev_run, prev_cd, prev_sudo

@contextlib.contextmanager
def remote_commands():
    global run, cd, sudo
    # capture existing
    prev_run, prev_cd, prev_sudo = run, cd, sudo
    # set remote
    run, cd, sudo = remote_run, remote_cd, safe_sudo
    yield
    # restore previous
    run, cd, sudo = prev_run, prev_cd, prev_sudo


@contextlib.contextmanager
def virtualenv(envdir):
    envact = os.path.join(envdir, 'bin', 'activate')
    with prefix("source %s" % envact):
        yield
    # run("deactivate") # no need for this

class DumbCodeDeployer(object):
    def __init__(self,
                package_name,
                root_directory='/opt',
                recent_deploys_to_keep=5,
                link_tuples=(),
                requirements_file='requirements.txt',
                restart_cmds=(),
                ):
        assert len(package_name) > 0
        self._root_directory = root_directory
        self._package_name = package_name
        self._recent_deploys_to_keep = recent_deploys_to_keep
        self._link_tuples = link_tuples
        self._requirements_file = requirements_file
        self._restart_cmds = restart_cmds
    
    def _get_project_directory(self):
        return os.path.join(self._root_directory, self._package_name)

    def _get_project_bundle_directory(self):
        return os.path.join(self._get_project_directory(), 'bundles')

    def _get_project_venvs_directory(self):
        return os.path.join(self._get_project_directory(), 'venvs')

    def _get_bundle_tag_directory(self, tag):
        return os.path.join(self._get_project_bundle_directory(), tag)

    def _get_bundle_venv_directory(self, tag):
        return os.path.join(self._get_project_venvs_directory(), tag)

    def _get_already_deployed_bundles(self):
        raw_all_bundles = run("find %s -maxdepth 1 -mindepth 1 -type d | xargs ls -td1" % self._get_project_bundle_directory())
        remote_bundles = [s.strip() for s in filter(None, raw_all_bundles.split("\n")) if len(s) > 1]
        return remote_bundles

    def _add_trailing_slash(self, dir):
        if not dir.endswith("/"):
            return dir + "/"
        else:
            return dir

    def _get_latest_deployed_tag(self, tag):
        # make sure our remote root exists
        run("mkdir -p %s" % self._get_project_directory())
        # check that we can write it
        result = run("touch %s/.write_test" % self._get_project_directory())
        run("rm -rf %s/.write_test" % self._get_project_directory())
        # make sure our bundle directory exists
        run("mkdir -p %s" % self._get_project_bundle_directory())
        assert result.return_code == 0, "Cannot write to project directory"
        # look for the latest already deployed version
        existing_remote_bundles = self._get_already_deployed_bundles()
        if existing_remote_bundles:
            if not files.exists(self._get_bundle_tag_directory(tag), use_sudo=False, verbose=False):
                return existing_remote_bundles[-1]
            else:
                return None
        else:
            return None

    def push_code(self, local_project_checkout, tag):
        with remote_commands():
            # cp the most recent tag to the name of our new tag, if it exists
            most_recent_remote_bundle = self._get_latest_deployed_tag(tag)
            if most_recent_remote_bundle:
                run("cp -rp %s %s" % (most_recent_remote_bundle, self._get_bundle_tag_directory(tag)))
            # rsync to remote
            rsync_project(self._get_bundle_tag_directory(tag), self._add_trailing_slash(local_project_checkout), extra_opts='-aq', ssh_opts='-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no', delete=True)
            run("ln -sfn %s %s" % (self._get_bundle_tag_directory(tag), os.path.join(self._get_project_directory(), "current_bundle")))
            
    def clear_bundles(self, num_to_keep):
        with remote_commands():
            remote_bundles = self._get_already_deployed_bundles()
            # clean up all but latest num_to_keep bundles
            for old_bundle in remote_bundles[num_to_keep:]:
                run("rm -rf %s" % os.path.join(self._get_project_bundle_directory(), old_bundle))

    def preflight_remote_commands(self):
        for command, install_command in (
            ('virtualenv', 'sudo easy_install virtualenv'),
            ('usenv', 'echo \'%s\' | sudo tee /usr/local/bin/usenv > /dev/null && sudo chmod +x /usr/local/bin/usenv' % """#!/bin/bash
VENV=$1
if [ -z $VENV ]; then
    echo "usage: $0 [virtualenv_path] CMDS"
    exit 1
fi
. ${VENV}/bin/activate
shift 1
echo "Executing $@ in ${VENV}"
exec "$@"
deactivate
"""),
            ('supervisord', 'sudo yum -y install supervisor')
        ):
            with settings(warn_only=True):
                is_installed = (run("which %s" % command, pty=False).return_code == 0) or "command not found" not in run(command, pty=False)
            if not is_installed:
                run(install_command)

    def create_and_install_virtualenv(self, tag):
        with remote_commands():
            self.preflight_remote_commands()
            run("mkdir -p %s" % self._get_project_venvs_directory())
            run("virtualenv %s" % self._get_bundle_venv_directory(tag))
            with virtualenv(self._get_bundle_venv_directory(tag)):
                puts("installing requirements... (output muted)")
                with hide('running', 'stdout'):
                    run("pip install -r %s" % os.path.join(self._get_bundle_tag_directory(tag), self._requirements_file))
            run("ln -sfn %s %s" % (self._get_bundle_venv_directory(tag), os.path.join(self._get_project_directory(), "current_env")))
    
    def link_paths(self, tag):
        for bundle_relative_path, full_path in self._link_tuples:
            bundle_full_path = os.path.join(self._get_bundle_tag_directory(tag), bundle_relative_path)
            sudo("ln -sfn %s %s" % (bundle_full_path, full_path))
    
    def restart(self):
        for cmd in self._restart_cmds:
            sudo(cmd)
    
    def deploy(self, local_code_dir, tag_name):
        self.push_code(local_code_dir, tag_name)
        self.create_and_install_virtualenv(tag_name)
        self.link_paths(tag_name)
        self.restart()
        self.clear_bundles(self._recent_deploys_to_keep)

