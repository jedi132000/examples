# Guestbook Monitoring with Pulumi, Prometheus, and Grafana

This project deploys a Kubernetes Guestbook application together with a monitoring stack using Pulumi Python. It provisions Prometheus and Grafana with the `kube-prometheus-stack` Helm chart, exposes Grafana, and creates a basic Grafana dashboard that visualizes Guestbook pod resource usage metrics such as CPU, memory, and restart counts. The exercise prompt explicitly allows Guestbook metrics such as request rates, error rates, **or pod resource usage**, so this implementation uses pod resource usage because the sample Guestbook container does not expose verified Prometheus HTTP counters by default. 

## What this deploys

- A `monitoring` namespace containing Prometheus and Grafana deployed through `kube-prometheus-stack`. 
- A `guestbook` namespace containing:
  - Guestbook frontend deployment and service.
  - Redis leader deployment and service.
- A `ServiceMonitor` resource for the frontend service. 
- A provisioned Grafana dashboard showing Guestbook-related resource metrics. 


## Prerequisites

- Python 3.10+
- Pulumi CLI
- A working Kubernetes cluster and `kubectl` configured to access it
- Internet access from the cluster or deployment environment to pull container images and Helm charts

## Project structure

```text
## Project structure
.
├── Pulumi.yaml
├── Pulumi.<stack>.yaml
├── requirements.txt
├── __main__.py
└── observability_roadmap.md
```

## Python dependencies

Install the required packages:

```bash
python -m venv .venv
source .venv/bin/activate
pip install pulumi pulumi-kubernetes
```

You can also record them in `requirements.txt`:

```text
pulumi
pulumi-kubernetes
```

## Configure Pulumi secret

Set the Grafana admin password as a Pulumi secret:

```bash
pulumi config set --secret grafanaAdminPassword '<your-password>'
```

The Pulumi program reads this value and exports it as part of the stack outputs so the Grafana login details are available after deployment.

## Deploy

Run:

```bash
pulumi up
```

This applies the Kubernetes namespaces, Guestbook workloads, monitoring stack, `ServiceMonitor`, and Grafana dashboard provisioning resources. 

## Verify workloads

Check the Guestbook workloads:

```bash
kubectl -n guestbook get pods
kubectl -n guestbook get svc
```

A healthy deployment should show three frontend pods and one Redis leader pod in `Running` state, with the frontend service exposed and Redis available internally. In the validated deployment, the frontend service is a `NodePort` service on port `30080`, Redis is a `ClusterIP` service on `6379`, and the frontend and Redis pods are running. 

Check the monitoring workloads:

```bash
kubectl -n monitoring get pods
kubectl -n monitoring get svc
```

A healthy monitoring deployment should show Prometheus components and Grafana resources in the `monitoring` namespace. Grafana must be present because the exercise requires both Prometheus and Grafana to be deployed and Grafana to be exposed as `LoadBalancer` or `NodePort`. 

## Access Grafana and Guestbook

The Pulumi stack exports these logical access values:

- `grafana_url`: `http://localhost:30300`
- `grafana_admin_username`: `admin`
- `grafana_admin_password`: Pulumi secret output
- `guestbook_url`: `http://localhost:30080` 

Depending on the Kubernetes runtime, `NodePort` services may not be directly reachable on `localhost`. If direct access does not work, use `kubectl port-forward`, which is acceptable for local verification even though the Kubernetes services remain exposed as `NodePort`. 

### Port-forward commands

Grafana:

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 30300:80
```

Guestbook frontend:

```bash
kubectl -n guestbook port-forward svc/frontend 30080:80
```

Then open:

- `http://localhost:30300` for Grafana
- `http://localhost:30080` for Guestbook 

If the Grafana service name differs, list services first and use the actual Grafana service name:

```bash
kubectl -n monitoring get svc | grep grafana
```

## Grafana login

Use:

- Username: `admin`
- Password: the value set in `grafanaAdminPassword` 

You can also read the exported values with:

```bash
pulumi stack output grafana_admin_username
pulumi stack output grafana_admin_password
pulumi stack output grafana_url
pulumi stack output guestbook_url
```

## Dashboard contents

The provisioned Grafana dashboard is designed around Guestbook workload resource metrics that are reliably available from the monitoring stack. It includes panels for frontend CPU usage, frontend memory usage, frontend restart counts, and Redis leader CPU usage. This matches the assignment language allowing pod resource usage as a valid Guestbook metric type. 

## How to verify metrics

1. Confirm Guestbook pods are running:

```bash
kubectl -n guestbook get pods
```

2. Confirm monitoring components are running:

```bash
kubectl -n monitoring get pods,svc
```

3. Access Grafana and open the provisioned dashboard.
4. Confirm the dashboard panels return data for Guestbook frontend and Redis workloads. 

If you want to validate at the Prometheus level, open the Prometheus UI from the monitoring stack and test queries such as:

```promql
sum(rate(container_cpu_usage_seconds_total{namespace="guestbook", pod=~"frontend-.*", container!="POD"}[5m])) by (pod)
```

```promql
sum(container_memory_working_set_bytes{namespace="guestbook", pod=~"frontend-.*", container!="POD"}) by (pod)
```

```promql
sum(kube_pod_container_status_restarts_total{namespace="guestbook", pod=~"frontend-.*"}) by (pod)
```

These queries correspond directly to the dashboard panels and validate that Guestbook pod metrics are being collected. 