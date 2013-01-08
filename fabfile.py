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

from fabutils import envs
from fabutils import deploy_utils

@task
def tag_and_deploy():
    # git tag
    tag_name = "test_tag_1"
    # clone in temp, checkout to tag
    
    # deploy to remote
    d = deploy_utils.DumbCodeDeployer("tasty-server",
        requirements_file='requirements.txt',
        link_tuples=(
                ('conf/tasty.conf', '/etc/tasty.conf'),
                ('tasty.ini', '/etc/supervisord.d/tasty.ini')
        ),
        restart_cmds=(
            'sudo /etc/init.d/supervisord start',
            'sudo supervisorctl reread update',
            'sudo supervisorctl restart tasty',            
        )
    )
        
    this_dir = os.path.dirname(os.path.abspath( __file__ ))
    d.deploy(this_dir, tag_name)

