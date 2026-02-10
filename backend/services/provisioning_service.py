"""
Provisioning Service - Kubernetes and Helm operations for store management.

Handles:
- Namespace creation/deletion
- Helm chart deployment
- Deployment status monitoring
- Resource cleanup
- Port-forwarding for local access
"""

import asyncio
import subprocess
import json
import logging
import os
import socket
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Get the project root directory (parent of backend/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Global registry of port-forward processes: {store_id: {"process": Process, "port": int}}
_port_forward_registry: Dict[str, Dict[str, Any]] = {}

# Port range for store port-forwarding (9001-9100)
PORT_RANGE_START = 9001
PORT_RANGE_END = 9100


def _get_available_port() -> int:
    """Find an available port in the designated range."""
    used_ports = {info["port"] for info in _port_forward_registry.values()}
    
    for port in range(PORT_RANGE_START, PORT_RANGE_END):
        if port in used_ports:
            continue
        # Check if port is actually available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    
    raise RuntimeError(f"No available ports in range {PORT_RANGE_START}-{PORT_RANGE_END}")


class ProvisioningService:
    """
    Service for managing store provisioning on Kubernetes.
    
    Uses kubectl and helm CLI commands to interact with the cluster.
    This approach ensures compatibility with any Kubernetes cluster
    (Kind, k3s, minikube, etc.).
    """
    
    # Path to Helm charts directory (absolute path from project root)
    CHARTS_DIR = str(PROJECT_ROOT / "charts")
    
    # Default values files
    VALUES_LOCAL = "values.yaml"
    VALUES_PROD = "values-prod.yaml"
    
    def __init__(self, environment: str = "local"):
        """
        Initialize provisioning service.
        
        Args:
            environment: 'local' or 'production' - determines which values file to use
        """
        self.environment = environment
        self.values_file = self.VALUES_PROD if environment == "production" else self.VALUES_LOCAL
    
    async def _run_command(
        self,
        cmd: list[str],
        timeout: int = 60,
        check: bool = True,
    ) -> Dict[str, Any]:
        """
        Run a shell command asynchronously.
        
        Uses subprocess.run in a thread pool for reliable cross-platform
        behavior (avoids Windows asyncio subprocess issues under uvicorn).
        
        Args:
            cmd: Command and arguments as list
            timeout: Timeout in seconds
            check: Raise exception on non-zero exit code
            
        Returns:
            Dict with 'success', 'stdout', 'stderr', 'returncode'
        """
        def _run_sync() -> Dict[str, Any]:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return {
                    "success": proc.returncode == 0,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                    "returncode": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout}s",
                    "returncode": -1,
                }
            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                    "returncode": -1,
                }

        result = await asyncio.to_thread(_run_sync)

        if check and result["returncode"] != 0:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"stderr: {result['stderr']}")

        return result
    
    async def create_namespace(self, namespace: str) -> Dict[str, Any]:
        """
        Create a Kubernetes namespace for a store.
        
        Also applies resource quotas and limit ranges for isolation.
        
        Args:
            namespace: Name of the namespace to create
            
        Returns:
            Dict with operation result
        """
        # Check if namespace already exists (idempotency)
        check_result = await self._run_command(
            ["kubectl", "get", "namespace", namespace, "-o", "json"],
            check=False
        )
        
        if check_result["success"]:
            logger.info(f"Namespace {namespace} already exists")
            return {"success": True, "message": "Namespace already exists"}
        
        # Create namespace
        result = await self._run_command(
            ["kubectl", "create", "namespace", namespace]
        )
        
        if result["success"]:
            logger.info(f"Created namespace: {namespace}")
            
            # Apply resource quota for isolation
            await self._apply_resource_quota(namespace)
            
            # Apply limit range for default resource limits
            await self._apply_limit_range(namespace)
        
        return result
    
    async def _apply_resource_quota(self, namespace: str) -> Dict[str, Any]:
        """Apply resource quota to namespace for isolation."""
        quota_manifest = f"""
apiVersion: v1
kind: ResourceQuota
metadata:
  name: store-quota
  namespace: {namespace}
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 2Gi
    limits.cpu: "4"
    limits.memory: 4Gi
    persistentvolumeclaims: "5"
    pods: "20"
    services: "10"
"""
        return await self._apply_manifest(quota_manifest, namespace)
    
    async def _apply_limit_range(self, namespace: str) -> Dict[str, Any]:
        """Apply limit range to namespace for default container limits."""
        limit_manifest = f"""
apiVersion: v1
kind: LimitRange
metadata:
  name: store-limits
  namespace: {namespace}
spec:
  limits:
  - default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "100m"
      memory: "256Mi"
    type: Container
"""
        return await self._apply_manifest(limit_manifest, namespace)
    
    async def _apply_manifest(self, manifest: str, namespace: str) -> Dict[str, Any]:
        """Apply a YAML manifest using kubectl."""
        def _run_sync() -> Dict[str, Any]:
            try:
                proc = subprocess.run(
                    ["kubectl", "apply", "-f", "-", "-n", namespace],
                    input=manifest,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return {
                    "success": proc.returncode == 0,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                }
            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                }

        return await asyncio.to_thread(_run_sync)
    
    async def deploy_store(
        self,
        engine: str,
        namespace: str,
        helm_release: str,
        custom_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Deploy a store using Helm.
        
        Args:
            engine: Store engine type ('medusa' or 'woocommerce')
            namespace: Kubernetes namespace
            helm_release: Helm release name
            custom_values: Optional custom Helm values
            
        Returns:
            Dict with operation result
        """
        chart_path = f"{self.CHARTS_DIR}/{engine}"
        values_path = f"{chart_path}/{self.values_file}"
        
        # Build Helm install command
        cmd = [
            "helm", "upgrade", "--install",
            helm_release,
            chart_path,
            "-n", namespace,
            "-f", values_path,
            "--wait",
            "--timeout", "5m",
        ]
        
        # Add custom values if provided
        if custom_values:
            for key, value in custom_values.items():
                cmd.extend(["--set", f"{key}={value}"])
        
        logger.info(f"Deploying {engine} store with Helm: {helm_release}")
        result = await self._run_command(cmd, timeout=360)  # 6 minute timeout
        
        if result["success"]:
            logger.info(f"Successfully deployed {helm_release}")
        else:
            logger.error(f"Failed to deploy {helm_release}: {result['stderr']}")
        
        return result
    
    async def check_deployment_status(
        self,
        namespace: str,
        helm_release: str,
    ) -> Dict[str, Any]:
        """
        Check the status of a store deployment.
        
        Args:
            namespace: Kubernetes namespace
            helm_release: Helm release name
            
        Returns:
            Dict with 'ready', 'url', 'pods', 'error'
        """
        # Check Helm release status
        helm_result = await self._run_command(
            ["helm", "status", helm_release, "-n", namespace, "-o", "json"],
            check=False
        )
        
        if not helm_result["success"]:
            return {
                "ready": False,
                "error": f"Helm release not found: {helm_result['stderr']}",
            }
        
        # Check pod status
        pods_result = await self._run_command(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            check=False
        )
        
        if not pods_result["success"]:
            return {
                "ready": False,
                "error": f"Failed to get pods: {pods_result['stderr']}",
            }
        
        try:
            pods_data = json.loads(pods_result["stdout"])
            pods = pods_data.get("items", [])
            
            all_ready = True
            pod_statuses = []
            
            for pod in pods:
                pod_name = pod["metadata"]["name"]
                phase = pod["status"]["phase"]
                
                # Check container statuses
                container_statuses = pod["status"].get("containerStatuses", [])
                containers_ready = all(
                    cs.get("ready", False) for cs in container_statuses
                )
                
                pod_ready = phase == "Running" and containers_ready
                all_ready = all_ready and pod_ready
                
                pod_statuses.append({
                    "name": pod_name,
                    "phase": phase,
                    "ready": pod_ready,
                })
            
            # Get service URL
            url = await self._get_store_url(namespace, helm_release)
            
            return {
                "ready": all_ready and len(pods) > 0,
                "url": url,
                "pods": pod_statuses,
            }
            
        except json.JSONDecodeError as e:
            return {
                "ready": False,
                "error": f"Failed to parse pod status: {str(e)}",
            }
    
    async def _get_store_url(self, namespace: str, helm_release: str) -> Optional[str]:
        """Get the URL for accessing the store."""
        # Try to get service info
        svc_result = await self._run_command(
            ["kubectl", "get", "svc", "-n", namespace, "-o", "json"],
            check=False
        )
        
        if not svc_result["success"]:
            return None
        
        try:
            services = json.loads(svc_result["stdout"])
            for svc in services.get("items", []):
                svc_name = svc["metadata"]["name"]
                svc_type = svc["spec"]["type"]
                
                if svc_type == "LoadBalancer":
                    ingress = svc["status"].get("loadBalancer", {}).get("ingress", [])
                    if ingress:
                        ip = ingress[0].get("ip") or ingress[0].get("hostname")
                        port = svc["spec"]["ports"][0]["port"]
                        return f"http://{ip}:{port}"
                
                elif svc_type == "NodePort":
                    node_port = svc["spec"]["ports"][0].get("nodePort")
                    if node_port:
                        return f"http://localhost:{node_port}"
                
                elif svc_type == "ClusterIP":
                    # For local development, return port-forward instructions
                    port = svc["spec"]["ports"][0]["port"]
                    return f"http://{svc_name}.{namespace}.svc.cluster.local:{port}"
            
            return f"http://{helm_release}.local"
            
        except (json.JSONDecodeError, KeyError):
            return f"http://{helm_release}.local"
    
    async def wait_for_ready(
        self,
        namespace: str,
        helm_release: str,
        timeout_seconds: int = 300,
        poll_interval: int = 10,
    ) -> Dict[str, Any]:
        """
        Wait for a deployment to become ready.
        
        Args:
            namespace: Kubernetes namespace
            helm_release: Helm release name
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between status checks
            
        Returns:
            Dict with 'ready', 'url', 'error'
        """
        start_time = datetime.utcnow()
        
        while True:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                return {
                    "ready": False,
                    "error": f"Timeout waiting for deployment after {timeout_seconds}s",
                }
            
            status = await self.check_deployment_status(namespace, helm_release)
            
            if status.get("ready"):
                return status
            
            logger.info(f"Waiting for {helm_release} to be ready... ({int(elapsed)}s)")
            await asyncio.sleep(poll_interval)
    
    async def uninstall_helm_release(
        self,
        helm_release: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """
        Uninstall a Helm release.
        
        Args:
            helm_release: Helm release name
            namespace: Kubernetes namespace
            
        Returns:
            Dict with operation result
        """
        # Check if release exists first
        check_result = await self._run_command(
            ["helm", "status", helm_release, "-n", namespace],
            check=False
        )
        
        if not check_result["success"]:
            logger.info(f"Helm release {helm_release} not found, skipping uninstall")
            return {"success": True, "message": "Release not found"}
        
        result = await self._run_command(
            ["helm", "uninstall", helm_release, "-n", namespace, "--wait"],
            timeout=120
        )
        
        if result["success"]:
            logger.info(f"Uninstalled Helm release: {helm_release}")
        else:
            logger.error(f"Failed to uninstall {helm_release}: {result['stderr']}")
        
        return result
    
    async def delete_namespace(self, namespace: str) -> Dict[str, Any]:
        """
        Delete a Kubernetes namespace and all its resources.
        
        Args:
            namespace: Name of the namespace to delete
            
        Returns:
            Dict with operation result
        """
        # Check if namespace exists
        check_result = await self._run_command(
            ["kubectl", "get", "namespace", namespace],
            check=False
        )
        
        if not check_result["success"]:
            logger.info(f"Namespace {namespace} not found, skipping deletion")
            return {"success": True, "message": "Namespace not found"}
        
        # Delete namespace (this removes all resources within it)
        result = await self._run_command(
            ["kubectl", "delete", "namespace", namespace, "--wait=true"],
            timeout=120
        )
        
        if result["success"]:
            logger.info(f"Deleted namespace: {namespace}")
        else:
            logger.error(f"Failed to delete namespace {namespace}: {result['stderr']}")
        
        return result
    
    async def get_pod_logs(
        self,
        namespace: str,
        pod_name: Optional[str] = None,
        tail_lines: int = 100,
    ) -> Dict[str, Any]:
        """
        Get logs from pods in a namespace.
        
        Args:
            namespace: Kubernetes namespace
            pod_name: Specific pod name (if None, gets logs from all pods)
            tail_lines: Number of lines to retrieve
            
        Returns:
            Dict with pod logs
        """
        if pod_name:
            result = await self._run_command(
                ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail_lines}"],
                check=False
            )
            return {pod_name: result["stdout"] if result["success"] else result["stderr"]}
        
        # Get all pods in namespace
        pods_result = await self._run_command(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "jsonpath={.items[*].metadata.name}"],
            check=False
        )
        
        if not pods_result["success"]:
            return {"error": pods_result["stderr"]}
        
        pod_names = pods_result["stdout"].split()
        logs = {}
        
        for name in pod_names:
            log_result = await self._run_command(
                ["kubectl", "logs", name, "-n", namespace, f"--tail={tail_lines}"],
                check=False
            )
            logs[name] = log_result["stdout"] if log_result["success"] else log_result["stderr"]
        
        return logs
    
    async def get_helm_releases(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        List Helm releases.
        
        Args:
            namespace: Filter by namespace (if None, lists all namespaces)
            
        Returns:
            Dict with release information
        """
        cmd = ["helm", "list", "-o", "json"]
        if namespace:
            cmd.extend(["-n", namespace])
        else:
            cmd.append("-A")
        
        result = await self._run_command(cmd, check=False)
        
        if result["success"]:
            try:
                releases = json.loads(result["stdout"])
                return {"success": True, "releases": releases}
            except json.JSONDecodeError:
                return {"success": False, "error": "Failed to parse helm output"}
        
        return {"success": False, "error": result["stderr"]}
    
    async def rollback_helm_release(
        self,
        helm_release: str,
        namespace: str,
        revision: int = 0,  # 0 means previous revision
    ) -> Dict[str, Any]:
        """
        Rollback a Helm release to a previous revision.
        
        Args:
            helm_release: Helm release name
            namespace: Kubernetes namespace
            revision: Revision number (0 for previous)
            
        Returns:
            Dict with operation result
        """
        cmd = ["helm", "rollback", helm_release, "-n", namespace, "--wait"]
        if revision > 0:
            cmd.append(str(revision))
        
        result = await self._run_command(cmd, timeout=180)
        
        if result["success"]:
            logger.info(f"Rolled back {helm_release} to revision {revision or 'previous'}")
        else:
            logger.error(f"Failed to rollback {helm_release}: {result['stderr']}")
        
        return result

    async def get_services(self, namespace: str) -> Dict[str, Any]:
        """
        Get list of services in a namespace.
        
        Args:
            namespace: Kubernetes namespace
            
        Returns:
            Dict with list of service names or error
        """
        result = await self._run_command(
            ["kubectl", "get", "svc", "-n", namespace, "-o", "json"],
            check=False
        )
        
        if not result["success"]:
            return {"services": [], "error": result.get("stderr")}
        
        try:
            data = json.loads(result["stdout"])
            services = [item["metadata"]["name"] for item in data.get("items", [])]
            return {"services": services}
        except (json.JSONDecodeError, KeyError) as e:
            return {"services": [], "error": str(e)}
    
    async def start_port_forward(
        self,
        store_id: str,
        namespace: str,
        service_name: str,
        target_port: int = 9000,
    ) -> Dict[str, Any]:
        """
        Start port-forwarding for a store service.
        
        Args:
            store_id: Unique store identifier
            namespace: Kubernetes namespace
            service_name: Name of the service to forward
            target_port: Port on the service (default: 9000)
            
        Returns:
            Dict with 'success', 'port', 'url'
        """
        global _port_forward_registry
        
        # Check if already forwarding
        if store_id in _port_forward_registry:
            existing = _port_forward_registry[store_id]
            port = existing["port"]
            return {
                "success": True,
                "port": port,
                "url": f"http://localhost:{port}",
                "message": "Port-forward already running"
            }
        
        try:
            local_port = _get_available_port()
        except RuntimeError as e:
            return {"success": False, "error": str(e)}
        
        # Verify service exists before starting port-forward (with retries)
        max_retries = 5
        for attempt in range(max_retries):
            svc_check = await self._run_command(
                ["kubectl", "get", "svc", service_name, "-n", namespace, "-o", "json"],
                check=False
            )
            
            if not svc_check["success"]:
                if attempt < max_retries - 1:
                    logger.warning(f"Service {service_name} not found yet (attempt {attempt + 1}/{max_retries}), waiting...")
                    await asyncio.sleep(2)
                else:
                    # Get available services for debugging
                    services_info = await self.get_services(namespace)
                    available_services = ", ".join(services_info.get("services", []))
                    error_msg = f"Service {service_name} not found after {max_retries} attempts. Available services: {available_services}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }
                continue
            
            # Service exists, check if it has endpoints
            try:
                svc_data = json.loads(svc_check["stdout"])
                # Service found, log it and exit loop
                logger.info(f"Service {service_name} found in namespace {namespace}")
                break
            except json.JSONDecodeError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return {
                        "success": False,
                        "error": f"Failed to parse service information for {service_name}"
                    }
        
        # Start port-forward as a background process
        cmd = [
            "kubectl", "port-forward",
            f"svc/{service_name}",
            f"{local_port}:{target_port}",
            "-n", namespace
        ]
        
        try:
            # Start the process without waiting
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            
            # Give it more time to establish the connection
            await asyncio.sleep(2)
            
            # Check if process is still running
            if process.poll() is not None:
                stderr = process.stderr.strip() if process.stderr else ""
                # Try to read stderr if available
                try:
                    if process.stderr:
                        stderr = process.stderr.read()
                except:
                    pass
                logger.error(f"Port-forward process exited for {store_id}: {stderr}")
                return {
                    "success": False,
                    "error": f"Port-forward failed to start: {stderr}"
                }
            
            # Register the port-forward
            _port_forward_registry[store_id] = {
                "process": process,
                "port": local_port,
                "namespace": namespace,
                "service": service_name,
            }
            
            logger.info(f"Started port-forward for {store_id}: localhost:{local_port} -> {service_name}:{target_port}")
            
            return {
                "success": True,
                "port": local_port,
                "url": f"http://localhost:{local_port}",
            }
            
        except Exception as e:
            logger.error(f"Failed to start port-forward for {store_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def stop_port_forward(self, store_id: str) -> Dict[str, Any]:
        """
        Stop port-forwarding for a store.
        
        Args:
            store_id: Unique store identifier
            
        Returns:
            Dict with operation result
        """
        global _port_forward_registry
        
        if store_id not in _port_forward_registry:
            return {"success": True, "message": "No port-forward running"}
        
        try:
            info = _port_forward_registry[store_id]
            process = info["process"]
            
            # Terminate the process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            del _port_forward_registry[store_id]
            
            logger.info(f"Stopped port-forward for {store_id}")
            return {"success": True, "message": "Port-forward stopped"}
            
        except Exception as e:
            logger.error(f"Error stopping port-forward for {store_id}: {e}")
            # Clean up registry anyway
            if store_id in _port_forward_registry:
                del _port_forward_registry[store_id]
            return {"success": False, "error": str(e)}
    
    def get_port_forward_info(self, store_id: str) -> Optional[Dict[str, Any]]:
        """
        Get port-forward information for a store.
        
        Args:
            store_id: Unique store identifier
            
        Returns:
            Dict with port-forward info or None if not running
        """
        if store_id not in _port_forward_registry:
            return None
        
        info = _port_forward_registry[store_id]
        process = info["process"]
        
        # Check if process is still running
        if process.poll() is not None:
            # Process has died, clean up
            del _port_forward_registry[store_id]
            return None
        
        return {
            "port": info["port"],
            "url": f"http://localhost:{info['port']}",
            "namespace": info["namespace"],
            "service": info["service"],
        }