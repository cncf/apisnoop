- [Gloo](#sec-1)
  - [Deploy APISnoop in kind](#sec-1-1)
  - [install gloo](#sec-1-2)
  - [install gateway](#sec-1-3)
  - [wait for gloo deployment to be Available](#sec-1-4)
  - [deploy petstore](#sec-1-5)
  - [wait for petstore deployment to be Available](#sec-1-6)
  - [Add route](#sec-1-7)
  - [ensure default virutalservice is Accepted](#sec-1-8)
  - [Connect to route](#sec-1-9)
- [SQL Research](#sec-2)
  - [clients](#sec-2-1)
  - [endpoints](#sec-2-2)
  - [psql](#sec-2-3)
  - [untested](#sec-2-4)


# Gloo<a id="sec-1"></a>

```tmate
#!/usr/bin/env bash
set -x
```

## Deploy APISnoop in kind<a id="sec-1-1"></a>

```tmate
kind create cluster --config kind+apisnoop.yaml
# ensure auditlogger is ready to apisnoop on k8s
kubectl wait --for=condition=Ready --selector=app.kubernetes.io/name=auditlogger --timeout=600s pod
export PGUSER=apisnoop
export PGHOST=localhost
```

## install gloo<a id="sec-1-2"></a>

```tmate
brew install solo-io/tap/glooctl
```

```shell
glooctl version
```

    Client: {"version":"1.3.17"}
    Server: {"type":"Gateway","kubernetes":{"containers":[{"Tag":"1.3.17","Name":"discovery","Registry":"quay.io/solo-io"},{"Tag":"1.3.17","Name":"gateway","Registry":"quay.io/solo-io"},{"Tag":"1.3.17","Name":"gloo-envoy-wrapper","Registry":"quay.io/solo-io"},{"Tag":"1.3.17","Name":"gloo","Registry":"quay.io/solo-io"}],"namespace":"gloo-system"}}

## install gateway<a id="sec-1-3"></a>

```shell
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
```

## wait for gloo deployment to be Available<a id="sec-1-4"></a>

```shell
kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=gateway
kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=gateway-proxy
kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=discovery
kubectl wait deployment -n gloo-system --for=condition=Available --selector=gloo=gloo
```

    deployment.apps/gateway condition met
    deployment.apps/gateway-proxy condition met
    deployment.apps/discovery condition met
    deployment.apps/gloo condition met

## deploy petstore<a id="sec-1-5"></a>

```shell
kubectl apply -f https://raw.githubusercontent.com/solo-io/gloo/v1.2.9/example/petstore/petstore.yaml
```

    deployment.apps/petstore unchanged
    service/petstore unchanged

```shell
kubectl get svc petstore
```

    NAME       TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
    petstore   ClusterIP   10.96.139.41   <none>        8080/TCP   11m

```shell
glooctl get upstreams
```

    +---------------------------------|------------|----------|------------------------------+
    |            UPSTREAM             |    TYPE    |  STATUS  |           DETAILS            |
    +---------------------------------|------------|----------|------------------------------+
    | default-kubernetes-443          | Kubernetes | Accepted | svc name:      kubernetes    |
    |                                 |            |          | svc namespace: default       |
    |                                 |            |          | port:          443           |
    |                                 |            |          |                              |
    | default-petstore-8080           | Kubernetes | Accepted | svc name:      petstore      |
    |                                 |            |          | svc namespace: default       |
    |                                 |            |          | port:          8080          |
    |                                 |            |          | REST service:                |
    |                                 |            |          | functions:                   |
    |                                 |            |          | - addPet                     |
    |                                 |            |          | - deletePet                  |
    |                                 |            |          | - findPetById                |
    |                                 |            |          | - findPets                   |
    |                                 |            |          |                              |
    | gloo-system-gateway-443         | Kubernetes | Accepted | svc name:      gateway       |
    |                                 |            |          | svc namespace: gloo-system   |
    |                                 |            |          | port:          443           |
    |                                 |            |          |                              |
    | gloo-system-gateway-proxy-31500 | Kubernetes | Accepted | svc name:      gateway-proxy |
    |                                 |            |          | svc namespace: gloo-system   |
    |                                 |            |          | port:          31500         |
    |                                 |            |          |                              |
    | gloo-system-gateway-proxy-32500 | Kubernetes | Pending  | svc name:      gateway-proxy |
    |                                 |            |          | svc namespace: gloo-system   |
    |                                 |            |          | port:          32500         |
    |                                 |            |          |                              |
    | gloo-system-gloo-9966           | Kubernetes | Accepted | svc name:      gloo          |
    |                                 |            |          | svc namespace: gloo-system   |
    |                                 |            |          | port:          9966          |
    |                                 |            |          |                              |
    | gloo-system-gloo-9977           | Kubernetes | Accepted | svc name:      gloo          |
    |                                 |            |          | svc namespace: gloo-system   |
    |                                 |            |          | port:          9977          |
    |                                 |            |          |                              |
    | gloo-system-gloo-9979           | Kubernetes | Accepted | svc name:      gloo          |
    |                                 |            |          | svc namespace: gloo-system   |
    |                                 |            |          | port:          9979          |
    |                                 |            |          |                              |
    | gloo-system-gloo-9988           | Kubernetes | Accepted | svc name:      gloo          |
    |                                 |            |          | svc namespace: gloo-system   |
    |                                 |            |          | port:          9988          |
    |                                 |            |          |                              |
    | kube-system-kube-dns-53         | Kubernetes | Accepted | svc name:      kube-dns      |
    |                                 |            |          | svc namespace: kube-system   |
    |                                 |            |          | port:          53            |
    |                                 |            |          |                              |
    | kube-system-kube-dns-9153       | Kubernetes | Accepted | svc name:      kube-dns      |
    |                                 |            |          | svc namespace: kube-system   |
    |                                 |            |          | port:          9153          |
    |                                 |            |          |                              |
    +---------------------------------|------------|----------|------------------------------+

```shell
glooctl get upstream default-petstore-8080 --output kube-yaml
```

```yaml
apiVersion: gloo.solo.io/v1
kind: Upstream
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"v1","kind":"Service","metadata":{"annotations":{},"labels":{"service":"petstore"},"name":"petstore","namespace":"default"},"spec":{"ports":[{"port":8080,"protocol":"TCP"}],"selector":{"app":"petstore"}}}
  creationTimestamp: null
  generation: 4
  labels:
    discovered_by: kubernetesplugin
    service: petstore
  name: default-petstore-8080
  namespace: gloo-system
  resourceVersion: "3333"
spec:
  discoveryMetadata: {}
  kube:
    selector:
      app: petstore
    serviceName: petstore
    serviceNamespace: default
    servicePort: 8080
    serviceSpec:
      rest:
        swaggerInfo:
          url: http://petstore.default.svc.cluster.local:8080/swagger.json
        transformations:
          addPet:
            body:
              text: '{"id": {{ default(id, "") }},"name": "{{ default(name, "")}}","tag":
                "{{ default(tag, "")}}"}'
            headers:
              :method:
                text: POST
              :path:
                text: /api/pets
              content-type:
                text: application/json
          deletePet:
            headers:
              :method:
                text: DELETE
              :path:
                text: /api/pets/{{ default(id, "") }}
              content-type:
                text: application/json
          findPetById:
            body: {}
            headers:
              :method:
                text: GET
              :path:
                text: /api/pets/{{ default(id, "") }}
              content-length:
                text: "0"
              content-type: {}
              transfer-encoding: {}
          findPets:
            body: {}
            headers:
              :method:
                text: GET
              :path:
                text: /api/pets?tags={{default(tags, "")}}&limit={{default(limit,
                  "")}}
              content-length:
                text: "0"
              content-type: {}
              transfer-encoding: {}
status:
  reported_by: gloo
  state: 1

```

```shell
kubectl label namespace default  discovery.solo.io/function_discovery=enabled  --overwrite
```

    namespace/default not labeled

```shell
glooctl get upstream default-petstore-8080
```

    +-----------------------|------------|----------|-------------------------+
    |       UPSTREAM        |    TYPE    |  STATUS  |         DETAILS         |
    +-----------------------|------------|----------|-------------------------+
    | default-petstore-8080 | Kubernetes | Accepted | svc name:      petstore |
    |                       |            |          | svc namespace: default  |
    |                       |            |          | port:          8080     |
    |                       |            |          | REST service:           |
    |                       |            |          | functions:              |
    |                       |            |          | - addPet                |
    |                       |            |          | - deletePet             |
    |                       |            |          | - findPetById           |
    |                       |            |          | - findPets              |
    |                       |            |          |                         |
    +-----------------------|------------|----------|-------------------------+

```shell
glooctl get upstream default-petstore-8080 --output kube-yaml
```

```yaml
apiVersion: gloo.solo.io/v1
kind: Upstream
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"v1","kind":"Service","metadata":{"annotations":{},"labels":{"service":"petstore"},"name":"petstore","namespace":"default"},"spec":{"ports":[{"port":8080,"protocol":"TCP"}],"selector":{"app":"petstore"}}}
  creationTimestamp: null
  generation: 4
  labels:
    discovered_by: kubernetesplugin
    service: petstore
  name: default-petstore-8080
  namespace: gloo-system
  resourceVersion: "1172"
spec:
  discoveryMetadata: {}
  kube:
    selector:
      app: petstore
    serviceName: petstore
    serviceNamespace: default
    servicePort: 8080
    serviceSpec:
      rest:
        swaggerInfo:
          url: http://petstore.default.svc.cluster.local:8080/swagger.json
        transformations:
          addPet:
            body:
              text: '{"id": {{ default(id, "") }},"name": "{{ default(name, "")}}","tag":
                "{{ default(tag, "")}}"}'
            headers:
              :method:
                text: POST
              :path:
                text: /api/pets
              content-type:
                text: application/json
          deletePet:
            headers:
              :method:
                text: DELETE
              :path:
                text: /api/pets/{{ default(id, "") }}
              content-type:
                text: application/json
          findPetById:
            body: {}
            headers:
              :method:
                text: GET
              :path:
                text: /api/pets/{{ default(id, "") }}
              content-length:
                text: "0"
              content-type: {}
              transfer-encoding: {}
          findPets:
            body: {}
            headers:
              :method:
                text: GET
              :path:
                text: /api/pets?tags={{default(tags, "")}}&limit={{default(limit,
                  "")}}
              content-length:
                text: "0"
              content-type: {}
              transfer-encoding: {}
status:
  reported_by: gloo
  state: 1

```

## wait for petstore deployment to be Available<a id="sec-1-6"></a>

```shell
kubectl wait deployment --for=condition=Available --selector=app=petstore
```

    deployment.apps/petstore condition met

## Add route<a id="sec-1-7"></a>

```shell
glooctl add route \
  --path-exact /all-pets \
  --dest-name default-petstore-8080 \
  --prefix-rewrite /api/pets
```

    +-----------------|--------------|---------|------|---------|-----------------|-----------------------------------+
    | VIRTUAL SERVICE | DISPLAY NAME | DOMAINS | SSL  | STATUS  | LISTENERPLUGINS |              ROUTES               |
    +-----------------|--------------|---------|------|---------|-----------------|-----------------------------------+
    | default         |              | *       | none | Pending |                 | /all-pets ->                      |
    |                 |              |         |      |         |                 | gloo-system.default-petstore-8080 |
    |                 |              |         |      |         |                 | (upstream)                        |
    +-----------------|--------------|---------|------|---------|-----------------|-----------------------------------+

## ensure default virutalservice is Accepted<a id="sec-1-8"></a>

```shell
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
```

    Waiting for default virtual service to be Accepted...!
    +-----------------|--------------|---------|------|----------|-----------------|-----------------------------------+
    | VIRTUAL SERVICE | DISPLAY NAME | DOMAINS | SSL  |  STATUS  | LISTENERPLUGINS |              ROUTES               |
    +-----------------|--------------|---------|------|----------|-----------------|-----------------------------------+
    | default         |              | *       | none | Accepted |                 | /all-pets ->                      |
    |                 |              |         |      |          |                 | gloo-system.default-petstore-8080 |
    |                 |              |         |      |          |                 | (upstream)                        |
    +-----------------|--------------|---------|------|----------|-----------------|-----------------------------------+
    Waiting for upstream default-petstore-8080 to be Accepted...!
    +-----------------------|------------|----------|-------------------------+
    |       UPSTREAM        |    TYPE    |  STATUS  |         DETAILS         |
    +-----------------------|------------|----------|-------------------------+
    | default-petstore-8080 | Kubernetes | Accepted | svc name:      petstore |
    |                       |            |          | svc namespace: default  |
    |                       |            |          | port:          8080     |
    |                       |            |          | REST service:           |
    |                       |            |          | functions:              |
    |                       |            |          | - addPet                |
    |                       |            |          | - deletePet             |
    |                       |            |          | - findPetById           |
    |                       |            |          | - findPets              |
    |                       |            |          |                         |
    +-----------------------|------------|----------|-------------------------+

```shell
glooctl get virtualservice default --output kube-yaml
```

    apiVersion: gateway.solo.io/v1
    kind: VirtualService
    metadata:
      creationTimestamp: null
      generation: 3
      name: default
      namespace: gloo-system
      resourceVersion: "3514"
    spec:
      virtualHost:
        domains:
        - '*'
        routes:
        - matchers:
          - exact: /all-pets
          options:
            prefixRewrite: /api/pets
          routeAction:
            single:
              upstream:
                name: default-petstore-8080
                namespace: gloo-system
    status:
      reported_by: gateway
      state: 1
      subresource_statuses:
        '*v1.Proxy.gloo-system.gateway-proxy':
          reported_by: gloo
          state: 1

```shell
glooctl proxy url
```

    http://172.18.0.2:31407

## Connect to route<a id="sec-1-9"></a>

```shell
curl $(glooctl proxy url)/all-pets
```

    [{"id":1,"name":"Dog","status":"available"},{"id":2,"name":"Cat","status":"pending"}]

# SQL Research<a id="sec-2"></a>

## clients<a id="sec-2-1"></a>

```sql-mode
select useragent
  from testing.audit_event
 where useragent like 'gloo%'
 group by useragent;
```

```example
                    useragent
--------------------------------------------------
 glooctl/v0.0.0 (darwin/amd64) kubernetes/$Format
 gloo/v0.0.0 (linux/amd64) kubernetes/$Format
(2 rows)

```

## endpoints<a id="sec-2-2"></a>

```sql-mode
select endpoint
  from testing.audit_event
 where useragent like 'gloo%'
 group by endpoint;
```

```example
                  endpoint
---------------------------------------------

 listCoreV1ConfigMapForAllNamespaces
 getStorageV1APIResources
 getNodeV1beta1APIResources
 getSchedulingV1APIResources
 getCertificatesV1APIResources
 listCoreV1Namespace
 getRbacAuthorizationV1APIResources
 getNetworkingV1APIResources
 listCoreV1NamespacedSecret
 getBatchV1beta1APIResources
 readCoreV1NamespacedService
 getAuthorizationV1APIResources
 getAdmissionregistrationV1APIResources
 getCoordinationV1APIResources
 getAuthenticationV1APIResources
 listCoreV1EndpointsForAllNamespaces
 getEventsV1beta1APIResources
 getAuthenticationV1beta1APIResources
 getApiextensionsV1APIResources
 getAPIVersions
 listCoreV1SecretForAllNamespaces
 getDiscoveryV1beta1APIResources
 getAuthorizationV1beta1APIResources
 getPolicyV1beta1APIResources
 readCoreV1Node
 replaceCoreV1NamespacedConfigMap
 getCertificatesV1beta1APIResources
 getAutoscalingV2beta1APIResources
 getExtensionsV1beta1APIResources
 getRbacAuthorizationV1beta1APIResources
 getCodeVersion
 listCoreV1ServiceForAllNamespaces
 readCoreV1NamespacedConfigMap
 listCoreV1PodForAllNamespaces
 getAppsV1APIResources
 getAutoscalingV2beta2APIResources
 listAppsV1NamespacedDeployment
 getAutoscalingV1APIResources
 getApiregistrationV1APIResources
 createCoreV1Namespace
 getApiextensionsV1beta1APIResources
 getBatchV1APIResources
 createCoreV1NamespacedSecret
 getAdmissionregistrationV1beta1APIResources
 getCoreV1APIResources
 getCoreAPIVersions
 getStorageV1beta1APIResources
 getEventsV1APIResources
 getApiregistrationV1beta1APIResources
 replaceCoreV1NamespacedSecret
 getNetworkingV1beta1APIResources
 readCoreV1Namespace
 getCoordinationV1beta1APIResources
 getSchedulingV1beta1APIResources
 listCoreV1NamespacedPod
(56 rows)

```

## psql<a id="sec-2-3"></a>

```shell
psql -U apisnoop -h localhost -c "select useragent from testing.audit_event where useragent like 'gloo%' group by useragent;"
psql -U apisnoop -h localhost -c "select useragent, endpoint, tested, conf_tested
  from        testing.audit_event
         join endpoint_coverage ec using(endpoint)
 where useragent like 'gloo%'
   and ec.release = '1.20.0'
   and conf_tested = false
 group by endpoint, ec.release, tested, conf_tested, useragent
 order by conf_tested asc;"
```

                        useragent
    --------------------------------------------------
     glooctl/v0.0.0 (darwin/amd64) kubernetes/$Format
     gloo/v0.0.0 (linux/amd64) kubernetes/$Format
    (2 rows)

## untested<a id="sec-2-4"></a>

```sql-mode
select * from describe_columns('public','endpoint_coverage');
```

```example
   column    |                                 description
-------------|-----------------------------------------------------------------------------
 release     | the open api release, date of endpoint details
 endpoint    | a kubernetes endpoint, the operation_id in the spec
 level       | alpha, beta, or stable
 category    | endpoint category, roughly its group, taken from the first tag in the spec.
 path        | the http path of the endpoint
 description |
 kind        | k8s kind  for endpoint
 version     | k8s version for endpoint
 group       | k8s group for endpoint
 action      | endpoint action, roughly related to an http method
 tested      | was endpoint hit at least once by a test useragent
 conf_tested | was endpoint hit at least once by a conformance test useragent
 tests       | array of codenames of all tests that hit this endpoint
(13 rows)

```

```sql-mode
select useragent, endpoint, tested, conf_tested
  from        testing.audit_event
         join endpoint_coverage ec using(endpoint)
 where useragent like 'gloo%'
   and ec.release = '1.20.0'
   and conf_tested = false
 group by endpoint, ec.release, tested, conf_tested, useragent
 order by conf_tested asc;
```

```example
                    useragent                     |    endpoint    | tested | conf_tested
--------------------------------------------------|----------------|--------|-------------
 glooctl/v0.0.0 (darwin/amd64) kubernetes/$Format | getCodeVersion | f      | f
(1 row)

```
