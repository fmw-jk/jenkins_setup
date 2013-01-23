#!/usr/bin/env python

import datetime
import socket
import pkg_resources
import yaml
import re

from jenkins_setup import cob_distro


class Jenkins_Job(object):
    """
    Object representation of Jenkins job
    """
    def __init__(self, jenkins_instance, pipeline_config):
        """
        Sets up Jenkins job object
        """

        self.JOB_TYPE_NAMES = {'pipe': 'pipe_starter',
                               'prio': 'prio_build',
                               'normal': 'normal_build',
                               'down': 'downstream_build',
                               'db': 'database_test',
                               'sim': 'simulation_test',
                               'app': 'application_test',
                               'clean': 'cleanup',
                               'bringup': 'bringup_hardware_test',
                               'hilevel': 'highlevel_hardware_test',
                               'release': 'release_params'}

        self.jenkins_instance = jenkins_instance
        self.pipe_conf = pipeline_config

        self.job_config_params = pkg_resources.resource_string('jenkins_setup', 'templates/job_config_params.yaml')
        self.job_config_params = yaml.load(self.job_config_params)
        self.job_config = pkg_resources.resource_string('jenkins_setup', 'templates/job_config.xml')

        self.pipe_inst = cob_distro.Cob_Distro_Pipe()
        self.pipe_inst.load_from_dict(self.pipe_conf['repositories'])

    def schedule_job(self):
        """
        Create new or reconfigure existent job
        """
        if self.jenkins_instance.job_exists(self.job_name):
            try:
                self.jenkins_instance.reconfig_job(self.job_name, self.job_config)
                print "Reconfigured job %s" % self.job_name
                return 'reconfigured'
            except:
                return 'reconfiguration failed'
        else:
            try:
                self.jenkins_instance.create_job(self.job_name, self.job_config)
                print "Created job %s" % self.job_name
                return 'created'
            except:
                return 'creation failed'

    def delete_job(self):
        """
        Deletes the job defined by the job name

        :param job_name: name of the job to delete, ``str``
        :returns: return message, ``str``
        """

        if self.jenkins_instance.job_exists(self.job_name):
            try:
                self.jenkins_instance.delete_job(self.job_name)
            except:
                return 'deletion failed'  # Exception ??
            return 'deleted'
        else:
            return 'not existent'

    def get_common_params(self):
        """
        Gets all parameters which have to be defined for every job type
        """

        self.params = {}

        self.params['USERNAME'] = self.pipe_conf['user_name']
        self.params['EMAIL'] = self.pipe_conf['email']
        self.params['EMAIL_COMMITTER'] = self.pipe_conf['committer']
        self.params['JOB_TYPE_NAME'] = self.JOB_TYPE_NAMES[self.job_type]
        self.params['SCRIPT'] = self.JOB_TYPE_NAMES[self.job_type]
        self.params['NODE_LABEL'] = self.job_type
        self.params['TIME'] = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M')
        self.params['HOSTNAME'] = socket.gethostname()
        self.params['PROJECT'] = 'matrix-project'
        self.params['TRIGGER'] = self.job_config_params['triggers']['none']
        self.params['VCS'] = self.job_config_params['vcs']['none']
        self.params['MATRIX'] = ''
        self.params['PARAMETERS'] = ''
        self.params['POSTBUILD_TRIGGER'] = self.params['JOIN_TRIGGER'] = self.params['PIPELINE_TRIGGER'] = self.params['GROOVY_POSTBUILD'] = ''

    ###########################################################################
    # helper methods - parameter generation
    ###########################################################################
    def replace_placeholder(self):
        '''
        replace placeholder in template with params
        '''

        for key, value in self.params.iteritems():
            if "@(%s)" % key not in self.job_config:
                raise KeyError("Parameter %s could not be replaced, because it is not existent" % key)
            self.job_config = self.job_config.replace("@(%s)" % key, value)
        not_replaced_keys = re.findall('@\(([A-Z0-9_]+)\)', self.job_config)
        if not_replaced_keys != []:
            raise KeyError("The keys %s were not replaced, because the parameters where missing" % (str(not_replaced_keys)))

    def generate_job_name(self, job_type, suffix=''):
        '''
        Returns a job_name string generated from a job_type plus suffix

        :param job_type: short job type name, ``str``
        :param suffix: will be added to the end of the name, ``str``
        '''

        if suffix != '':
            return '__'.join([self.pipe_conf['user_name'],
                              self.JOB_TYPE_NAMES[job_type],
                              suffix])
        else:
            return '__'.join([self.pipe_conf['user_name'],
                              self.JOB_TYPE_NAMES[job_type]])

    def generate_job_list(self, job_type_list):
        '''
        returns a list of job_names generated from a list of job_types
        '''

        if type(job_type_list) != list:
            raise TypeError("Input type is not type 'list'")
        return [self.generate_job_name(job_type) for job_type in job_type_list]

    def generate_job_list_string(self, job_type_list):
        '''
        returns a string of comma separated job_names generated from a list of job_types
        '''

        return ', '.join(self.generate_job_list(job_type_list))

    def generate_matrix_filter(self, config, negation=False):
        """
        Returns a groovy combination filter

        :param config: couples of names and values which have to be met, ``dict``
        :param negation: negates the resulting filter, ``bool``
        :returns: matrix config, ``str``
        """

        filter = '(%s)' % ' || '.join(['(%s)' % ' && '.join(['%s == %s' % (key, value)
                                                             for key, value in i.iteritems()])
                                       for i in config])
        if negation:
            filter = '!' + filter

        return filter

    def generate_matrix_axis(self, axis_name, value_list):
        """
        Returns matrix axis config for given list of values

        :param axis_name: name of axis, ``str``
        :param value_list: list with value, ``list``
        :returns: axis config, ``str``
        """

        if axis_name == '':
            raise Exception('No proper name given')
        if value_list == []:
            raise Exception('No values given')
        axis = self.job_config_params['matrix']['axis'].replace('@(NAME)', axis_name)
        values = ' '.join([self.job_config_params['matrix']['value'].replace('@(VALUE)', value) for value in value_list])
        axis = axis.replace('@(VALUES)', values)

        return axis

    def generate_matrix_param(self, name_value_dict, filter=None):
        """
        Returns matrix config for given dictionary containing names and values

        :param name_value_dict: matrix parameter config, ``dict``
        :param filter: combination filter, ``str``
        :returns: matrix config, ``str``
        """

        axes = ''
        if name_value_dict == {}:
            return ''
        axes += ' '.join([self.generate_matrix_axis(axis_name, axis_values)
                          for axis_name, axis_values in name_value_dict.iteritems()])

        matrix = self.job_config_params['matrix']['basic'].replace('@(AXES)', axes)
        if filter:
            matrix += ' ' + self.job_config_params['matrix']['filter'].replace('@(FILTER)', filter)

        return matrix

    def generate_jointrigger_param(self, job_type_list, unstable_behavior):
        '''
        '''

        if job_type_list == []:
            return ''
        elif unstable_behavior == '':
            raise Exception('No behavior for unstable job result')
        elif not (unstable_behavior == 'true' or unstable_behavior == 'false'):
            raise Exception("Behavior argument has to be 'true' or 'false'")

        jointrigger = self.job_config_params['jointrigger'].replace('@(JOIN_PROJECTS)',
                                                                    self.generate_job_list_string(job_type_list))
        return jointrigger.replace('@(JOIN_UNSTABLE)', str(unstable_behavior))

    def generate_postbuildtrigger_param(self, job_type_list, threshold_name):
        '''
        '''

        if job_type_list == []:
            return ''
        elif threshold_name == '':
            raise Exception('No treshold for postbuildtrigger given')
        elif threshold_name not in ['SUCCESS', 'UNSTABLE', 'FAILURE']:  # TODO check tresholds
            raise Exception("Threshold argument invalid")

        postbuildtrigger = self.job_config_params['postbuildtrigger'].replace('@(CHILD_PROJECTS)',
                                                                              self.generate_job_list_string(job_type_list))
        return postbuildtrigger.replace('@(THRESHOLD)', threshold_name)

    def generate_pipelinetrigger_param(self, job_type_list):
        '''
        '''

        if job_type_list == []:
            return ''
        return self.job_config_params['pipelinetrigger'].replace('@(PIPELINETRIGGER_PROJECT)',
                                                                 self.generate_job_list_string(job_type_list))

    def generate_groovypostbuild_param(self, script_type, project_list, behavior):
        '''
        '''

        if project_list == []:
            raise Exception('No project is given')
        if behavior > 2 or behavior < 0 or type(behavior) != int:
            raise Exception('Invalid behavior number given')
        script = self.job_config_params['groovypostbuild']['script'][script_type].replace('@(PROJECT_LIST)',
                                                                                          str(self.generate_job_list(project_list)))
        return self.job_config_params['groovypostbuild']['basic'].replace('@(GROOVYPB_SCRIPT)', script).replace('@(GROOVYPB_BEHAVIOR)', str(behavior))

    def generate_parameterizedtrigger_param(self, project_list, condition='SUCCESS', predefined_param='', subset_filter='', no_param=False):
        """
        Generates config for parameterizedtrigger plugin
        """

        matrix_subset = ''
        if subset_filter != '':
            matrix_subset = self.job_config_params['parameterizedtrigger']['matrix_subset']
            matrix_subset = matrix_subset.replace('@(FILTER)', subset_filter)

        predef_param = ''
        if predefined_param != '':
            predef_param = self.job_config_params['parameterizedtrigger']['predef_param']
            predef_param = predef_param.replace('@(PARAMETER)', predefined_param)

        param_trigger = self.job_config_params['parameterizedtrigger']['basic']
        param_trigger = param_trigger.replace('@(CONFIGS)', predef_param + matrix_subset)
        param_trigger = param_trigger.replace('@(PROJECTLIST)', ', '.join(project_list))
        param_trigger = param_trigger.replace('@(CONDITION)', condition)

        if no_param:
            param_trigger = param_trigger.replace('@(NOPARAM)', 'true')
        else:
            param_trigger = param_trigger.replace('@(NOPARAM)', 'false')

        return param_trigger


class Pipe_Starter_Job(Jenkins_Job):
    """
    Object representation of Pipe Starter Job
    """
    def __init__(self, jenkins_instance, pipeline_config, repo, poll=None):
        """
        :param jenkins_instance: object of Jenkins server
        :param pipeline_config: config dict, ``dict``
        :param repo: name of repository after change, ``str``
        :param poll: name of repository to monitor for changes, ``str``
        """

        super(Pipe_Starter_Job, self).__init__(jenkins_instance, pipeline_config)

        self.job_type = 'pipe'
        self.job_name = self.generate_job_name()

        self.repo = repo
        self.poll = None
        if poll:
            self.poll = poll

        self.get_common_params()

        self.replace_placeholder()

        self.schedule_job()

    def get_job_type_params(self):
        """
        Generates pipe starter specific job configuration parameters
        """

        self.params['NODE_LABEL'] = 'master'
        self.params['PROJECT'] = 'project'

        self.params['TRIGGER'] = self.job_config_params['triggers']['vcs']

        if self.poll:
            git_poll_repo = self.job_config_params['vcs']['git']['repo']
            git_poll_repo = git_poll_repo.replace('@(URI)', self.pipe_inst.repositories[self.repo].dependencies[self.poll].url)
            git_poll_repo = git_poll_repo.replace('@(BRANCH)', self.pipe_inst.repositories[self.repo].dependencies[self.poll].version)
        else:
            git_poll_repo = self.job_config_params['vcs']['git']['repo']
            git_poll_repo = git_poll_repo.replace('@(URI)', self.pipe_inst.repositories[self.repo].url)
            git_poll_repo = git_poll_repo.replace('@(BRANCH)', self.pipe_inst.repositories[self.repo].version)

        git_branch = self.job_config_params['vcs']['git']['branch'].replace('@(BRANCH)', '')  # TODO check if thats right
        self.params['VCS'] = (self.job_config_params['vcs']['git']['basic'].replace('@(GIT_REPOS)', git_poll_repo)
                              .replace('@(GIT_BRANCHES)', git_branch))

        # generate groovy postbuild script
        self.params['GROOVY_POSTBUILD'] = self.generate_groovypostbuild_param('disable', ['bringup', 'hilevel', 'release'], 2)

        # generate postbuild trigger
        self.params['POSTBUILD_TRIGGER'] = self.generate_postbuildtrigger_param(['prio'], 'SUCCESS')
