# Copyright © 2020 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""File processing rules and actions for the incorporation of a business."""
from typing import Dict

import requests
from entity_queue_common.service_utils import logger
from flask import Flask
from legal_api.models import Business

from entity_filer.filing_processors import create_office, create_party, create_role, create_share_class


def get_next_corp_num(business_type: str, application: Flask):
    """Retrieve the next available sequential corp-num from COLIN."""
    resp = requests.get(f'{application.config["COLIN_API"]}?legal_type={business_type}')

    if resp.status_code == 200:
        new_corpnum = resp.json()['corpNum'][0]
        if new_corpnum:
            # TODO: Fix endpoint
            return business_type + str(new_corpnum)
    return None


def update_business_info(corp_num: str, business: Business, business_info: Dict):
    """Format and update the business entity from incorporation filing."""
    if corp_num and business and business_info:
        business.identifier = corp_num
        # TODO: Other properties contained in the NR
    else:
        return None
    return business


def process(business: Business, filing: Dict, app: Flask = None):  # pylint: disable=too-many-locals; 1 extra
    """Process the incoming incorporation filing."""
    # Extract the filing information for incorporation
    incorp_filing = filing['incorporationApplication']

    if incorp_filing:  # pylint: disable=too-many-nested-blocks; 1 extra and code is still very clear
        # Extract the office, business, addresses, directors etc.
        # these will have to be inserted into the db.
        offices = incorp_filing.get('offices', None)
        parties = incorp_filing.get('parties', None)
        business_info = incorp_filing['nameRequest']
        share_classes = incorp_filing['shareClasses']

        # Sanity check
        if business and business.identifier == business_info['nrNumber']:
            # Reserve the Corp Numper for this entity
            corp_num = get_next_corp_num(business_info['legalType'], app)

            # Initial insert of the business record
            business = update_business_info(corp_num, business, business_info)

            if business:
                for office_type, addresses in offices.items():
                    office = create_office(business, office_type, addresses)
                    business.offices.append(office)

                if parties:
                    for party_info in parties:
                        party = create_party(party_info=party_info)
                        for role_type in party_info.get('roles'):
                            role = {
                                'roleType': role_type.get('roleType'),
                                'appointmentDate': role_type.get('appointmentDate', None),
                                'cessationDate': role_type.get('cessationDate', None)
                            }
                            party_role = create_role(party=party, role_info=role)
                            business.party_roles.append(party_role)

                if share_classes:
                    for share_class_info in share_classes:
                        share_class = create_share_class(share_class_info)
                        business.share_classes.append(share_class)
        else:
            logger.error('No business exists for NR number: %s', business_info['nrNUmber'])
