#!/bin/bash
aca-py start \
    -it acapy_plugin_toolbox.http_ws 0.0.0.0 "$PORT" \
    -ot http \
    -e "$ACAPY_ENDPOINT" "${ACAPY_ENDPOINT/http/ws}"\
    --label "$AGENT_NAME" \
    --auto-accept-requests --auto-ping-connection \
    --auto-respond-credential-proposal --auto-respond-credential-offer --auto-respond-credential-request --auto-store-credential \
    --auto-respond-presentation-proposal --auto-respond-presentation-request --auto-verify-presentation \
    --invite --invite-role admin --invite-label "$AGENT_NAME (admin)" \
    --genesis-url http://test.bcovrin.vonx.io/genesis \
    --wallet-type indy \
    --wallet-name 'wallet_db' \
    --wallet-key 'development' \
    --wallet-storage-type 'postgres_storage' \
    --wallet-storage-config '{"url":"<RDS_ACAPY_ARN>:5432", "max_connections":5}' \
    --wallet-storage-creds '{"account":"<RDS_ACAPY_USER>","password":"<RDS_ACAPY_PASSWORD>","admin_account":"<RDS_ACAPY_USER>","admin_password":"<RDS_ACAPY_PASSWORD>"}' \
    --plugin acapy_plugin_toolbox \
    --plugin acapy_plugin_data_transfer \
    --admin 0.0.0.0 "$ADMIN_PORT" \
    --admin-insecure-mode \
    --webhook-url "$WEBHOOK_ADDRESS" \
    --debug-connections \
    --debug-credentials \
    --debug-presentations \
    --enable-undelivered-queue \
    --log-level debug \
    --public-invites \
    "$@"
