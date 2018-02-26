
import time

import simplejson as json

from apscheduler.events import (
    EVENT_JOBSTORE_ADDED,
    EVENT_JOBSTORE_REMOVED,
    EVENT_SCHEDULER_START,
    EVENT_SCHEDULER_SHUTDOWN,
    EVENT_JOB_ADDED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    EVENT_JOB_REMOVED,
    EVENT_JOB_EXECUTED
)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

class SchedulerManager(object):

    def __init__(self):

        self.is_scheduler_running = False

        jobstore_type = 'sqlite'
        jobstore_alias = 'job_store'
        misfire_gracetime = 3600
        scheduler_threads = 10

        executors = dict()

        jobstores = {
            'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
        }

        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }
        job_defaults = {
            'coalesce': False ,
            'max_instances': 3
        }

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores, executors=executors, job_defaults=job_defaults
        )

    def start(self):
        self.scheduler.start()
        self.is_scheduler_running = True

    def stop(self):
        self.scheduler.stop()
        self.is_scheduler_running = False

    def restart(self):
        self.stop()
        time.sleep(2)
        self.start()


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

def job_trigger_callback(*args, **kwargs):
    print '................. CALLED ............. {}'.format(kwargs)


class TaskScheduler(SchedulerManager):

    """Singleton Task Scheduler."""

    __metaclass__ = Singleton

    def __init__(self):

        super(self.__class__, self).__init__()

        self.scheduler.add_listener(
            self.job_event_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_MISSED | EVENT_JOB_ERROR
        )

        self.scheduler.add_listener(
            self.sched_event_listener,
            EVENT_SCHEDULER_SHUTDOWN | EVENT_SCHEDULER_START
        )

        self.scheduler.add_listener(
            self.jobstore_event_listener,
            EVENT_JOB_ADDED | EVENT_JOB_REMOVED | EVENT_JOBSTORE_ADDED | EVENT_JOBSTORE_REMOVED
        )

    def __call__(self):
        self.start()

    def job_event_listener(self, event):
        print event, 'JOB EVENT'

    def jobstore_event_listener(self, event):
        print event, 'JOBSTORE EVENT'

    def sched_event_listener(self, event):
        print event, 'SCHEDULER EVENT'

    def process_job(self, payload=None):

        schedule_type = payload.get('schedule_type', '').lower().replace(' ', '')

        recurrence = payload.get('recurrence')
        start_date = {
            'date': payload.get('date'),
            'hour': payload.get('hour'),
            'minute': payload.get('minute'),
            'second': payload.get('second', '00') or '00',
        }

        day_of_week = payload.get('day_of_week')

        job_action = payload.get('job_action')

        if job_action not in ('add', 'update', 'remove', ):
            raise Exception('job action is wrong')

        trigger_map = {
            'onetime': OneTimeTrigger,
            'daily': IntervalTrigger,
            'weekly': CronTrigger
        }

        if schedule_type not in trigger_map:
            raise Exception('schedule type is in-valid')

        Trigger = trigger_map[schedule_type]

        trigger = Trigger()

        if job_action == 'add':

            job = trigger.add_job(
                self.scheduler,
                callback=job_trigger_callback,
                schedule_type=schedule_type,
                recurrence=recurrence,
                start_date=start_date,
                day_of_week=day_of_week,
                job_action=job_action,
                emit_event='InitiateProcess'
            )

            print "Created job:", job.id


class JobTrigger(object):
    def __init__(self):
        pass

    def add_job(self, *args, **kwargs):
        print 'Add new Job'

    def update_job(self, *args, **kwargs):
        print 'Update existing job'

    def remove_job(self, *args, **kwargs):
        print 'Remove job'


class OneTimeTrigger(JobTrigger):

    def add_job(self, scheduler, *args, **kw):

        from uuid import uuid4
        job_id = str(uuid4())

        return scheduler.add_job(
            kw['callback'],
            trigger='date',
            id=job_id,
            args=None,
            kwargs=dict(job_id=job_id, event=kw['emit_event']),
            misfire_grace_time=60,
            max_instances=1,
        )


class IntervalTrigger(JobTrigger):
    pass


class CronTrigger(JobTrigger):
    pass

