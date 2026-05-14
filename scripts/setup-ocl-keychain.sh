#!/usr/bin/env bash
# scripts/setup-ocl-keychain.sh
#
# (Re)create the macOS keychain item that holds the OCL API token, with an ACL
# that allows the `security` CLI to read it WITHOUT prompting for keychain
# password / Touch ID on every access.
#
# Why: by default `security add-generic-password` creates an item whose ACL
# lists no trusted applications. Any subsequent `security find-generic-password`
# call triggers a "Allow access?" dialog. Adding `/usr/bin/security` to the
# trusted-apps list whitelists exactly that one tool and silences the prompt
# while keeping the secret encrypted at rest in the user's login keychain.
#
# Usage:
#   ./scripts/setup-ocl-keychain.sh
#     -> prompts for token (no echo), creates/replaces the keychain item.
#
#   ./scripts/setup-ocl-keychain.sh --rotate
#     -> same; semantic alias for documenting a token rotation event.
#
# The script never echoes the token and never writes it to a file or log.
# The `security` CLI does briefly receive the token on its argv (the `-w VALUE`
# form below) — visible to `ps` for a few milliseconds. On a single-user macOS
# workstation this is the documented apple-recommended invocation and we
# accept the tiny window; on a shared host you should run this script under a
# dedicated account.

set -euo pipefail

SERVICE_NAME="${OCL_KEYCHAIN_SERVICE:-ocl-token}"
ACCOUNT_NAME="${OCL_KEYCHAIN_ACCOUNT:-$(whoami)}"
SECURITY_BIN="/usr/bin/security"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: This script is macOS-only (uses /usr/bin/security)." >&2
  exit 1
fi

echo "Configuring macOS keychain item:"
echo "  service: ${SERVICE_NAME}"
echo "  account: ${ACCOUNT_NAME}"
echo "  trusted: ${SECURITY_BIN}"
echo ""

# Prompt for the token interactively, hidden input, no shell history exposure.
# `read -s` does not echo. Single-quote the variable on use to preserve special chars.
read -r -s -p "Paste OCL API token (input hidden; Enter to submit): " TOKEN
echo ""
echo ""

if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: empty token. Aborting." >&2
  exit 1
fi

# Sanity-check token length (OCL tokens are 40 chars).
if [[ ${#TOKEN} -lt 32 ]]; then
  echo "WARNING: token length is ${#TOKEN}; expected ~40. Proceeding anyway." >&2
fi

# Delete any existing item first (idempotent). `-s SERVICE` matches by service name.
if ${SECURITY_BIN} find-generic-password -s "${SERVICE_NAME}" -w >/dev/null 2>&1; then
  echo "Removing existing keychain item (will be replaced)..."
  ${SECURITY_BIN} delete-generic-password -s "${SERVICE_NAME}" >/dev/null 2>&1 || true
fi

# Add with `-T /usr/bin/security` to whitelist this binary in the ACL.
# `-U` means "upsert" (update if exists). `-w` reads value from stdin if not given;
# we pass it via `-w` arg to avoid an extra round-trip.
${SECURITY_BIN} add-generic-password \
  -s "${SERVICE_NAME}" \
  -a "${ACCOUNT_NAME}" \
  -l "${SERVICE_NAME}" \
  -D "OCL API token" \
  -T "${SECURITY_BIN}" \
  -U \
  -w "${TOKEN}"

# Clear the token from this shell's environment as soon as we're done.
unset TOKEN

echo "Keychain item created."
echo ""
echo "Verifying retrieval (should print 'OK' with no password / Touch ID prompt)..."
if ${SECURITY_BIN} find-generic-password -s "${SERVICE_NAME}" -w >/dev/null 2>&1; then
  echo "OK"
else
  echo "FAILED — retrieval still prompts or fails." >&2
  exit 1
fi

echo ""
echo "Done. Future calls to:"
echo "  security find-generic-password -s ${SERVICE_NAME} -w"
echo "will return the token silently."
