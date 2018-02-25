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
    get_unique_id, AutoSession, get_loggedin_user_id
)

from core.db.model import (
    CodeScheduleTypeModel, JobDetailsModel, UserModel
)
# ----------- END: In-App Imports ---------- #


__all__ = [
    # All public symbols go here.
]


def save_scheduler_config(form_data):

    # TODO: move to constants
    _response_dict = {'result': False, 'data': None, 'alert_type': None, 'alert_what': None, 'msg': None}

    schedule_data = dict()
    start_date = form_data['start_date']
    string_date = "{0}-{1}-{2} {3}:{4}:00"\
        .format(start_date['year'],start_date['month'],start_date['day'],start_date['hour'],start_date['mins'])    

    with AutoSession() as auto_session:
        code_schedule_type = CodeScheduleTypeModel.fetch_one(
            auto_session, schedule_type=form_data['type']
        )

        schedule_data['schedule_type_idn'] = code_schedule_type.schedule_type_idn

        # TODO: move to constants
        schedule_data['start_date'] = datetime.strptime(string_date, "%Y-%m-%d %H:%M:%S")
        schedule_data['job_id'] = get_unique_id()
        schedule_data['user_idn'] = get_loggedin_user_id()

        valve_id = [valve['id'] for valve in form_data['ValveDetails'] if valve['selected']]

        schedule_data['params'] = ','.join(valve_id)
        schedule_data['recurrence'] = form_data['recurs']

        week_id = [weekday['id'] for weekday in form_data['weekDays'] if weekday['selected']]

        schedule_data['day_of_week'] = ','.join(week_id)

        # Inserting schedule config into Job details
        job_details_idn = JobDetailsModel.insert(
            auto_session, **schedule_data
        ).job_details_idn

    return _response_dict


def search_scheduled_job(form_data):

    _response_dict = {'result': list(), 'alert_type': None, 'alert_what': None, 'msg': None}

    search_data = dict()
    schedule_type = form_data['searchScheduleType']
    with AutoSession() as auto_session:
        code_schedule_type = CodeScheduleTypeModel.fetch_one(
            auto_session, schedule_type=schedule_type
        )

        if form_data['searchScheduleType'] == 'Select One':
            search_data['is_active'] = 1
        else:
            search_data['schedule_type_idn'] = code_schedule_type.schedule_type_idn

        scheduled_job_data = JobDetailsModel.fetch(
            auto_session, **search_data
        )

        for jobs in scheduled_job_data:

            result_set = dict()
            code_schedule_type_data = CodeScheduleTypeModel.fetch_one(
                auto_session, schedule_type_idn=jobs.schedule_type_idn
            )
            
            result_set['schedule_type'] = code_schedule_type_data.schedule_type
            result_set['start_date'] = str(jobs.start_date)

            scheduled_user_name = UserModel.fetch_user_data(
                auto_session, mode='one', user_idn=jobs.user_idn
            )
            result_set['user_name'] = "{0}, {1}".format(
                scheduled_user_name.first_name, scheduled_user_name.last_name)

            result_set['params'] = jobs.params

            _response_dict['result'].append(result_set)

    return _response_dict
