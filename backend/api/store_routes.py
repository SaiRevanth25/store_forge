"""
Store Routes - CRUD operations for store provisioning platform.

Provides endpoints for:
- Creating stores (Medusa or WooCommerce)
- Listing stores for a user
- Getting store details and status
- Deleting stores and cleaning up resources
- Viewing store events/activity log
"""

import uuid
from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.orm import get_session, Store as StoreORM, StoreEvent as StoreEventORM
from core.utils import get_current_user
from models.users import User
from models.store import (
    StoreEngineEnum,
    StoreStatusEnum,
    StoreResponse,
    StoreListResponse,
    CreateStoreRequest,
    CreateStoreResponse,
    DeleteStoreResponse,
    StoreEventResponse,
    ErrorResponse,
)
from services.provisioning_service import ProvisioningService

router = APIRouter(prefix="/stores", tags=["stores"])


# --- Helper Functions ---

def generate_store_id() -> str:
    """Generate a unique store ID."""
    return f"store-{uuid.uuid4().hex[:12]}"


def generate_namespace(store_id: str) -> str:
    """Generate namespace name from store ID."""
    return store_id


def generate_helm_release(store_id: str) -> str:
    """Generate Helm release name from store ID."""
    return store_id


async def log_store_event(
    session: AsyncSession,
    store_id: str,
    action: str,
    message: str
) -> None:
    """Log an event for a store."""
    event = StoreEventORM(
        event_id=f"evt-{uuid.uuid4().hex[:12]}",
        store_id=store_id,
        action=action,
        message=message,
    )
    session.add(event)
    await session.commit()


# --- Routes ---

@router.get("/", response_model=StoreListResponse)
async def list_stores(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> StoreListResponse:
    """
    List all stores for the current user.
    
    Returns paginated list of stores with their status, URLs, and timestamps.
    """
    # Get total count
    count_stmt = select(func.count(StoreORM.store_id)).where(
        StoreORM.user_id == current_user.user_id
    )
    total = await session.scalar(count_stmt) or 0
    
    # Get stores
    stmt = (
        select(StoreORM)
        .where(StoreORM.user_id == current_user.user_id)
        .order_by(StoreORM.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    stores = result.scalars().all()
    
    store_responses = [
        StoreResponse(
            store_id=store.store_id,
            user_id=store.user_id,
            engine=store.engine,
            status=store.status,
            namespace=store.namespace,
            helm_release=store.helm_release,
            store_url=store.store_url,
            error_reason=store.error_reason,
            created_at=store.created_at,
            updated_at=store.updated_at,
        )
        for store in stores
    ]
    
    return StoreListResponse(stores=store_responses, total=total)


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StoreResponse:
    """
    Get details of a specific store.
    
    Returns store status, URL, timestamps, and any error information.
    """
    stmt = select(StoreORM).where(
        StoreORM.store_id == store_id,
        StoreORM.user_id == current_user.user_id,
    )
    store = await session.scalar(stmt)
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return StoreResponse(
        store_id=store.store_id,
        user_id=store.user_id,
        engine=store.engine,
        status=store.status,
        namespace=store.namespace,
        helm_release=store.helm_release,
        store_url=store.store_url,
        error_reason=store.error_reason,
        created_at=store.created_at,
        updated_at=store.updated_at,
    )


@router.post("/", response_model=CreateStoreResponse, status_code=201)
async def create_store(
    request: CreateStoreRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CreateStoreResponse:
    """
    Create a new store.
    
    Initiates provisioning of a new ecommerce store. The store will be
    created in the background and status can be monitored via GET /stores/{store_id}.
    
    - **engine**: Store engine type ('medusa' or 'woocommerce')
    - **name**: Optional name for the store (used in namespace generation)
    
    Returns immediately with store_id and PROVISIONING status.
    """
    # Check store limit (max 3 stores per user)
    count_stmt = select(func.count(StoreORM.store_id)).where(
        StoreORM.user_id == current_user.user_id
    )
    store_count = await session.scalar(count_stmt) or 0
    
    if store_count >= 3:
        raise HTTPException(
            status_code=400,
            detail="Store limit reached. Each user can create a maximum of 3 stores."
        )
    
    store_id = generate_store_id()
    namespace = generate_namespace(store_id)
    helm_release = generate_helm_release(store_id)
    
    # Create store record in database
    store = StoreORM(
        store_id=store_id,
        user_id=current_user.user_id,
        engine=request.engine.value,
        status=StoreStatusEnum.PROVISIONING.value,
        namespace=namespace,
        helm_release=helm_release,
        store_url=None,
        error_reason=None,
    )
    session.add(store)
    await session.commit()
    
    # Log creation event
    await log_store_event(
        session,
        store_id,
        "CREATE",
        f"Store creation initiated for engine: {request.engine.value}"
    )
    
    # Start provisioning in background
    background_tasks.add_task(
        provision_store_task,
        store_id=store_id,
        engine=request.engine.value,
        namespace=namespace,
        helm_release=helm_release,
        user_id=current_user.user_id,
    )
    
    return CreateStoreResponse(
        store_id=store_id,
        status=StoreStatusEnum.PROVISIONING.value,
        message=f"Store provisioning started. Monitor status via GET /stores/{store_id}",
        namespace=namespace,
    )


@router.delete("/{store_id}", response_model=DeleteStoreResponse)
async def delete_store(
    store_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DeleteStoreResponse:
    """
    Delete a store and clean up all associated resources.
    
    This will:
    - Delete the Kubernetes namespace and all resources within it
    - Remove the Helm release
    - Clean up persistent volumes
    - Remove database records
    
    The deletion happens in the background. Status can be monitored via GET /stores/{store_id}.
    """
    stmt = select(StoreORM).where(
        StoreORM.store_id == store_id,
        StoreORM.user_id == current_user.user_id,
    )
    store = await session.scalar(stmt)
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    if store.status == StoreStatusEnum.DELETING.value:
        raise HTTPException(status_code=400, detail="Store is already being deleted")
    
    # Update status to DELETING
    update_stmt = (
        update(StoreORM)
        .where(StoreORM.store_id == store_id)
        .values(status=StoreStatusEnum.DELETING.value, updated_at=datetime.utcnow())
    )
    await session.execute(update_stmt)
    await session.commit()
    
    # Log deletion event
    await log_store_event(
        session,
        store_id,
        "DELETE",
        "Store deletion initiated"
    )
    
    # Start deletion in background
    background_tasks.add_task(
        delete_store_task,
        store_id=store_id,
        namespace=store.namespace,
        helm_release=store.helm_release,
    )
    
    return DeleteStoreResponse(
        store_id=store_id,
        message="Store deletion initiated. All resources will be cleaned up.",
    )


@router.get("/{store_id}/events", response_model=List[StoreEventResponse])
async def get_store_events(
    store_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
) -> List[StoreEventResponse]:
    """
    Get event log for a specific store.
    
    Returns a list of events (create, ready, fail, delete) for the store,
    ordered by most recent first.
    """
    # Verify store belongs to user
    store_stmt = select(StoreORM).where(
        StoreORM.store_id == store_id,
        StoreORM.user_id == current_user.user_id,
    )
    store = await session.scalar(store_stmt)
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Get events
    events_stmt = (
        select(StoreEventORM)
        .where(StoreEventORM.store_id == store_id)
        .order_by(StoreEventORM.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(events_stmt)
    events = result.scalars().all()
    
    return [
        StoreEventResponse(
            event_id=event.event_id,
            store_id=event.store_id,
            action=event.action,
            message=event.message,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.post("/{store_id}/refresh-status", response_model=StoreResponse)
async def refresh_store_status(
    store_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StoreResponse:
    """
    Refresh the status of a store by checking Kubernetes resources.
    
    Useful for getting the latest status when provisioning is in progress.
    """
    stmt = select(StoreORM).where(
        StoreORM.store_id == store_id,
        StoreORM.user_id == current_user.user_id,
    )
    store = await session.scalar(stmt)
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # Only refresh if store is in PROVISIONING status
    if store.status == StoreStatusEnum.PROVISIONING.value:
        provisioning_service = ProvisioningService()
        status_info = await provisioning_service.check_deployment_status(
            namespace=store.namespace,
            helm_release=store.helm_release,
        )
        
        if status_info["ready"]:
            # Start port-forwarding for local access
            service_name = f"{store.helm_release}-medusa"
            pf_result = await provisioning_service.start_port_forward(
                store_id=store_id,
                namespace=store.namespace,
                service_name=service_name,
                target_port=9000,
            )
            
            if pf_result["success"]:
                store_url = pf_result["url"]
            else:
                store_url = status_info.get("url")
            
            # Update store to READY
            update_stmt = (
                update(StoreORM)
                .where(StoreORM.store_id == store_id)
                .values(
                    status=StoreStatusEnum.READY.value,
                    store_url=store_url,
                    updated_at=datetime.utcnow(),
                )
            )
            await session.execute(update_stmt)
            await session.commit()
            
            await log_store_event(
                session,
                store_id,
                "READY",
                f"Store is now ready. URL: {store_url}"
            )
            
            # Refresh store object
            store = await session.scalar(stmt)
    
    return StoreResponse(
        store_id=store.store_id,
        user_id=store.user_id,
        engine=store.engine,
        status=store.status,
        namespace=store.namespace,
        helm_release=store.helm_release,
        store_url=store.store_url,
        error_reason=store.error_reason,
        created_at=store.created_at,
        updated_at=store.updated_at,
    )


# --- Background Tasks ---

async def provision_store_task(
    store_id: str,
    engine: str,
    namespace: str,
    helm_release: str,
    user_id: str,
) -> None:
    """
    Background task to provision a store.
    
    This function orchestrates the Kubernetes resource creation:
    1. Create namespace
    2. Deploy Helm chart
    3. Wait for pods to be ready
    4. Update store status
    """
    from core.orm import _get_session_maker
    
    session_maker = _get_session_maker()
    async with session_maker() as session:
        try:
            provisioning_service = ProvisioningService()
            
            # Log step: Creating namespace
            await log_store_event(
                session, store_id, "PROVISION", f"Creating namespace: {namespace}"
            )
            
            # Create namespace
            ns_result = await provisioning_service.create_namespace(namespace)
            if not ns_result["success"]:
                raise Exception(f"Namespace creation failed: {ns_result.get('stderr', 'unknown error')}")
            
            # Log step: Deploying Helm chart
            await log_store_event(
                session, store_id, "PROVISION", f"Deploying Helm chart: {helm_release}"
            )
            
            # Deploy store using Helm
            deploy_result = await provisioning_service.deploy_store(
                engine=engine,
                namespace=namespace,
                helm_release=helm_release,
            )
            
            if not deploy_result["success"]:
                raise Exception(f"Helm deployment failed: {deploy_result.get('stderr', 'unknown error')}")
            
            # Log step: Waiting for deployment
            await log_store_event(
                session, store_id, "PROVISION", "Waiting for deployment to be ready..."
            )
            
            # Wait for deployment to be ready (with timeout)
            status_info = await provisioning_service.wait_for_ready(
                namespace=namespace,
                helm_release=helm_release,
                timeout_seconds=300,  # 5 minutes timeout
            )
            
            if status_info["ready"]:
                # Start port-forwarding for local access
                service_name = f"{helm_release}-medusa"
                pf_result = await provisioning_service.start_port_forward(
                    store_id=store_id,
                    namespace=namespace,
                    service_name=service_name,
                    target_port=9000,
                )
                
                if pf_result["success"]:
                    store_url = pf_result["url"]
                    await log_store_event(
                        session, store_id, "PORT_FORWARD", 
                        f"Port-forwarding started on {store_url}"
                    )
                else:
                    # Fallback to internal URL if port-forward fails
                    store_url = status_info.get("url", f"http://{helm_release}.local")
                    await log_store_event(
                        session, store_id, "WARNING", 
                        f"Port-forwarding failed: {pf_result.get('error')}. Using internal URL."
                    )
                
                # Update store status to READY
                update_stmt = (
                    update(StoreORM)
                    .where(StoreORM.store_id == store_id)
                    .values(
                        status=StoreStatusEnum.READY.value,
                        store_url=store_url,
                        updated_at=datetime.utcnow(),
                    )
                )
                await session.execute(update_stmt)
                await session.commit()
                
                await log_store_event(
                    session, store_id, "READY", f"Store is ready. URL: {store_url}"
                )
            else:
                raise Exception(status_info.get("error", "Deployment did not become ready"))
                
        except Exception as e:
            # Update store status to FAILED
            error_msg = str(e)
            update_stmt = (
                update(StoreORM)
                .where(StoreORM.store_id == store_id)
                .values(
                    status=StoreStatusEnum.FAILED.value,
                    error_reason=error_msg[:500],  # Truncate error message
                    updated_at=datetime.utcnow(),
                )
            )
            await session.execute(update_stmt)
            await session.commit()
            
            await log_store_event(
                session, store_id, "FAIL", f"Provisioning failed: {error_msg}"
            )


async def delete_store_task(
    store_id: str,
    namespace: str,
    helm_release: str,
) -> None:
    """
    Background task to delete a store and clean up resources.
    
    This function:
    1. Uninstalls the Helm release
    2. Deletes the namespace (which cleans up all resources)
    3. Removes database records
    """
    from core.orm import _get_session_maker
    
    session_maker = _get_session_maker()
    async with session_maker() as session:
        try:
            provisioning_service = ProvisioningService()
            
            # Stop port-forwarding first
            await log_store_event(
                session, store_id, "DELETE", "Stopping port-forward..."
            )
            await provisioning_service.stop_port_forward(store_id)
            
            # Log step: Uninstalling Helm release
            await log_store_event(
                session, store_id, "DELETE", f"Uninstalling Helm release: {helm_release}"
            )
            
            # Uninstall Helm release
            await provisioning_service.uninstall_helm_release(
                helm_release=helm_release,
                namespace=namespace,
            )
            
            # Log step: Deleting namespace
            await log_store_event(
                session, store_id, "DELETE", f"Deleting namespace: {namespace}"
            )
            
            # Delete namespace (this cleans up all resources)
            await provisioning_service.delete_namespace(namespace)
            
            # Log step: Cleaning up database records
            await log_store_event(
                session, store_id, "DELETE", "Cleaning up database records"
            )
            
            # Delete store events first (foreign key constraint)
            delete_events_stmt = delete(StoreEventORM).where(
                StoreEventORM.store_id == store_id
            )
            await session.execute(delete_events_stmt)
            
            # Delete store record
            delete_store_stmt = delete(StoreORM).where(
                StoreORM.store_id == store_id
            )
            await session.execute(delete_store_stmt)
            await session.commit()
            
        except Exception as e:
            # Update store status to FAILED with error
            error_msg = f"Deletion failed: {str(e)}"
            update_stmt = (
                update(StoreORM)
                .where(StoreORM.store_id == store_id)
                .values(
                    status=StoreStatusEnum.FAILED.value,
                    error_reason=error_msg[:500],
                    updated_at=datetime.utcnow(),
                )
            )
            await session.execute(update_stmt)
            await session.commit()
            
            await log_store_event(
                session, store_id, "FAIL", error_msg
            )
