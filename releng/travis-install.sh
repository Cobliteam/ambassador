#!/usr/bin/env bash

# Copyright 2018 Datawire. All rights reserved.
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
# limitations under the License

GO_VERSION=1.13
HELM_VERSION=2.9.1
KUBECTL_VERSION=1.10.2
KUBERNAUT_VERSION=2018.10.24-d46c1f1
KIND_VERSION=v0.7.0  # see https://github.com/kubernetes-sigs/kind/releases

# The ingress conformance tests (as a Zip, from GitHub)
INGRESS_CONFORMANCE_TESTS_ZIP="https://github.com/alexgervais/ingress-controller-conformance/archive/ambassador-ref.zip"
INGRESS_CONFORMANCE_TESTS_DIR="$HOME/ingress-conformance-tests"

set -o errexit
set -o nounset
set -o xtrace

printf "== Begin: travis-install.sh ==\n"

mkdir -p ~/bin
PATH=~/bin:$PATH

# Install kubectl
curl -L -o ~/bin/kubectl https://storage.googleapis.com/kubernetes-release/release/v${KUBECTL_VERSION}/bin/linux/amd64/kubectl
chmod +x ~/bin/kubectl

# Install helm
curl -L https://storage.googleapis.com/kubernetes-helm/helm-v${HELM_VERSION}-linux-amd64.tar.gz | tar -x -z -O linux-amd64/helm > ~/bin/helm
chmod +x ~/bin/helm
helm init --client-only # Initialize helm for indexing use

# Install kubernaut
curl -L -o ~/bin/kubernaut http://releases.datawire.io/kubernaut/${KUBERNAUT_VERSION}/linux/amd64/kubernaut
chmod +x ~/bin/kubernaut

# Install Go
gimme ${GO_VERSION}
source ~/.gimme/envs/latest.env

# Install awscli
sudo pip install awscli

# Install KIND (for running the Ingress v1 conformance tests)
curl -Lo ~/bin/kind "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-$(uname)-amd64"
chmod +x ~/bin/kind

# Install the Ingress Conformance tests
TMP_DIR=$(mktemp -d -t ingress-conf-XXXX)
cleanup() { rm -rf "$TMP_DIR" ; }
trap cleanup EXIT
curl -L -o $TMP_DIR/ingress.zip $INGRESS_CONFORMANCE_TESTS_ZIP && \
    cd $TMP_DIR && \
	unzip -xU ingress.zip && \
	rm -f $TMP_DIR/ingress.zip && \
	rm -rf $INGRESS_CONFORMANCE_TESTS_DIR && \
	mv $TMP_DIR/* $INGRESS_CONFORMANCE_TESTS_DIR

# Configure kubernaut
base64 -d < kconf.b64 | ( cd ~ ; tar xzf - )
# Grab a kubernaut cluster
CLAIM_NAME=kat-${USER}-$(uuidgen)
DEV_KUBECONFIG=~/.kube/${CLAIM_NAME}.yaml
echo $CLAIM_NAME > ~/kubernaut-claim.txt
kubernaut claims delete ${CLAIM_NAME}
kubernaut claims create --name ${CLAIM_NAME} --cluster-group main
# Do a quick sanity check on that cluster
kubectl --kubeconfig ${DEV_KUBECONFIG} -n default get service kubernetes

# Print Kubernetes version
kubectl --kubeconfig ${DEV_KUBECONFIG} version

printf "== End:   travis-install.sh ==\n"
