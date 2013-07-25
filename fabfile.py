# file fabfile.py
# 
#   Copyright 2010 Emory University General Library
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
import re
import shutil
from urllib import urlencode, urlopen
from xml.etree.ElementTree import XML

from fabric.api import abort, env, lcd, local, prefix, put, puts, require, \
                       run, sudo, task
from fabric.colors import green, red, cyan, yellow
from fabric.context_managers import cd, hide, settings
from fabric.contrib import files
from fabric.contrib.console import confirm

##
# automated build/test tasks
##

# omit these from the test coverage report
env.omit_coverage = ','.join([
    'digitizedbooks/manage.py',
    'digitizedbooks/settings.py',
    'digitizedbooks/localsettings.py',
    ])

def all_deps():
    '''Locally install all dependencies.'''
    local('pip install -r pip-install-req.txt -r pip-dev-req.txt')
    if os.path.exists('pip-local-req.txt'):
        local('pip install -r pip-local-req.txt')

def test():
    '''Locally run all tests.'''
    if os.path.exists('test-results'):
        shutil.rmtree('test-results')

    local('coverage run --branch %(project)s/manage.py test --noinput' % env)
    local('coverage xml --include=%(project)s**/*.py --omit=%(omit_coverage)s' % env)

def doc():
    '''Locally build documentation.'''
    with lcd('doc'):
        local('make clean html')

@task
def build():
    '''Run a full local build/test cycle.'''
    all_deps()
    test()
    doc()


##
# deploy tasks
##

env.project = 'digitizedbooks'
env.git_rev_tag = ''
env.git_rev = ''
env.remote_path = '/home/httpd/sites/digitizedbooks'
env.remote_solr_path = '/home/solr33/multicore'
env.remote_acct = 'digitizedbooks'
env.url_prefix = None
env.remote_proxy = None

def configure(path=None, solr_path=None, user=None, solr_user=None, url_prefix=None,
              remote_proxy=None, solr_admin_url=None):
    'Configuration settings used internally for the build.'


    env.version = digitizedbooks.__version__
    config_from_git()
    # construct a unique build directory name based on software version and git revision
    env.build_dir = '%(project)s-%(version)s-%(git_rev)s' % env
    env.tarball = '%(project)s-%(version)s-%(git_rev)s.tar.bz2' % env
    env.solr_tarball = '%(project)s-solr-%(version)s%(git_rev_tag)s.tar.bz2' % env

    if path:
        env.remote_path = path.rstrip('/')
    if solr_path:
        env.remote_solr_path = solr_path.rstrip('/')
    if user:
        env.remote_acct = user
    if solr_user:
        env.solr_acct = solr_user
    if url_prefix:
        env.url_prefix = url_prefix.rstrip('/')
    if solr_admin_url:
        env.solr_admin_url = solr_admin_url

    if remote_proxy:
        env.remote_proxy = remote_proxy
        puts('Setting remote proxy to %(remote_proxy)s' % env)


def config_from_git():
    """Infer revision from local git checkout."""
    # if not a released version, use revision tag
    env.git_rev = local('git rev-parse --short HEAD', capture=True).strip()
    if digitizedbooks.__version_info__[-1]:
        env.rev_tag = '-r' + env.git_rev

def prep_source():
    'Checkout the code from git and do local prep.'

    require('git_rev', 'build_dir',
            used_for='Exporting code from git into build area')

    local('mkdir -p build')
    local('rm -rf build/%(build_dir)s' % env)
    # create a tar archive of the specified version and extract inside the bulid directory
    local('git archive --format=tar --prefix=%(build_dir)s/ %(git_rev)s | (cd build && tar xf -)' % env)

    # local settings handled remotely

    if env.url_prefix:
        env.apache_conf = 'build/%(build_dir)s/apache/%(project)s.conf' % env
        # back up the unmodified apache conf
        orig_conf = env.apache_conf + '.orig'
        local('cp %s %s' % (env.apache_conf, orig_conf))
        with open(orig_conf) as original:
            text = original.read()
        text = text.replace('WSGIScriptAlias / ', 'WSGIScriptAlias %(url_prefix)s ' % env)
        text = text.replace('Alias /static/ ', 'Alias %(url_prefix)s/static ' % env)
        text = text.replace('<Location />', '<Location %(url_prefix)s/>' % env)
        with open(env.apache_conf, 'w') as conf:
            conf.write(text)

    local('mkdir -p build/solr/%(build_dir)s' % env)
    local('rm -rf build/solr/%(build_dir)s/conf' % env)
    local('cp -a build/%(build_dir)s/solr build/solr/%(build_dir)s/conf' % env)

def package_source():
    'Create a tarball of the source tree.'
    local('mkdir -p dist')
    local('tar cjf dist/%(tarball)s -C build %(build_dir)s' % env)
    local('tar cjf dist/%(solr_tarball)s -C build/solr %(build_dir)s' % env)

def upload_source():
    'Copy the source tarball to the target server.'
    put('dist/%(tarball)s' % env,
        '/tmp/%(tarball)s' % env)

def upload_solr_core():
    'Copy the solr core tarball to the target server.'
    put('dist/%(solr_tarball)s' % env,
        '/tmp/%(solr_tarball)s' % env)

def extract_source():
    'Extract the remote source tarball under the configured remote directory.'
    with cd(env.remote_path):
        sudo('tar xjf /tmp/%(tarball)s' % env, user=env.remote_acct)
        # if the untar succeeded, remove the tarball
        run('rm /tmp/%(tarball)s' % env)
        # update apache.conf if necessary

def extract_solr_core():
    'Extract the remote solr core tarball under the configured remote directory.'
    with cd(env.remote_solr_path):
        sudo('tar xjf /tmp/%(solr_tarball)s' % env, user=env.solr_acct)
        # if the untar succeeded, remove the tarball
        run('rm /tmp/%(solr_tarball)s' % env)

def bootstrap_unix_env():
    '''Set up host-specific remote unix environment by sourcing
    ``bootstrap-env`` if it exists. This is necessary (in our environment at
    least) to bring nonstandard package build and linker paths into to unix
    environment, e.g., for oracle libraries.
    '''
    # FIXME: There has *got* to be a batter way to incorporate library paths
    # etc in our build/deploy environment.
    return prefix('if [ -f %(remote_path)s/bootstrap-env ]; then source %(remote_path)s/bootstrap-env; fi' % env)

def setup_virtualenv(python=None):
    'Create a virtualenv and install required packages on the remote server.'
    python_opt = '--python=' + python if python else ''

    with cd('%(remote_path)s/%(build_dir)s' % env):
        # TODO: we should be using an http proxy here  (how?)
        # create the virtualenv under the build dir
        sudo('virtualenv --no-site-packages %s env' % (python_opt,),
             user=env.remote_acct)
        # activate the environment and install required packages
        with prefix('source env/bin/activate'):
            with bootstrap_unix_env():
                pip_cmd = 'pip install -r pip-install-req.txt'
                if env.remote_proxy:
                    pip_cmd += ' --proxy=%(remote_proxy)s' % env
                sudo(pip_cmd, user=env.remote_acct)
                if files.exists('../pip-local-req.txt'):
                    pip_cmd = 'pip install -r ../pip-local-req.txt'
                    if env.remote_proxy:
                        pip_cmd += ' --proxy=%(remote_proxy)s' % env
                    sudo(pip_cmd, user=env.remote_acct)


def configure_site():
    'Copy configuration files into the remote source tree.'
    with cd(env.remote_path):
        if not files.exists('localsettings.py'):
            abort('Configuration file is not in expected location: %(remote_path)s/localsettings.py' % env)
        sudo('cp localsettings.py %(build_dir)s/%(project)s/localsettings.py' % env,
             user=env.remote_acct)

    with cd('%(remote_path)s/%(build_dir)s' % env):
        with prefix('source env/bin/activate'):
            with bootstrap_unix_env():
                sudo('python %(project)s/manage.py collectstatic --noinput' % env,
                     user=env.remote_acct)
                # make static files world-readable
                sudo('chmod -R a+r `env DJANGO_SETTINGS_MODULE="%(project)s.settings" python -c "from django.conf import settings; print settings.STATIC_ROOT"`' % env,
                     user=env.remote_acct)
                

def update_links():
    'Update current/previous symlinks on the remote server.'
    with cd(env.remote_path):
        if files.exists('current' % env):
            sudo('rm -f previous; mv current previous', user=env.remote_acct)
        sudo('ln -sf %(build_dir)s current' % env, user=env.remote_acct)

@task
def syncdb():
    '''Remotely run syncdb and migrate after deploy and configuration.'''
    with cd('%(remote_path)s/%(build_dir)s' % env):
        with prefix('source env/bin/activate'):
            sudo('python %(project)s/manage.py syncdb --noinput' % env,
                 user=env.remote_acct)
            sudo('python %(project)s/manage.py migrate --noinput' % env,
                 user=env.remote_acct)

@task
def build_source_package(path=None, user=None, url_prefix='',
                        remote_proxy=None):
    '''Produce a tarball of the source tree and a solr core.'''
    # exposed as a task since this is as far as we can go for now with solr.
    # as solr deployment matures we should expose the most mature piece
    configure(path=path, user=user, url_prefix=url_prefix,
            remote_proxy=remote_proxy)
    prep_source()
    package_source()

@task
def deploy(path=None, user=None, url_prefix='', python=None,
           remote_proxy=None):
    '''Deploy the web app to a remote server.

    Parameters:
      path: base deploy directory on remote host; deploy expects a
            localsettings.py file in this directory
            Default: env.remote_path = /home/httpd/sites/digitizedbooks
      user: user on the remote host to run the deploy; ssh user (current or
            specified with -U option) must have sudo permission to run deploy
            tasks as the specified user
            Default: digitizedbooks
      url_prefix: base url if site is not deployed at /

    Example usage:
      fab deploy:/home/digitizedbooks/,oe -H servername
      fab deploy:user=www-data,url_prefix=/oe -H servername
      fab deploy:remote_proxy=some.proxy.server:3128 -H servername

    '''

    configure(path=path, user=user, url_prefix=url_prefix,
              remote_proxy=remote_proxy)
    prep_source()
    package_source()
    upload_source()
    extract_source()
    setup_virtualenv(python)
    configure_site()
    update_links()
    compare_localsettings()

@task
def revert(path=None, user=None):
    """Update remote symlinks to retore the previous version as current"""
    configure(path=path, user=user)
    # if there is a previous link, shift current to previous
    with cd(env.remote_path):
        if files.exists('previous'):
            # remove the current link (but not actually removing code)
            sudo('rm current', user=env.remote_acct)
            # make previous link current
            sudo('mv previous current', user=env.remote_acct)
            sudo('readlink current', user=env.remote_acct)

@task
def clean():
    '''Remove build/dist artifacts generated by deploy task'''
    local('rm -rf build dist')
    # should we do any remote cleaning?

@task
def rm_old_builds(path=None, user=None, noinput=False):
    '''Remove old build directories on the deploy server.

    Takes the same path and user options as **deploy**.  By default,
    will ask user to confirm delition.  Use the noinput parameter to
    delete without requesting confirmation.
    '''
    configure(path=path, user=user)
    with cd(env.remote_path):
        with hide('stdout'):  # suppress ls/readlink output
            # get directory listing sorted by modification time (single-column for splitting)
            dir_listing = sudo('ls -t1', user=env.remote_acct)
            # get current and previous links so we don't remove either of them
            current = sudo('readlink current', user=env.remote_acct) if files.exists('current') else None
            previous = sudo('readlink previous', user=env.remote_acct) if files.exists('previous') else None
            
        # split dir listing on newlines and strip whitespace
        dir_items = [n.strip() for n in dir_listing.split('\n')] 
        # regex based on how we generate the build directory:
        #   project name, numeric version, optional pre/dev suffix, optional revision #
        build_dir_regex = r'^%(project)s-[0-9.]+(-[A-Za-z0-9_-]+)?(-r[0-9]+)?$' % env
        build_dirs = [item for item in dir_items if re.match(build_dir_regex, item)]
        # by default, preserve the 3 most recent build dirs from deletion
        rm_dirs = build_dirs[3:]
        # if current or previous for some reason is not in the 3 most recent,
        # make sure we don't delete it
        for link in [current, previous]:
            if link in rm_dirs:
                rm_dirs.remove(link)

        if rm_dirs:
            for dir in rm_dirs:
                if noinput or confirm('Remove %s/%s ?' % (env.remote_path, dir)):
                    sudo('rm -rf %s' % dir, user=env.remote_acct)
        else:
            puts('No old build directories to remove')
 
@task
def compare_localsettings(path=None, user=None):
    'Compare current/previous (if any) localsettings on the remote server.'
    configure(path=path, user=user)
    with cd(env.remote_path):
        # sanity-check current localsettings against previous
        if files.exists('previous'):
            with settings(hide('warnings', 'running', 'stdout', 'stderr'),
                          warn_only=True):  # suppress output, don't abort on diff error exit code
                output = sudo('diff current/%(project)s/localsettings.py previous/%(project)s/localsettings.py' % env,
                              user=env.remote_acct)
                if output:
                    puts(yellow('WARNING: found differences between current and previous localsettings.py'))
                    puts(output)
                else:
                    puts(green('No differences between current and previous localsettings.py'))

