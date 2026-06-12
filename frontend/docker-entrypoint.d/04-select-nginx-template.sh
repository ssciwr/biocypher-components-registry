#!/bin/sh
set -eu

mkdir -p /etc/nginx/templates

if [ -f "${TLS_CERTIFICATE_PATH}" ] && [ -f "${TLS_CERTIFICATE_PRIV_PATH}" ]; then
    cp /etc/nginx/template-options/default.conf.https.template /etc/nginx/templates/default.conf.template
else
    cp /etc/nginx/template-options/default.conf.http.template /etc/nginx/templates/default.conf.template
fi
