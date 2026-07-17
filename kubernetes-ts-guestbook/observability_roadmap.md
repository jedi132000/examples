# Observability Roadmap

This document outlines how the current Guestbook monitoring implementation could evolve beyond the coding exercise into a more complete observability and incident-response platform. The exercise itself focuses on deploying Prometheus and Grafana with Pulumi, enabling Guestbook monitoring, exposing Grafana, and optionally building a basic dashboard. This roadmap shows what the next 90 days could look like if the same foundation were extended in a production setting. 

## Intent

The current implementation intentionally focuses on what can be delivered accurately within the scope of the exercise: Prometheus and Grafana deployed with Pulumi, Guestbook workload monitoring, Grafana exposure, and a basic dashboard centered on pod resource usage. The assignment explicitly allows simple metrics such as request counts or resource usage, so starting with Guestbook CPU, memory, and restart signals is a practical and defensible baseline. 

The goal of this roadmap is not to suggest that a short take-home should include a full platform rollout. Instead, it shows how this initial deployment could mature into a more complete observability stack with richer telemetry, better incident handling, and a clearer path toward AIOps-style automation. 

## Days 0-30

### Stabilize the baseline

- Validate that Prometheus is scraping the intended Guestbook targets and that Grafana dashboards are showing stable resource metrics for the frontend and Redis workloads. 
- Review dashboard usefulness and remove anything speculative or noisy so the platform starts from trusted signals only. 
- Keep observability assets versioned alongside infrastructure so service monitors, dashboards, and future alerting rules evolve through the same review process as the rest of the stack. 

### Establish ownership

- Document what each metric means, who owns the workload, and how to validate a signal before it turns into an alert. 
- Add short runbooks for common issues such as pod restarts, elevated CPU, or memory pressure in the Guestbook namespace. 
- Define the minimum operating model for the environment: what gets monitored, who responds, and which failures are important enough to escalate. 

## Days 31-60

### Expand telemetry with Grafana Alloy

Grafana Alloy would be the next logical addition because it provides a more flexible telemetry collection and routing layer than a metrics-only stack. Adding Alloy would make it possible to collect, enrich, and route metrics, logs, traces, and profiles through a more unified pipeline as the environment grows. 

A practical next step would be to use Alloy as the central collection path for workloads beyond the initial Guestbook example. That would make the platform easier to standardize and would create a cleaner foundation for alerting, troubleshooting, and future automation. 

### Add frontend visibility with Faro/RUM

Once backend and infrastructure telemetry are stable, the next gap to close is user experience. Grafana Faro provides real user monitoring for browser applications, including frontend performance, JavaScript errors, and user-side interaction signals, which would let the team see whether backend health issues are actually visible to end users. 

For a Guestbook-style application, this could mean instrumenting the frontend so browser-side failures and latency can be correlated with Kubernetes workload behavior. That would move the monitoring story from “the pods look healthy” to “the user experience is healthy,” which is a much stronger operational signal. 

## Days 61-90

### Improve response with Grafana IRM

Once reliable telemetry exists, the next maturity step is improving how the team responds to incidents. Grafana IRM is designed for on-call management, alert routing, and coordinated incident response, making it a good fit for moving from dashboards into actual operational workflows. 

In practice, that would mean connecting high-value alerts to clear ownership, escalation paths, and incident status handling. Instead of treating observability as a passive dashboarding exercise, the team would have a direct path from signal detection to coordinated response. 

### Introduce AIOps carefully

AIOps should be introduced only after the team trusts the signals and response process. With richer telemetry from Alloy and Faro, the platform would be in a much better position to experiment with anomaly detection, alert correlation, or noise reduction on a small number of high-value signals instead of applying AI indiscriminately. 

A sensible pilot would focus on a few cases such as unusual restart patterns, abnormal frontend latency, or sudden CPU shifts. The aim would be to reduce alert fatigue and improve incident prioritization, not to replace engineering judgment. 

## Target state

At the end of this roadmap, the platform would move beyond a basic exercise implementation into a more complete operating model. Prometheus and Grafana would still provide the foundation requested in the assignment, but Alloy would unify telemetry collection, Faro would add real user visibility, and IRM would connect alerts to structured incident response. 

That evolution would preserve the strengths of the current implementation: practical scope, observability as code, and a bias toward accurate signals over speculative metrics. It would also show a clear path toward a more mature SRE and AIOps posture without overcomplicating the original assignment. 