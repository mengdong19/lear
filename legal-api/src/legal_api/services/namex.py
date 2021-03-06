# Copyright © 2020 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This provides the service for namex-api calls."""
from datetime import datetime
from enum import Enum

import requests
from flask import current_app


class NameXService():
    """Provides services to use the namex-api."""

    class State(Enum):
        """Name request states."""

        APPROVED = 'APPROVED'
        CANCELLED = 'CANCELLED'
        COMPLETED = 'COMPLETED'
        CONDITIONAL = 'CONDITIONAL'
        DRAFT = 'DRAFT'
        EXPIRED = 'EXPIRED'
        HISTORICAL = 'HISTORICAL'
        HOLD = 'HOLD'
        INPROGRESS = 'INPROGRESS'
        REJECTED = 'REJECTED'
        NRO_UPDATING = 'NRO_UPDATING'

    @staticmethod
    def query_nr_number(identifier: str):
        """Return a JSON object with name request information."""
        auth_url = current_app.config.get('NAMEX_AUTH_SVC_URL')
        username = current_app.config.get('NAMEX_SERVICE_CLIENT_USERNAME')
        secret = current_app.config.get('NAMEX_SERVICE_CLIENT_SECRET')
        namex_url = current_app.config.get('NAMEX_SVC_URL')

        # Get access token for namex-api in a different keycloak realm
        auth = requests.post(auth_url, auth=(username, secret), headers={
            'Content-Type': 'application/x-www-form-urlencoded'}, data={'grant_type': 'client_credentials'})

        # Return the auth response if an error occurs
        if auth.status_code != 200:
            return auth.json()

        token = dict(auth.json())['access_token']

        # Perform proxy call using the inputted identifier (e.g. NR 1234567)
        nr_response = requests.get(namex_url + 'requests/' + identifier, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
            })

        return nr_response

    @staticmethod
    def validate_nr(nr_json):
        """Provide validation info based on a name request response payload."""
        # Initial validation result state
        is_consumable = False
        is_approved = False
        is_expired = False
        consent_required = None
        consent_received = None
        nr_state = nr_json['state']

        if nr_json['expirationDate']:
            expiration_date = datetime.strptime(nr_json['expirationDate'], '%a, %d %b %Y %H:%M:%S %Z')
            if expiration_date < datetime.today():
                is_expired = True

        # Not consumable and not approved
        if nr_state not in (NameXService.State.APPROVED.value, NameXService.State.CONDITIONAL.value):
            is_consumable = False
            is_approved = False

        # Is approved
        elif nr_state == NameXService.State.APPROVED.value:
            is_approved = True
            consumed = False
            # Approved, but check if it has been consumed
            for name in nr_json['names']:
                # Already consumed
                if name['consumptionDate']:
                    consumed = True
            if not consumed:
                is_consumable = True

        # Is conditionally approved
        elif nr_state == NameXService.State.CONDITIONAL.value:
            is_approved = True
            consent_required = True
            consent_received = False
            # Check if consent received
            if nr_json['consentFlag'] == 'R':
                consent_received = True
                is_consumable = True

        return {
            'is_consumable': is_consumable,
            'is_approved': is_approved,
            'is_expired': is_expired,
            'consent_required': consent_required,
            'consent_received': consent_received
            }
