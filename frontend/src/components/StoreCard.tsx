import { useState, useEffect, useRef } from 'react';
import { Store, StoreEvent } from '../types';
import { api } from '../utils/api';
import { ExternalLink, Trash2, RefreshCw, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

interface StoreCardProps {
  store: Store;
  onDelete: (storeId: string) => void;
  onUpdate: (store: Store) => void;
}

export const StoreCard = ({ store, onDelete, onUpdate }: StoreCardProps) => {
  const [localStore, setLocalStore] = useState(store);
  const [events, setEvents] = useState<StoreEvent[]>([]);
  const [showEvents, setShowEvents] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const pollCountRef = useRef(0);

  // Polling logic for PROVISIONING stores
  useEffect(() => {
    setLocalStore(store);

    // Start polling if store is in PROVISIONING state
    if (store.status === 'PROVISIONING') {
      startPolling();
    }

    return () => {
      stopPolling();
    };
  }, [store.store_id]);

  const startPolling = () => {
    pollCountRef.current = 0;
    
    // Poll immediately
    pollStoreStatus();

    // Then poll every 5 seconds, max 6 times (30 seconds total)
    pollIntervalRef.current = setInterval(() => {
      pollCountRef.current += 1;
      
      if (pollCountRef.current >= 6) {
        stopPolling();
        return;
      }

      pollStoreStatus();
    }, 5000);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const pollStoreStatus = async () => {
    try {
      const response = await api.post(`/api/stores/${localStore.store_id}/refresh-status`);
      const updatedStore = response.data;
      
      setLocalStore(updatedStore);
      onUpdate(updatedStore);

      // Stop polling if status changed to READY or FAILED
      if (updatedStore.status === 'READY' || updatedStore.status === 'FAILED') {
        stopPolling();

        // If READY, fetch events to get store URL
        if (updatedStore.status === 'READY') {
          fetchEvents();
        }
      }
    } catch (error) {
      console.error('Error polling store status:', error);
    }
  };

  const fetchEvents = async () => {
    try {
      const response = await api.get(`/api/stores/${localStore.store_id}/events?limit=50`);
      setEvents(response.data || []);
    } catch (error) {
      console.error('Error fetching events:', error);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/api/stores/${localStore.store_id}`);
      onDelete(localStore.store_id);
    } catch (error) {
      console.error('Error deleting store:', error);
      alert('Failed to delete store');
    } finally {
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const getStatusBadge = () => {
    switch (localStore.status) {
      case 'READY':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
            <CheckCircle className="w-4 h-4" />
            Ready
          </span>
        );
      case 'PROVISIONING':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
            <Loader2 className="w-4 h-4 animate-spin" />
            Provisioning
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">
            <AlertCircle className="w-4 h-4" />
            Failed
          </span>
        );
    }
  };

  // Find READY event for store URL
  const readyEvent = events.find((e) => e.action === 'READY');
  const storeUrl = localStore.store_url || readyEvent?.message.match(/URL: (.+)$/)?.[1];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-xl font-semibold text-gray-900 mb-1">
            {localStore.name || localStore.store_id}
          </h3>
          {getStatusBadge()}
        </div>
      </div>

      <div className="space-y-2 mb-4 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-600">Store ID:</span>
          <span className="font-medium text-gray-900">{localStore.store_id}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Engine:</span>
          <span className="font-medium text-gray-900">{localStore.engine}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Created:</span>
          <span className="font-medium text-gray-900">
            {new Date(localStore.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Provisioning message */}
      {localStore.status === 'PROVISIONING' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
          <p className="text-sm text-blue-700">
            Provisioning store... this may take 10–30 seconds
          </p>
        </div>
      )}

      {/* Store URL when READY */}
      {localStore.status === 'READY' && storeUrl && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
          <p className="text-sm text-green-700 font-medium mb-1">
            Store is live!
          </p>
          <a
            href={`${storeUrl}/app`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1 break-all"
          >
            {storeUrl}
            <ExternalLink className="w-3 h-3 flex-shrink-0" />
          </a>
        </div>
      )}

      {/* Error reason when FAILED */}
      {localStore.status === 'FAILED' && localStore.error_reason && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
          <p className="text-sm text-red-700">
            <span className="font-medium">Error:</span> {localStore.error_reason}
          </p>
        </div>
      )}

      {/* Events toggle */}
      {events.length > 0 && (
        <button
          onClick={() => setShowEvents(!showEvents)}
          className="text-sm text-blue-500 hover:text-blue-600 mb-3"
        >
          {showEvents ? 'Hide' : 'Show'} Events ({events.length})
        </button>
      )}

      {/* Events list */}
      {showEvents && events.length > 0 && (
        <div className="mb-4 space-y-2 max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-3 bg-gray-50">
          {events.map((event) => (
            <div key={event.event_id} className="text-xs">
              <div className="flex items-start gap-2">
                <span className="font-medium text-blue-600 whitespace-nowrap">
                  {event.action}
                </span>
                <span className="text-gray-700">{event.message}</span>
              </div>
              <div className="text-gray-500 text-xs mt-0.5">
                {new Date(event.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={fetchEvents}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
        <button
          onClick={() => setShowDeleteConfirm(true)}
          disabled={deleting}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors text-sm font-medium disabled:bg-red-300"
        >
          <Trash2 className="w-4 h-4" />
          Delete
        </button>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-2">Delete Store?</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete <strong>{localStore.store_id}</strong>? This action
              cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors font-medium disabled:bg-red-300"
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};