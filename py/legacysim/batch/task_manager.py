"""Task manager that run tasks in series."""

import sys
import logging
import subprocess


logger = logging.getLogger('legacysim.task_manager')


class BaseTaskManager(object):
    """A dumb task manager, that simply iterates through the tasks in series."""

    def __enter__(self):
        """Return self."""
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Do nothing."""

    def iterate(self, tasks):
        """
        Iterate through a series of tasks.

        Parameters
        ----------
        tasks : iterable
            An iterable of tasks that will be yielded.

        Yields
        -------
        task :
            The individual items of ```tasks``, iterated through in series.
        """
        for task in tasks:
            yield task

    def map(self, function, tasks):
        """
        Apply a function to all of the values in a list and return the list of results.

        If ``tasks`` contains tuples, the arguments are passed to
        ``function`` using the ``*args`` syntax.

        Parameters
        ----------
        function : callable
            The function to apply to the list.
        tasks : list
            The list of tasks.

        Returns
        -------
        results : list
            The list of the return values of ``function``.
        """
        return [function(*(t if isinstance(t,tuple) else (t,))) for t in tasks]


def TaskManager(ntasks=None, **kwargs):
    """
    Switch between non-MPI (ntasks=1) and MPI task managers. To be called as::

        with TaskManager(...) as tm:
            # do stuff

    """
    if ntasks == 1:
        logger.info('Non-MPI task manager')
        self = object.__new__(BaseTaskManager)
    else:
        logger.info('MPI task manager')
        from .mpi_task_manager import MPITaskManager
        self = object.__new__(MPITaskManager)
    self.__init__(**kwargs)
    return self


def run_shell(command, check=False):
    """Run a command in the shell, returning stdout and stderr combined."""
    if isinstance(command,list):
        command = ' '.join(map(str,command))
    print(command)
    sys.stdout.flush()
    output = subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=True,check=check).stdout
    return output.decode('utf-8')
