import os
import sys
import getpass

from fabric.api import env, task
from fabric.colors import red, green, blue
from fabric.contrib import console

def confirm_env():
    print blue("\n".join(env.hosts))
    should_continue = console.confirm(red("You are about to modify the above hosts. Are you sure you want to continue?"), default=False)
    if not should_continue:
        print red("aborted.")
        sys.exit(1)
    else:
        print green("here we go!")

@task
def tasty_server():
    deployment_name = 'tasty_server'
    env.user = 'deploy'
    env.password = os.getenv(deployment_name+"_dpw") or getpass.getpass("enter the deployment password for %s:" % deployment_name)
    env.hosts = ['tastes.gd']
    print green(("using %s environment!" % deployment_name).upper())
    confirm_env()