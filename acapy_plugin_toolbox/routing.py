"""BasicMessage Plugin."""
# pylint: disable=invalid-name, too-few-public-methods

from typing import Union
from datetime import datetime

from marshmallow import fields

from aries_cloudagent.core.profile import ProfileSession
from aries_cloudagent.core.protocol_registry import ProtocolRegistry
from aries_cloudagent.connections.models.conn_record import (
    ConnRecord
)
from aries_cloudagent.messaging.base_handler import (
    BaseHandler, BaseResponder, RequestContext
)
from aries_cloudagent.protocols.coordinate_mediation.v1_0.manager import MediationManager
from aries_cloudagent.protocols.coordinate_mediation.v1_0.messages.mediate_request import \
    MediationRequest
from aries_cloudagent.protocols.coordinate_mediation.v1_0.models.mediation_record import (
    MediationRecord, MediationRecordSchema
)
from aries_cloudagent.protocols.routing.v1_0.models.route_record import RouteRecordSchema
from aries_cloudagent.protocols.problem_report.v1_0.message import \
    ProblemReport
from aries_cloudagent.protocols.coordinate_mediation.v1_0.messages.keylist_update import KeylistUpdate
from aries_cloudagent.protocols.coordinate_mediation.v1_0.messages.inner.keylist_update_rule import KeylistUpdateRule
from aries_cloudagent.storage.error import StorageNotFoundError
from aries_cloudagent.protocols.coordinate_mediation.v1_0.message_types import KEYLIST
from aries_cloudagent.protocols.coordinate_mediation.v1_0.messages.keylist import KeylistSchema
from marshmallow import fields
from marshmallow.validate import OneOf

from .util import admin_only, generate_model_schema

ADMIN_PROTOCOL_URI = "https://github.com/hyperledger/" \
    "aries-toolbox/tree/master/docs/admin-routing/0.1"

SEND_UPDATE = f"{ADMIN_PROTOCOL_URI}/send_update"
MEDIATION_REQUESTS_GET = f"{ADMIN_PROTOCOL_URI}/mediation-requests-get"
MEDIATION_REQUESTS = f"{ADMIN_PROTOCOL_URI}/mediation-requests"
MEDIATION_REQUEST_SEND = f"{ADMIN_PROTOCOL_URI}/mediation-request-send"
MEDIATION_REQUEST_SENT = f"{ADMIN_PROTOCOL_URI}/mediation-request-sent"
KEYLIST_UPDATE_SEND = f"{ADMIN_PROTOCOL_URI}/keylist-update-send"
KEYLIST_UPDATE_SENT = f"{ADMIN_PROTOCOL_URI}/keylist-update-sent"
ROUTES_GET = f"{ADMIN_PROTOCOL_URI}/routes-get"
ROUTES = f"{ADMIN_PROTOCOL_URI}/routes"

MESSAGE_TYPES = {
    MEDIATION_REQUESTS_GET: 'acapy_plugin_toolbox.routing.MediationRequestsGet',
    MEDIATION_REQUESTS: 'acapy_plugin_toolbox.routing.MediationRequests',
    MEDIATION_REQUEST_SEND: 'acapy_plugin_toolbox.routing.MediationRequestSend',
    MEDIATION_REQUEST_SENT: 'acapy_plugin_toolbox.routing.MediationRequestSent',
    KEYLIST_UPDATE_SEND: 'acapy_plugin_toolbox.routing.KeylistUpdateSend',
    KEYLIST_UPDATE_SENT: 'acapy_plugin_toolbox.routing.KeylistUpdateSent',
    ROUTES_GET: 'acapy_plugin_toolbox.routing.RoutesGet',
    ROUTES: 'acapy_plugin_toolbox.routing.Routes'
}


async def setup(
        session: ProfileSession,
        protocol_registry: ProblemReport = None
):
    """Setup the routing plugin."""
    if not protocol_registry:
        protocol_registry = session.inject(ProtocolRegistry)
    protocol_registry.register_message_types(
        MESSAGE_TYPES
    )


MediationRequestsGet, MediationRequestsGetSchema = generate_model_schema(
    name='MediationRequestsGet',
    handler='acapy_plugin_toolbox.routing.MediationRequestsGetHandler',
    msg_type=MEDIATION_REQUESTS_GET,
    schema={
        'state': fields.Str(required=False),
        'connection_id': fields.Str(required=False)
    }
)

MediationRequests, MediationRequestsSchema = generate_model_schema(
    name='MediationRequests',
    handler='acapy_plugin_toolbox.util.PassHandler',
    msg_type=MEDIATION_REQUESTS,
    schema={
        'requests': fields.List(fields.Nested(MediationRecordSchema))
    }
)


class MediationRequestsGetHandler(BaseHandler):
    """Handler for received mediation requests get messages."""

    @admin_only
    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle mediation requests get message."""
        tag_filter = dict(
            filter(lambda item: item[1] is not None, {
                'state': context.message.state,
                'role': MediationRecord.ROLE_CLIENT,
                'connection_id': context.message.connection_id
            }.items())
        )
        records = await MediationRecord.query(context, tag_filter=tag_filter)
        response = MediationRequests(requests=records)
        response.assign_thread_from(context.message)
        await responder.send_reply(response)


MediationRequestSend, MediationRequestSendSchema = generate_model_schema(
    name='MediationRequestSend',
    handler='acapy_plugin_toolbox.routing.SendMediationRequestHandler',
    msg_type=MEDIATION_REQUEST_SEND,
    schema={
        'connection_id': fields.Str(required=True),
        'mediator_terms': fields.List(fields.Str(), required=False),
        'recipient_terms': fields.List(fields.Str(), required=False),
    }
)
MediationRequestSent, MediationRequestSentSchema = generate_model_schema(
    name="MediationRequestSent",
    handler="acapy_plugin_toolbox.util.PassHandler",
    msg_type=MEDIATION_REQUEST_SENT,
    schema={
        'connection_id': fields.Str(required=True)
    }
)


class SendMediationRequestHandler(BaseHandler):
    """Handler for sending mediation requests."""

    @admin_only
    async def handle(self, context: RequestContext, responder: BaseResponder):
        # Verify connection exists
        try:
            connection = await ConnectionRecord.retrieve_by_id(
                context,
                context.message.connection_id
            )
        except StorageNotFoundError:
            report = ProblemReport(
                explain_ltxt='Connection not found.',
                who_retries='none'
            )
            report.assign_thread_from(context.message)
            await responder.send_reply(report)
            return

        # Create record
        record = MediationRecord(
            role=MediationRecord.ROLE_CLIENT,
            connection_id=connection.connection_id
        )
        await record.save(context, reason="Sending new mediation request")

        # Construct message
        mediation_request = MediationRequest(
            mediator_terms=context.message.mediator_terms,
            recipient_terms=context.message.recipient_terms,
        )

        # Send mediation request
        await responder.send(
            mediation_request,
            connection_id=connection.connection_id,
        )

        # Send notification of mediation request sent
        sent = MediationRequestSent(connection_id=connection.connection_id)
        sent.assign_thread_from(context.message)
        await responder.send_reply(sent)


KeylistUpdateSend, KeylistUpdateSendSchema = generate_model_schema(
    name='KeylistUpdateSend',
    handler='acapy_plugin_toolbox.routing.KeylistUpdateSendHandler',
    msg_type=KEYLIST_UPDATE_SEND,
    schema={
        'connection_id': fields.Str(required=True),
        'verkey': fields.Str(required=True),
        'action': fields.Str(
            required=True,
            validate=OneOf({'add', 'remove'})
        ),
    }
)


KeylistUpdateSent, KeylistUpdateSentSchema = generate_model_schema(
    name='KeylistUpdateSent',
    handler='acapy_plugin_toolbox.util.PassHandler',
    msg_type=KEYLIST_UPDATE_SENT,
    schema={
        'connection_id': fields.Str(required=True),
        'verkey': fields.Str(required=True),
        'action': fields.Str(
            required=True,
            validate=OneOf({'add', 'remove'})
        ),
    }
)


class KeylistUpdateSendHandler(BaseHandler):
    """Handler KeylistUpdateSend request."""

    @admin_only
    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle KeylistUpdateSend messages."""
        manager = MediationManager(context)
        if context.message.action == KeylistUpdateRule.RULE_ADD:
            update = await manager.add_key(
                context.message.verkey,
                context.message.connection_id
            )
        elif context.message.action == KeylistUpdateRule.RULE_REMOVE:
            update = await manager.remove_key(
                context.message.verkey,
                context.message.connection_id
            )

        await responder.send(
            update,
            connection_id=context.message.connection_id,
        )

        sent = KeylistUpdateSent(
            connection_id=context.message.connection_id,
            verkey=context.message.verkey,
            action=context.message.action
        )
        sent.assign_thread_from(context.message)
        await responder.send_reply(sent)


RoutesGet, RoutesGetSchema = generate_model_schema(
    name='RoutesGet',
    handler='acapy_plugin_toolbox.routing.RoutesGetHandler',
    msg_type=ROUTES_GET,
    schema={
        'connection_id': fields.Str(required=False)
    }
)


Routes, RoutesSchema = generate_model_schema(
    name='Routes',
    handler='acapy_plugin_toolbox.util.PassHandler',
    msg_type=ROUTES,
    schema={
        'routes': fields.List(fields.Nested(RouteRecordSchema))
    }
)


class RoutesGetHandler(BaseHandler):
    """Handler for RoutesGet."""

    @admin_only
    async def handle(self, context: RequestContext, responder: BaseResponder):
        """Handle RotuesGet."""
        manager = MediationManager(context)
        routes = Routes(routes=await manager.get_my_keylist(context.message.connection_id))
        routes.assign_thread_from(context.message)
        await responder.send_reply(routes)
