#!/usr/bin/env bash
set -x

# Deploy APISnoop in kind

kind create cluster --config kind+apisnoop.yaml
# ensure auditlogger is ready to apisnoop on k8s
kubectl wait --for=condition=Ready --selector=app.kubernetes.io/name=auditlogger --timeout=600s pod
export PGUSER=apisnoop
export PGHOST=localhost

# install gateway

cat <<EOF | glooctl install gateway --values -
gatewayProxies:
  gatewayProxy:
    service:
      type: NodePort
      httpPort: 31500
      httpsPort: 32500
      httpNodePort: 31500
      httpsNodePort: 32500
EOF

# wait for gloo deployment to be Available


kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=gateway
kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=gateway-proxy
kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=discovery
kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=gloo

# deploy petstore

kubectl apply -f https://raw.githubusercontent.com/solo-io/gloo/v1.2.9/example/petstore/petstore.yaml

kubectl label namespace default  discovery.solo.io/function_discovery=enabled  --overwrite

# wait for petstore deployment to be Available


kubectl wait deployment --for=condition=Available --selector=app=petstore

# Add route


glooctl add route \
  --path-exact /all-pets \
  --dest-name default-petstore-8080 \
  --prefix-rewrite /api/pets

# ensure default virutalservice is Accepted

set +x
echo -n Waiting for default virtual service to be Accepted...
while [ $(glooctl get virtualservice  default -o json | jq -r '.[0].status.state') != "Accepted" ] ; do echo -n . ; sleep 1 ; done
echo !
glooctl get virtualservice  default
echo -n Waiting for upstream default-petstore-8080 to be Accepted...
while [ $(glooctl get upstream default-petstore-8080 -o json | jq -r '.[0].status.state') != "Accepted" ] ; do echo -n . ; sleep 1 ; done
echo !
glooctl get upstream default-petstore-8080
set -x

# Connect to route

curl $(glooctl proxy url)/all-pets

# psql

PGUSER='apisnoop'
PGHOST='localhost'
psql -U apisnoop -h localhost -c "select useragent from testing.audit_event where useragent like 'gloo%' group by useragent;"
psql -U apisnoop -h localhost -c "select useragent, endpoint, tested, conf_tested
  from        testing.audit_event
         join endpoint_coverage ec using(endpoint)
 where useragent like 'gloo%'
   and ec.release = '1.20.0'
   and conf_tested = false
 group by endpoint, ec.release, tested, conf_tested, useragent
 order by conf_tested asc;"
