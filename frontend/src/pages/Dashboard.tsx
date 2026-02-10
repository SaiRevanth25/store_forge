import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router';
import { Navbar } from '../components/Navbar';
import { StoreCard } from '../components/StoreCard';
import { CreateStoreModal } from '../components/CreateStoreModal';
import { api } from '../utils/api';
import { Store } from '../types';
import { Plus } from 'lucide-react';

export const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [error, setError] = useState('');

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!user) {
      navigate('/login');
    }
  }, [user, navigate]);

  const fetchStores = async () => {
    try {
      setError('');
      const response = await api.get('/api/stores/?skip=0&limit=50');
      setStores(response.data.stores || []);
    } catch (err: any) {
      setError('Failed to load stores. Please try again.');
      console.error('Error fetching stores:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchStores();
    }
  }, [user]);

  const handleStoreCreated = (newStore: Store) => {
    setStores((prev) => [newStore, ...prev]);
    setShowCreateModal(false);
  };

  const handleStoreDeleted = (storeId: string) => {
    setStores((prev) => prev.filter((store) => store.store_id !== storeId));
  };

  const handleStoreUpdated = (updatedStore: Store) => {
    setStores((prev) =>
      prev.map((store) =>
        store.store_id === updatedStore.store_id ? updatedStore : store
      )
    );
  };

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">My Stores</h1>
            <p className="mt-1 text-gray-600">
              Manage your e-commerce store deployments
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-blue-500 hover:bg-blue-600 text-white px-5 py-2.5 rounded-lg font-medium transition-colors shadow-sm"
          >
            <Plus className="w-5 h-5" />
            Create Store
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-3">
              <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
              <p className="text-gray-600">Loading stores...</p>
            </div>
          </div>
        ) : stores.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <div className="max-w-md mx-auto">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Plus className="w-8 h-8 text-blue-500" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                No stores yet
              </h3>
              <p className="text-gray-600 mb-6">
                Get started by creating your first store deployment
              </p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2.5 rounded-lg font-medium transition-colors"
              >
                Create Your First Store
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {stores.map((store) => (
              <StoreCard
                key={store.store_id}
                store={store}
                onDelete={handleStoreDeleted}
                onUpdate={handleStoreUpdated}
              />
            ))}
          </div>
        )}
      </div>

      {showCreateModal && (
        <CreateStoreModal
          onClose={() => setShowCreateModal(false)}
          onStoreCreated={handleStoreCreated}
        />
      )}
    </div>
  );
};
