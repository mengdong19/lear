# Copyright © 2019 Province of British Columbia
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
"""This module holds data for corp parties (people/organizations)."""
from __future__ import annotations

from enum import Enum
from http import HTTPStatus

from sqlalchemy import event

from legal_api.exceptions import BusinessException

from .db import db


from .address import Address  # noqa: F401 pylint: disable=unused-import; needed by the SQLAlchemy relationship


class Party(db.Model):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the parties (people and organizations)."""

    class PartyTypes(Enum):
        """Render an Enum of the party types."""

        PERSON = 'person'
        ORGANIZATION = 'organization'

    __versioned__ = {}
    __tablename__ = 'parties'

    id = db.Column(db.Integer, primary_key=True)
    party_type = db.Column('party_type', db.String(30), default=PartyTypes.PERSON.value)
    # person
    first_name = db.Column('first_name', db.String(30), index=True)
    middle_initial = db.Column('middle_initial', db.String(30), index=True)
    last_name = db.Column('last_name', db.String(30))
    title = db.Column('title', db.String(1000))
    # organization
    organization_name = db.Column('organization_name', db.String(150))

    # parent keys
    delivery_address_id = db.Column('delivery_address_id', db.Integer, db.ForeignKey('addresses.id'))
    mailing_address_id = db.Column('mailing_address_id', db.Integer, db.ForeignKey('addresses.id'))

    # Relationships - Address
    delivery_address = db.relationship('Address', foreign_keys=[delivery_address_id])
    mailing_address = db.relationship('Address', foreign_keys=[mailing_address_id])

    def save(self):
        """Save the object to the database immediately."""
        db.session.add(self)
        db.session.commit()

    @property
    def json(self) -> dict:
        """Return the party member as a json object."""
        if self.party_type == Party.PartyTypes.PERSON.value:
            member = {
                'officer': {
                    'firstName': self.first_name,
                    'lastName': self.last_name
                }
            }
            if self.title:
                member['title'] = self.title
            if self.middle_initial:
                member['officer']['middleInitial'] = self.middle_initial
        else:
            member = {
                'officer': {'organizationName': self.organization_name}
            }

        if self.delivery_address:
            member_address = self.delivery_address.json
            if 'addressType' in member_address:
                del member_address['addressType']
            member['deliveryAddress'] = member_address
        if self.mailing_address:
            member_mailing_address = self.mailing_address.json
            if 'addressType' in member_mailing_address:
                del member_mailing_address['addressType']
            member['mailingAddress'] = member_mailing_address
        else:
            if self.delivery_address:
                member['mailingAddress'] = member['deliveryAddress']

        return member

    @property
    def valid_party_type_data(self) -> bool:
        """Validate the model based on the party type (person/organization)."""
        if self.party_type == Party.PartyTypes.ORGANIZATION.value:
            if not self.organization_name or self.first_name or self.middle_initial or self.last_name:
                return False

        elif self.party_type == Party.PartyTypes.PERSON.value:
            if self.organization_name or not (self.first_name or self.middle_initial or self.last_name):
                return False
        return True

    @classmethod
    def find_by_name(cls, first_name: str, last_name: str, organization_name: str) -> Party:
        """Return a Party by the name given."""
        party = None
        if organization_name:
            party = cls.query.filter_by(organization_name=organization_name).one_or_none()
        else:
            party = cls.query.filter_by(first_name=first_name, last_name=last_name).one_or_none()
        return party


@event.listens_for(Party, 'before_insert')
@event.listens_for(Party, 'before_update')
def receive_before_change(mapper, connection, target):  # pylint: disable=unused-argument; SQLAlchemy callback signature
    """Run checks/updates before adding/changing the party model data."""
    party = target

    if not party.valid_party_type_data:
        raise BusinessException(
            error=f'Attempt to change/add {party.party_type} had invalid data.',
            status_code=HTTPStatus.BAD_REQUEST
        )
