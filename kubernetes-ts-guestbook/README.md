# Kubernetes Guestbook with Prometheus & Grafana Monitoring

This repository contains a Pulumi Python program to deploy the classic **Kubernetes Guestbook Application** alongside an automated, production-grade **Prometheus and Grafana** monitoring stack using the Helm-based Prometheus Operator.

---

## Prerequisites

Before deploying, ensure you have:
* An active Kubernetes Cluster (EKS, GKE, LKE, minikube, or kind).
* [Pulumi CLI](https://www.pulumi.com/docs/get-started/install/) installed and configured.
* Python 3.9+ and `pip` installed.
* Your local `kubeconfig` actively targeted to your running cluster.

---

## Deployment Instructions

1. **Navigate** to your project directory:
   ```bash
   cd guestbook-monitoring-standard