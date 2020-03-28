"""Multi-core related objects."""
import multiprocessing
import subprocess

from idpconfgen import Path, log
from idpconfgen.libs import libcheck
from idpconfgen.logger import S


class Worker(multiprocessing.Process):
    """
    Multiprocessing Worker.

    Parameters
    ----------
    task_queue
        A queue of tasks. Queue must be poisoned with a terminal `None`.
    
    results_queue
        A queue where to store the results.
    """

    def __init__(self, task_queue, result_queue):
      
        # super().__init__(self) ?
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        """
        Replace multiprocessing.Process.run() method.

        Queries new tasks from the task queue until `None` is found.
        """
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                log.info(S('exiting: {}', proc_name))
                self.task_queue.task_done()
                break
            result = next_task()
            self.task_queue.task_done()
            self.result_queue.put(result)
        return


class Task:
    """
    Task operation main class.

    Nothing is implement in here. But servers already as base class
    for the future if needed.
    """

    pass


class SubprocessTask(Task):
    """
    Subprocess Task operation.

    Parameters
    ----------
    cmd_exec : str or list
        The command to execute. Options to the command
        should be given here, and two formats are possible,
        as string or as list. If string, string is split into
        its components, for example:
            
            'ls -ltr' will result in ['ls', '-ltr']
        
        A preprepared list can be given instead.
    
    input : list
        A list containing whatever input the command must receive.
        Defaults to None, no input is used.
    """
   
    @libcheck.argstype(Task, (list, str))
    @libcheck.kwargstype((type(None), list, tuple))
    def __init__(self, cmd_exec, input_=None):
        self.cmd_exec = cmd_exec
        self.input = input_

    def __str__(self):  # noqa: D400, D401
        """String me! What was the noqa code for this?"""
        try:
            return ' '.join(self.cmd)
        except AttributeError:
            return repr(self)

    def __repr__(self):  # noqa: D102
        return '{}({})'.format(
            __class__.__name__,
            ','.join('{}={}'.format(
                k.lstrip('_'),
                v) for k, v in self.__dict__.items()),
            )
  
    def __call__(self):  # noqa: D400
        """Call. hello? Are you there?"""
        self.prepare_cmd()
        self.execute()
        return self.result.stdout.decode('utf8')

    @property
    def cmd_exec(self):  # noqa: D401
        """Execution command."""
        return self._cmd_exec

    @cmd_exec.setter
    def cmd_exec(self, command):
        try:
            self._cmd_exec = command.split()
        except AttributeError:  # in case cmd is a list
            # corrects for cases where cmd is ['ls -ltr'] for example
            # see tests/test_multicore.py
            self._cmd_exec = []
            for iitem in command:
                self._cmd_exec.extend(iitem.split())

    def prepare_cmd(self):
        """
        Prepare the subprocess command.

        Concatenates the given the cmd_exec input and the input
        parameter itself.
        """
        try:
            self.cmd = self.cmd_exec + self.input
        except TypeError:  # in case input_ is None
            self.cmd = self.cmd_exec

    def execute(self):
        """
        Execute subprocess.run() on the defined task.
        
        May brake if .prepare_cmd() was not executed beforehand.
        """
        log.info(S('running {}', self.cmd))
        self.result = subprocess.run(
            self.cmd,
            capture_output=True,
            )


class DSSPTask(SubprocessTask):
    """Subprocess Task for DSSP third party executable."""
    
    @libcheck.argstype(Task, (list, str), (str, Path))
    def __init__(self, cmd, input_):
        # forces input_ to be positional parameter in subclass DSSPTask
        
        try:
            cmd.append('-i')
        except AttributeError:
            cmd = [cmd, '-i']

        self.pdb_path = input_
        input_ = [input_]

        super().__init__(cmd, input_=input_)
    
    def __call__(self):
        """Call on meeeee :)."""
        self.prepare_cmd()
        self.execute()
        return (self.pdb_path, self.result.stdout.decode('utf8'))


class JoinedResults:
    """
    Execute jobs in a list.

    Given a list of `input_data` and a `command`, creates a queue of
    related [command - input] tasks. These tasks are executed
    as picked from the queue when the previous finishes. Takses are
    executed by :class:`Worker` objects.
    
    As tasks complete, results are stored in the :attr:`results`.

    Parameters
    ----------
    input_data : list
        A list of string to serve as input to the command.

    command : string
        The third party console based command, run by subprocess.

    ncores : int, optional
        The number of cores to use. Defaults to 1.

    TaskMethod : Task sublcass.
        The task interface. See :class:`SubprocessTask` or
        :class:`DSSPTask` for examples.

    results_parser : object
        The object that will parse the subprocess output before being
        saved in the :attr:`results`.
    """

    def __init__(
            self,
            input_data,
            command,
            ncores=1,
            TaskMethod=SubprocessTask,
            results_parser=str,
            ):
        self.input_data = input_data
        self.cmd = command
        self.ncores = ncores
        self.TaskMethod = TaskMethod
        self.rp = results_parser
        
    def build(self):
        """Build tasks, results and workers."""
        self.tasks = multiprocessing.JoinableQueue()
        self.queue_results = multiprocessing.Queue()
        self.workers = \
            [Worker(self.tasks, self.queue_results)
                for i in range(self.ncores)]
    
    def run(self):
        """
        Run tasks.
        
        Executes .build() method beforehand.

        Results are saved in the attribute `results` list, this is
        sorted naturally by the order of subprocess termination.
        """
        self.build()
        
        for w in self.workers:
            w.start()

        for input_datum in self.input_data:
            self.tasks.put(self.TaskMethod(self.cmd, input_datum))

        # Adds a poison pill
        for _w in self.workers:
            self.tasks.put(None)

        self.tasks.join()

        numjobs = len(self.input_data)
        self.results = []
        while numjobs:
            self.results.append(self.rp(self.queue_results.get()))
            numjobs -= 1