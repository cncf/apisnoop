#1/bin/bash
set -e
set -x

git fetch https://github.com/cncf/apisnoop master
git branch -av

TMATE_TMPDIR=$(mktemp -d /tmp/tmate-ci-XXX)
# install tmate
curl -L \
     https://github.com/tmate-io/tmate/releases/download/2.2.1/tmate-2.2.1-static-linux-amd64.tar.gz \
  | tar xvfzC - $TMATE_TMPDIR --strip-components 1
export PATH=$TMATE_TMPDIR:$PATH
# setup socket and ssh key
socket=$TMATE_TMPDIR/socket
ssh_key=$TMATE_TMPDIR/id_rsa
ssh-keygen -f $ssh_key -t rsa -N ''
# was ensure how to specify key to tmate
eval $(ssh-agent)
ssh-add $ssh_key
# launch detached tmate
tmate -S $socket \
      new-session \
      -d -x 80 -y 25 \
      -s ci-session \
      -n ci-window \
      /bin/bash --login
# wait until it is ready
tmate -S $socket wait tmate-ready
# display the tmate ssh and web connections strings
tmate -S $socket display -p '#{tmate_ssh} # #{tmate_web}'
# Should probably replace this sleep, with a poll mechanism
# probably just 'pkill sleep' for now
# what we really want is to pause and what for signal
sleep 300 || true # five mins is enough to test and not block the CI job


# Ensure there are no changes to audit-sources and data-gen
if git diff --quiet master -- audit-sources.yaml  data-gen/
then
  echo "There are no changes from master"
  echo "Not generating new data"
else
  echo "There are changes from master, lets use the most recent changes"
  export APISNOOP_DEST=$ARTIFACTS
  ./apisnoop.sh --install
  ./apisnoop.sh --update-cache
  ./apisnoop.sh --process-cache
  find /logs/artifacts
fi
