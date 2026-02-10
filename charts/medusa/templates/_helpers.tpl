{{/*
Expand the name of the chart.
*/}}
{{- define "medusa.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Create a default fully qualified app name.
*/}}
{{- define "medusa.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}


{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "medusa.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}


{{/*
Selector labels (MUST be stable & release-specific)
Used by:
- Deployment.spec.selector.matchLabels
- Pod template labels
- Service selectors
*/}}
{{- define "medusa.selectorLabels" -}}
app.kubernetes.io/name: {{ include "medusa.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}


{{/*
Common labels (safe to add/remove, NOT used for selectors)
*/}}
{{- define "medusa.labels" -}}
helm.sh/chart: {{ include "medusa.chart" . }}
{{ include "medusa.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app: medusa
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end }}


{{/*
Database URL
Used only when creating Kubernetes Secret via Helm.
For production SaaS, prefer external secret managers.
*/}}
{{- define "medusa.databaseUrl" -}}
postgres://{{ .Values.database.user }}:{{ .Values.database.password }}@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.name }}?sslmode={{ .Values.database.sslmode }}
{{- end }}
