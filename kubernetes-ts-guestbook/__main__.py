import pulumi
import pulumi_kubernetes as k8s


config = pulumi.Config()
grafana_admin_password = config.require_secret("grafanaAdminPassword")


# 1. Create a dedicated namespace for monitoring
monitoring_namespace = k8s.core.v1.Namespace(
    "monitoring",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="monitoring"),
)


# 2. Create a secret for Grafana admin credentials
grafana_admin_secret = k8s.core.v1.Secret(
    "grafana-admin-secret",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="grafana-admin-credentials",
        namespace=monitoring_namespace.metadata.name,
    ),
    string_data={
        "admin-user": "admin",
        "admin-password": grafana_admin_password,
    },
)


# 3. Deploy Prometheus and Grafana using kube-prometheus-stack
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
                    "type": "NodePort",
                    "port": 80,
                    "targetPort": 3000,
                    "nodePort": 30300,
                },
                "admin": {
                    "existingSecret": "grafana-admin-credentials",
                    "userKey": "admin-user",
                    "passwordKey": "admin-password",
                },
            },
            "prometheus": {
                "prometheusSpec": {
                    "serviceMonitorSelectorNilUsesHelmValues": False,
                },
            },
        },
    ),
    opts=pulumi.ResourceOptions(depends_on=[grafana_admin_secret]),
)


# 4. Guestbook application namespace
app_namespace = k8s.core.v1.Namespace(
    "guestbook",
    metadata=k8s.meta.v1.ObjectMetaArgs(name="guestbook"),
)


# 5. Redis leader deployment
redis_leader_deployment = k8s.apps.v1.Deployment(
    "redis-leader",
    metadata=k8s.meta.v1.ObjectMetaArgs(namespace=app_namespace.metadata.name),
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
                        ports=[
                            k8s.core.v1.ContainerPortArgs(container_port=6379)
                        ],
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
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        ports=[k8s.core.v1.ServicePortArgs(port=6379, target_port=6379)],
        selector={"app": "redis", "role": "leader"},
    ),
)


# 6. Frontend deployment
frontend_deployment = k8s.apps.v1.Deployment(
    "frontend",
    metadata=k8s.meta.v1.ObjectMetaArgs(namespace=app_namespace.metadata.name),
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
                        resources=k8s.core.v1.ResourceRequirementsArgs(
                            requests={"cpu": "100m", "memory": "100Mi"},
                        ),
                        ports=[
                            k8s.core.v1.ContainerPortArgs(container_port=80)
                        ],
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


# 7. ServiceMonitor for frontend
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
    opts=pulumi.ResourceOptions(depends_on=[prometheus_stack, frontend_service]),
)


# 8. Outputs
def build_grafana_access():
    return {
        "url": "http://localhost:30300",
        "username": "admin",
        "password": grafana_admin_password,
    }


grafana = build_grafana_access()

pulumi.export("grafana_url", grafana["url"])
pulumi.export("grafana_admin_username", grafana["username"])
pulumi.export("grafana_admin_password", grafana["password"])
pulumi.export("guestbook_url", "http://localhost:30080")