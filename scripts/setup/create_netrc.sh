#!/usr/bin/env bash
# Crée/complète ~/.netrc pour NASA Earthdata (ASF, NISAR). Le mot de passe est saisi
# en mode masqué et n'est jamais affiché ni passé en argument de commande.
set -euo pipefail
NETRC="$HOME/.netrc"
HOST="urs.earthdata.nasa.gov"
if [ -f "$NETRC" ] && grep -q "machine $HOST" "$NETRC"; then
  echo "Une entrée $HOST existe déjà dans $NETRC — rien à faire."; exit 0
fi
read -rp "Identifiant Earthdata : " EDL_USER
read -rsp "Mot de passe Earthdata : " EDL_PASS; echo
umask 077
printf 'machine %s login %s password %s\n' "$HOST" "$EDL_USER" "$EDL_PASS" >> "$NETRC"
chmod 600 "$NETRC"
unset EDL_PASS
echo "OK : $NETRC créé (droits $(stat -c %a "$NETRC"))."
