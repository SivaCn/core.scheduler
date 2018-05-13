# -*- coding: utf-8 -*-

"""

    Module :mod:``

    This Module is created to...

    LICENSE: The End User license agreement is located at the entry level.

"""

# ----------- START: Native Imports ---------- #
import json
from datetime import datetime
# ----------- END: Native Imports ---------- #

# ----------- START: Third Party Imports ---------- #
# ----------- END: Third Party Imports ---------- #

# ----------- START: In-App Imports ---------- #
from core.backend.utils.core_utils import (
    get_unique_id, AutoSession, get_loggedin_user_id, decode
)

from core.db.model import (
    CodeScheduleTypeModel, JobDetailsModel, UserModel, ConfigUserSmsModel
)
from core.backend.config import view_client_config
from core.mq import SimpleSchedulerPublisher
from core.backend.utils.core_utils import AutoSession
from core.constants.code_message import filled_code_message
from core.backend.config import get_valve_details
# ----------- END: In-App Imports ---------- #


__all__ = [
    # All public symbols go here.
]


def save_scheduler_config(session, form_data):

    # TODO: move to constants
    _response_dict = {'result': False, 'data': dict(), 'alert_type': None, 'alert_what': None, 'msg': None}

    schedule_data = dict()
    start_date = form_data['start_date']
    schedule_type = form_data['type']

    string_date = "{0}-{1}-{2} {3}:{4}:00"\
        .format(start_date['year'],start_date['month'],start_date['day'],start_date['hour'],start_date['mins'])

    code_schedule_type = CodeScheduleTypeModel.fetch_one(
        session, schedule_type=schedule_type
    )

    schedule_data['schedule_type_idn'] = code_schedule_type.schedule_type_idn

    # TODO: move to constants
    try:
        schedule_data['start_date'] = datetime.strptime(string_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        _response_dict['msg'] = filled_code_message('CM0008')
        _response_dict['data']['is_invalid_date'] = True
        return _response_dict

    schedule_data['job_id'] = get_unique_id()
    schedule_data['user_idn'] = get_loggedin_user_id()

    valve_id = [valve['id'] for valve in form_data['ValveDetails'] if valve['selected']]

    schedule_data['params'] = ','.join(valve_id)
    #schedule_data['recurrence'] = int(form_data['recurs'])
    recurrence = ','.join([str(int(value['id'])) for value in form_data['recurs'] if value['selected']])
    schedule_data['recurrence']  = recurrence

    week_id = [weekday['id'] for weekday in form_data['weekDays'] if weekday['selected']]

    schedule_data['day_of_week'] = ','.join(week_id)

    _params = dict(
        job_id=schedule_data['job_id'],
        schedule_type=schedule_type.lower(),
        user_idn=schedule_data['user_idn'],
        job_action='add',
        start_date=string_date, #schedule_data['start_date'],
        day_of_week=schedule_data['day_of_week'],
        recurrence=schedule_data['recurrence'],
    )

    _result = SimpleSchedulerPublisher().publish(payload=_params)

    if _result:
        # Inserting schedule config into Job details
        job_details_idn = JobDetailsModel.insert(
            session, **schedule_data
        ).job_details_idn

        _response_dict.update(
            {'result': True,
             'alert_type': 'pop-up',
             'level': 'INFO',
             'alert_what': 'user',
             'msg': filled_code_message('CM0014')
             }
        )

        return _response_dict

    _response_dict.update(
        {'result': False,
         'alert_type': 'pop-up',
         'level': 'CRITICAL',
         'alert_what': 'user',
         'msg': filled_code_message('CM0015')
         }
    )

    return _response_dict


def search_scheduled_job(session, form_data):

    _response_dict = {'result': True, 'data': None, 'alert_type': None, 'alert_what': None, 'msg': None}

    _params = dict()
    search_data = dict()

    if form_data['searchByField'].lower() == 'schedule':
        if form_data.get('searchByValue').lower().strip():
            _params['schedule_type_idn'] = form_data['searchByValue']

    elif form_data['searchByField'].lower() == 'user':
        if form_data.get('searchByValue').lower().strip():
            _params['user_idn'] = form_data['searchByValue']

    elif form_data['searchByField'].lower() == 'valve':
        if form_data.get('searchByValue').lower().strip():
            _params['params'] = ('like', form_data['searchByValue'], )

    scheduled_jobs = JobDetailsModel.scheduled_jobs(
        session, data_as_dict=True, **_params
    )

    client_config_data = view_client_config()

    for jobs in scheduled_jobs:

        _recur_freq = [int(e.strip()) for e in jobs['recurrence'].split(',') if jobs['recurrence']]

        jobs['recurrence'] = [
            idx if idx in _recur_freq else value
            for idx, value in enumerate(
                [-1] * (5 if jobs['schedule_type'].lower() == 'weekly' else 31), 1
            )
        ]

        if 'user_name' in jobs:
            jobs['user_name'] = decode(jobs['user_name'])

        if 'params' in jobs:

            jobs['params'] = ', '.join(
                [client_config_data[idn]['name']
                 for idn in jobs['params'].split(',')
                 ]
            )

    _response_dict.update({'data': scheduled_jobs})

    return _response_dict


def deactivate_completed_onetime_jobs(job_id):

    with AutoSession() as session:
        JobDetailsModel.deactivate_jobs(
            session,
            job_id=job_id
        )


def deactivate_scheduled_job(session, form_data):

    _response_dict = {'result': True, 'data': None, 'alert_type': None, 'alert_what': None, 'msg': None}

    job = JobDetailsModel.fetch_one(session, job_details_idn=form_data['job_details_idn'])

    if not job:
        _response_dict.update({'result': False,
                               'data': None,
                               'alert_type': 'alert',
                               'alert_what': None,
                               'msg': filled_code_message('CM0016')
                               })
        return _response_dict

    job_id = job.job_id

    _params = dict(
        job_id=job_id,
        job_action='remove',
    )

    _result = SimpleSchedulerPublisher().publish(payload=_params)

    if _result:
        # Deactivated the Job
        deactivated_jobs = JobDetailsModel.deactivate_jobs(
            session, job_details_idn = form_data['job_details_idn']
        )

        _response_dict.update(
                {'result': True,
                 'data': deactivated_jobs,
                 'alert_type': 'pop-up',
                 'level': 'INFO',
                 'alert_what': 'user',
                 'msg': filled_code_message('CM0017')
                 }
            )

        return _response_dict

    _response_dict.update(
        {'result': False,
         'alert_type': 'pop-up',
         'level': 'CRITICAL',
         'alert_what': 'user',
         'msg': filled_code_message('CM0015')
         }
    )

    return _response_dict


def update_scheduled_job(session, form_data):

    _response_dict = {'result': True, 'data': dict(), 'alert_type': None, 'alert_what': None, 'msg': None}

    schedule_type = form_data['type']

    schedule_data = dict()
    start_date = form_data['start_date']
    job_id = form_data['job_id']

    string_date = "{0}-{1}-{2} {3}:{4}:00"\
        .format(start_date['year'],start_date['month'],start_date['day'],start_date['hour'],start_date['mins'])

    code_schedule_type = CodeScheduleTypeModel.fetch_one(
        session, schedule_type=schedule_type
    )

    schedule_data['schedule_type_idn'] = code_schedule_type.schedule_type_idn

    # TODO: move to constants
    try:
        schedule_data['start_date'] = datetime.strptime(string_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        _response_dict['msg'] = filled_code_message('CM0008')
        _response_dict['data']['is_invalid_date'] = True
        return _response_dict

    schedule_data['job_id'] = job_id
    schedule_data['user_idn'] = get_loggedin_user_id()

    valve_id = [valve['id'] for valve in form_data['ValveDetails'] if valve['selected']]
    schedule_data['params'] = ','.join(valve_id)

    recurrence = [str(value['id']) for value in form_data['recurs'] if value['selected']]
    schedule_data['recurrence'] = ','.join(recurrence)

    week_id = [weekday['id'] for weekday in form_data['weekDays'] if weekday['selected']]

    schedule_data['day_of_week'] = ','.join(week_id)

    _params = dict(
        job_id=schedule_data['job_id'],
        schedule_type=schedule_type.lower(),
        job_action='update',
        start_date=string_date,
        day_of_week=schedule_data['day_of_week'],
        recurrence=schedule_data['recurrence'],
        user_idn=schedule_data['user_idn']
    )

    _result = SimpleSchedulerPublisher().publish(payload=_params)

    if _result:
        # Updating the scheduled Job
        updated_jobs = JobDetailsModel.update_jobs(
            session,
            where_condition={'job_details_idn': form_data['job_details_idn']},
            updates=schedule_data
        )

        _response_dict.update(
            {'result': True,
             'data': updated_jobs,
             'alert_type': 'pop-up',
             'level': 'INFO',
             'alert_what': 'user',
             'msg': filled_code_message('CM0018')
             }
        )

        return _response_dict

    _response_dict.update(
        {'result': False,
         'alert_type': 'pop-up',
         'level': 'CRITICAL',
         'alert_what': 'user',
         'msg': filled_code_message('CM0015')
         }
    )

    return _response_dict


def check_enabled_valves(session, selected_node):
    _response_dict = {'result': True, 'data': dict(), 'alert_type': None, 'alert_what': None, 'msg': None}

    scheduled_jobs = JobDetailsModel.scheduled_jobs(
        session, data_as_dict=True, schedule_type="Select One"
    )

    _response_dict['is_node_available'] = False
    _schedule_type = ''
    for jobs in scheduled_jobs:
        if selected_node in jobs['params']:
            _response_dict['is_node_available'] = True

            if jobs['schedule_type'] not in _schedule_type:
                _schedule_type += (jobs['schedule_type'] + ', ')

    _response_dict['data']['schedule_type'] = _schedule_type
    return _response_dict

def get_sms_config(session):
    _response_dict = {'result': True, 'data': dict(), 'alert_type': None, 'alert_what': None, 'msg': None}

    user_idn = get_loggedin_user_id()
    sms_config_data = ConfigUserSmsModel.fetch_sms_config(session, user_idn=user_idn)

    _response_dict['data'] = sms_config_data
    return _response_dict

def update_sms_config(session, form_data):
    _response_dict = {'result': True, 'data': dict(), 'alert_type': None, 'alert_what': None, 'msg': None}

    updated_sms_config = ConfigUserSmsModel.update(
        session, 
        updates={'is_active': form_data['is_active']}, 
        where_condition={'config_user_sms_idn': form_data['config_user_sms_idn']}
    )

    _response_dict['data'] = updated_sms_config
    return _response_dict

def fetch_scheduler_search_type(session, form_data):
    _response_dict = {'result': True, 'data': dict(), 'alert_type': None, 'alert_what': None, 'msg': None}

    if form_data.lower() == 'user':
        user_data = UserModel.fetch(session, data_as_dict=True)

        _response_dict['data'] = list()

        for user in user_data:
            _response_dict['data'].append({
                'id': user['user_idn'],
                'value': decode(user['user_name'])
            })

    if form_data.lower() == 'schedule':
        schedule_type = CodeScheduleTypeModel.fetch(session, data_as_dict=True)

        _response_dict['data'] = list()

        for type_ in schedule_type:
            _response_dict['data'].append({
                'id': type_['schedule_type_idn'],
                'value': type_['schedule_type']
            })

    if form_data.lower() == 'valve':

        _response_dict['data'] = [
            dict(id=each_valve['id'], value=each_valve['name'])
            for each_valve in get_valve_details()
        ]

    return _response_dict