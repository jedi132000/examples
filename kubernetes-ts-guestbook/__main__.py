import json
import pulumi
import pulumi_kubernetes as k8s


config = pulumi.Config()
grafana_admin_password = config.require_secret("grafanaAdminPassword")
grafana_cloud_remote_write_url = config.require("grafanaCloudRemoteWriteUrl")
grafana_cloud_metrics_username = config.require_secret("grafanaCloudMetricsUsername")
grafana_cloud_access_policy_token = config.require_secret("grafanaCloudAccessPolicyToken")
grafana_cloud_stack_url = config.require("grafanaCloudStackUrl")


# -----------------------------------------------------------------------------
# Namespaces
# -----------------------------------------------------------------------------
monitoring_namespace = k8s.core.v1.Namespace(
    "monitoring",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="monitoring"),
)


app_namespace = k8s.core.v1.Namespace(
    "guestbook",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="guestbook"),
)


# -----------------------------------------------------------------------------
# Secret for Prometheus remote_write to Grafana Cloud
# -----------------------------------------------------------------------------
grafana_cloud_remote_write_secret = k8s.core.v1.Secret(
    "grafana-cloud-remote-write",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="grafana-cloud-remote-write",
        namespace=monitoring_namespace.metadata.name,
    ),
    string_data={
        "username": grafana_cloud_metrics_username,
        "password": grafana_cloud_access_policy_token,
    },
)


# -----------------------------------------------------------------------------
# Deploy Prometheus + Grafana using kube-prometheus-stack
# -----------------------------------------------------------------------------
prometheus_stack = k8s.helm.v3.Chart(
    "kube-prometheus-stack",
    k8s.helm.v3.ChartOpts(
        chart="kube-prometheus-stack",
        version="61.3.0",
        fetch_opts=k8s.helm.v3.FetchOpts(
            repo="https://prometheus-community.github.io/helm-charts",
        ),
        namespace=monitoring_namespace.metadata.name,
        values={
            "grafana": {
                "enabled": True,
                "adminUser": "admin",
                "adminPassword": grafana_admin_password,
                "service": {
                    "type": "NodePort",
                    "port": 80,
                    "targetPort": 3000,
                    "nodePort": 30300,
                },
                "sidecar": {
                    "dashboards": {
                        "enabled": True,
                        "label": "grafana_dashboard",
                    }
                },
            },
            "prometheus": {
                "enabled": True,
                "prometheusSpec": {
                    "serviceMonitorSelectorNilUsesHelmValues": False,
                    "remoteWrite": [
                        {
                            "url": grafana_cloud_remote_write_url,
                            "basicAuth": {
                                "username": {
                                    "name": "grafana-cloud-remote-write",
                                    "key": "username",
                                },
                                "password": {
                                    "name": "grafana-cloud-remote-write",
                                    "key": "password",
                                },
                            },
                        }
                    ],
                },
            },
        },
    ),
    opts=pulumi.ResourceOptions(depends_on=[grafana_cloud_remote_write_secret]),
)


# -----------------------------------------------------------------------------
# Guestbook - Redis leader
# -----------------------------------------------------------------------------
redis_leader_deployment = k8s.apps.v1.Deployment(
    "redis-leader",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        namespace=app_namespace.metadata.name,
        labels={"app": "redis", "role": "leader"},
    ),
    spec=k8s.apps.v1.DeploymentSpecArgs(
        selector=k8s.meta.v1.LabelSelectorArgs(
            match_labels={"app": "redis", "role": "leader"}
        ),
        replicas=1,
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={"app": "redis", "role": "leader"}
            ),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[
                    k8s.core.v1.ContainerArgs(
                        name="leader",
                        image="docker.io/redis:6.0.5",
                        ports=[k8s.core.v1.ContainerPortArgs(container_port=6379)],
                        resources=k8s.core.v1.ResourceRequirementsArgs(
                            requests={"cpu": "50m", "memory": "64Mi"},
                            limits={"cpu": "250m", "memory": "128Mi"},
                        ),
                    )
                ],
            ),
        ),
    ),
)


redis_leader_service = k8s.core.v1.Service(
    "redis-leader",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="redis-leader",
        namespace=app_namespace.metadata.name,
        labels={"app": "redis", "role": "leader"},
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        ports=[k8s.core.v1.ServicePortArgs(name="redis", port=6379, target_port=6379)],
        selector={"app": "redis", "role": "leader"},
    ),
)


# -----------------------------------------------------------------------------
# Guestbook - Frontend
# -----------------------------------------------------------------------------
frontend_deployment = k8s.apps.v1.Deployment(
    "frontend",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        namespace=app_namespace.metadata.name,
        labels={"app": "guestbook", "tier": "frontend"},
    ),
    spec=k8s.apps.v1.DeploymentSpecArgs(
        selector=k8s.meta.v1.LabelSelectorArgs(
            match_labels={"app": "guestbook", "tier": "frontend"}
        ),
        replicas=3,
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={"app": "guestbook", "tier": "frontend"},
                annotations={
                    "prometheus.io/scrape": "true",
                    "prometheus.io/port": "80",
                },
            ),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[
                    k8s.core.v1.ContainerArgs(
                        name="php-redis",
                        image="us-docker.pkg.dev/google-samples/containers/gke/gb-frontend:v5",
                        ports=[k8s.core.v1.ContainerPortArgs(container_port=80)],
                        resources=k8s.core.v1.ResourceRequirementsArgs(
                            requests={"cpu": "100m", "memory": "128Mi"},
                            limits={"cpu": "500m", "memory": "256Mi"},
                        ),
                    )
                ],
            ),
        ),
    ),
)


frontend_service = k8s.core.v1.Service(
    "frontend",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="frontend",
        namespace=app_namespace.metadata.name,
        labels={"app": "guestbook", "tier": "frontend"},
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        type="NodePort",
        ports=[
            k8s.core.v1.ServicePortArgs(
                name="http",
                port=80,
                target_port=80,
                node_port=30080,
            )
        ],
        selector={"app": "guestbook", "tier": "frontend"},
    ),
)


# -----------------------------------------------------------------------------
# ServiceMonitor
# -----------------------------------------------------------------------------
frontend_service_monitor = k8s.apiextensions.CustomResource(
    "frontend-servicemonitor",
    api_version="monitoring.coreos.com/v1",
    kind="ServiceMonitor",
    metadata={
        "name": "frontend-monitor",
        "namespace": "monitoring",
        "labels": {"release": "kube-prometheus-stack"},
    },
    spec={
        "selector": {"matchLabels": {"app": "guestbook", "tier": "frontend"}},
        "namespaceSelector": {"matchNames": ["guestbook"]},
        "endpoints": [
            {
                "port": "http",
                "interval": "15s",
                "path": "/",
            }
        ],
    },
    opts=pulumi.ResourceOptions(depends_on=[prometheus_stack, frontend_service]),
)


# -----------------------------------------------------------------------------
# Grafana dashboard
# -----------------------------------------------------------------------------
dashboard = {
    "title": "Guestbook Resource Overview",
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "10s",
    "tags": ["guestbook", "kubernetes", "pulumi"],
    "panels": [
        {
            "id": 1,
            "type": "timeseries",
            "title": "Frontend Pod CPU Usage",
            "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
            "targets": [
                {
                    "refId": "A",
                    "expr": 'sum(rate(container_cpu_usage_seconds_total{namespace="guestbook", pod=~"frontend-.*", container!="POD"}[5m])) by (pod)',
                    "legendFormat": "{{pod}}",
                }
            ],
        },
        {
            "id": 2,
            "type": "timeseries",
            "title": "Frontend Pod Memory Usage",
            "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
            "targets": [
                {
                    "refId": "A",
                    "expr": 'sum(container_memory_working_set_bytes{namespace="guestbook", pod=~"frontend-.*", container!="POD"}) by (pod)',
                    "legendFormat": "{{pod}}",
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "bytes",
                },
                "overrides": [],
            },
        },
        {
            "id": 3,
            "type": "timeseries",
            "title": "Frontend Pod Restarts",
            "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
            "targets": [
                {
                    "refId": "A",
                    "expr": 'sum(kube_pod_container_status_restarts_total{namespace="guestbook", pod=~"frontend-.*"}) by (pod)',
                    "legendFormat": "{{pod}}",
                }
            ],
        },
        {
            "id": 4,
            "type": "timeseries",
            "title": "Redis Leader CPU Usage",
            "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
            "targets": [
                {
                    "refId": "A",
                    "expr": 'sum(rate(container_cpu_usage_seconds_total{namespace="guestbook", pod=~"redis-leader-.*", container!="POD"}[5m])) by (pod)',
                    "legendFormat": "{{pod}}",
                }
            ],
        },
    ],
}


grafana_dashboard_cm = k8s.core.v1.ConfigMap(
    "guestbook-grafana-dashboard",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="guestbook-dashboard",
        namespace=monitoring_namespace.metadata.name,
        labels={"grafana_dashboard": "1"},
    ),
    data={
        "guestbook-resource-overview.json": json.dumps(dashboard)
    },
    opts=pulumi.ResourceOptions(depends_on=[prometheus_stack]),
)


# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
pulumi.export("grafana_url", "http://localhost:30300")
pulumi.export("grafana_admin_username", "admin")
pulumi.export("grafana_admin_password", grafana_admin_password)
pulumi.export("guestbook_url", "http://localhost:30080")
pulumi.export("grafana_cloud_stack_url", grafana_cloud_stack_url)
pulumi.export("grafana_cloud_remote_write_url", grafana_cloud_remote_write_url)