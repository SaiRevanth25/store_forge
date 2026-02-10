import { useState } from 'react';
import { X } from 'lucide-react';
import { api } from '../utils/api';
import { Store } from '../types';

interface CreateStoreModalProps {
  onClose: () => void;
  onStoreCreated: (store: Store) => void;
}

export const CreateStoreModal = ({ onClose, onStoreCreated }: CreateStoreModalProps) => {
  const [name, setName] = useState('');
  const [engine, setEngine] = useState('medusa');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.post('/api/stores/', { name, engine });
      
      // Create a store object with PROVISIONING status
      const newStore: Store = {
        store_id: response.data.store_id,
        user_id: '', // Will be populated by backend
        name: name,
        engine,
        status: 'PROVISIONING',
        namespace: response.data.namespace,
        helm_release: response.data.store_id,
        store_url: null,
        error_reason: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      onStoreCreated(newStore);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create store. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900">Create New Store</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="storeName" className="block text-sm font-medium text-gray-700 mb-2">
              Store Name
            </label>
            <input
              id="storeName"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
              placeholder="My Store"
            />
          </div>

          <div>
            <label htmlFor="engine" className="block text-sm font-medium text-gray-700 mb-2">
              Engine
            </label>
            <select
              id="engine"
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
            >
              <option value="medusa">Medusa</option>
            </select>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-blue-500 hover:bg-blue-600 text-white py-2.5 rounded-lg font-medium transition-colors disabled:bg-blue-300 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create Store'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};