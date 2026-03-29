#!/usr/bin/env bash
# Copyright (c) 2024, Philip De Lorenzo
# All rights reserved.

# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. 

set -eo pipefail

BASE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
MAIN="${BASE}/.."
_GROUP=$(groups | awk -F' ' '{print $1}')
PYTHON=$(command -v python)

asdf_plugin_add()
{
    # Add the plugin in asdf
    asdf plugin add "${1}"
}

plugins()
{
    # Let's iterate over the .tool-versions file and then install the plugin
    echo "[INFO] - Running asdf plugin additions..."
    while IFS= read -r line; do
        if [[ -n $(echo "${line}" | grep -v '^#' || true) ]]; then
            plugin=$(echo "${line}" | cut -d' ' -f 1)
            # If the plugin is not already installed, install it, else pass
            if [[ -z $(asdf list | grep "${plugin}" || true) ]]; then
                echo "[INFO] - Installing plugin ${plugin}"
                asdf_plugin_add "${plugin}"
            else
                echo "[INFO] - Plugin '${plugin}' is installed already..."
            fi
        fi
    done < "${MAIN}/.tool-versions"

    echo "[INFO] - Running asdf plugin installations..."
    asdf install
}

asdf_installation()
{
    # Let's check for an asdf installation and use that locally
    _asdf=$(command -v asdf)
    # shellcheck disable=SC2236
    if [[ -z ${_asdf} ]]; then
        brew install asdf
        plugins # Let's add and install needed plugins, i.e. ~> Python, Terraform, etc.
    else
        plugins # Let's add and install needed plugins, i.e. ~> Python, Terraform, etc.
    fi
}

python_installation()
{
    python -m virtualenv "${MAIN}/.python"
    "${MAIN}"/.python/bin/pip install --upgrade pip
    "${MAIN}"/.python/bin/python -m pip install -r requirements.txt
}

completed()
{
    echo "[INFO] - Script complete!"
}

usage() { echo "Usage: $0 [-a asdf] [-p [Python Install Flag]]" 1>&2; exit 1; }

while getopts ":ap" arg; do
    case "${arg}" in
        a)
            asdf_installation
            completed
            ;;
        p)
            python_installation
            completed
            ;;
        \?)
            echo "[ERROR] - Unknown flag passed"
            usage
            ;;
        :)
            echo "[ERROR] - Option -${arg} requires an argument." >&2
            exit 1
            ;;
        *)
            usage
    esac
done

unset_data()
{
    unset _GROUP
    unset BASE
    unset _INFO_NAME
    unset LOCATION
    unset _PUBLICFILENAME
}

# Let's clean up the data.
unset_data

shift $((OPTIND-1))
