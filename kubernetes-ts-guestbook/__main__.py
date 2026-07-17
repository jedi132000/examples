import json
import pulumi
import pulumi_kubernetes as k8s

# 1. Create a dedicated namespace for monitoring
monitoring_namespace = k8s.core.v1.Namespace(
    "monitoring",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="monitoring")
)

# 2. Deploy Prometheus and Grafana using the kube-prometheus-stack Helm Chart
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
                "service": {
                    "type": "LoadBalancer",
                },
                "adminPassword": "admin-secret-password",
            },
            "prometheus": {
                "prometheusSpec": {
                    "serviceMonitorSelectorNilUsesHelmValues": False,
                },
            },
        },
    )
)

# 3. GUESTBOOK APPLICATION DEPLOYMENT
app_namespace = k8s.core.v1.Namespace(
    "guestbook",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="guestbook")
)

# Redis Leader
redis_leader_deployment = k8s.apps.v1.Deployment(
    "redis-leader",
    metadata=k8s.meta.v1.ObjectMetaArgs(namespace=app_namespace.metadata.name),
    spec=k8s.apps.v1.DeploymentSpecArgs(
        selector=k8s.meta.v1.LabelSelectorArgs(match_labels={"app": "redis", "role": "leader"}),
        replicas=1,
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(labels={"app": "redis", "role": "leader"}),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[k8s.core.v1.ContainerArgs(
                    name="leader",
                    image="docker.io/redis:6.0.5",
                    ports=[k8s.core.v1.ContainerPortArgs(container_port=6379)],
                )],
            ),
        ),
    )
)

redis_leader_service = k8s.core.v1.Service(
    "redis-leader",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="redis-leader",
        namespace=app_namespace.metadata.name,
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        ports=[k8s.core.v1.ServicePortArgs(port=6379, target_port=6379)],
        selector={"app": "redis", "role": "leader"},
    )
)

# Frontend Deployment
frontend_deployment = k8s.apps.v1.Deployment(
    "frontend",
    metadata=k8s.meta.v1.ObjectMetaArgs(namespace=app_namespace.metadata.name),
    spec=k8s.apps.v1.DeploymentSpecArgs(
        selector=k8s.meta.v1.LabelSelectorArgs(match_labels={"app": "guestbook", "tier": "frontend"}),
        replicas=3,
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={"app": "guestbook", "tier": "frontend"},
                annotations={
                    "prometheus.io/scrape": "true",
                    "prometheus.io/port": "80",
                }
            ),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[k8s.core.v1.ContainerArgs(
                    name="php-redis",
                    image="docker.io/clark921/gb-frontend:v4",
                    resources=k8s.core.v1.ResourceRequirementsArgs(
                        requests={"cpu": "100m", "memory": "100Mi"},
                    ),
                    ports=[k8s.core.v1.ContainerPortArgs(container_port=80)],
                )],
            ),
        ),
    )
)

frontend_service = k8s.core.v1.Service(
    "frontend",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="frontend",
        namespace=app_namespace.metadata.name,
        labels={"app": "guestbook", "tier": "frontend"},
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        type="LoadBalancer",
        ports=[k8s.core.v1.ServicePortArgs(port=80, target_port=80)],
        selector={"app": "guestbook", "tier": "frontend"},
    )
)

# 4. SERVICE MONITOR
frontend_service_monitor = k8s.apiextensions.CustomResource(
    "frontend-servicemonitor",
    api_version="monitoring.coreos.com/v1",
    kind="ServiceMonitor",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="frontend-monitor",
        namespace=monitoring_namespace.metadata.name,
        labels={"release": "kube-prometheus-stack"},
    ),
    spec={
        "selector": {"matchLabels": {"app": "guestbook", "tier": "frontend"}},
        "namespaceSelector": {"matchNames": ["guestbook"]},
        "endpoints": [{"port": "http", "interval": "15s"}],
    },
    opts=pulumi.ResourceOptions(depends_on=[prometheus_stack])
)

# --- OUTPUTS ---
def get_grafana_url(status):
    if not status or 'load_balancer' not in status:
        return "Pending allocation... (check using kubectl)"
    ingress = status['load_balancer'].get('ingress', [])
    if not ingress:
        return "Pending allocation..."
    endpoint = ingress[0]
    if 'ip' in endpoint:
        return f"http://{endpoint['ip']}"
    elif 'hostname' in endpoint:
        return f"http://{endpoint['hostname']}"
    return "Pending IP allocation..."

grafana_service_status = prometheus_stack.get_resource(
    "v1/Service", "monitoring/kube-prometheus-stack-grafana"
).status

pulumi.export("grafana_url", grafana_service_status.apply(get_grafana_url))
pulumi.export("grafana_admin_username", "admin")
pulumi.export("grafana_admin_password", pulumi.Output.secret("admin-secret-password"))