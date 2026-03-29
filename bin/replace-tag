#!/usr/bin/env bash
# Copyright (c) 2024, Philip De Lorenzo
# All rights reserved.

# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. 

# We want to make some change to the code, but keep the same tag for the version
RELEASE_TAG="v0.1.0"
git tag --delete "${RELEASE_TAG}"
git push --delete origin "${RELEASE_TAG}"

# Now we can push the new tag
git tag -a "${RELEASE_TAG}" -m "Release: ${RELEASE_TAG} -- SRE Automated Release/Tagging"
git push origin "${RELEASE_TAG}"
