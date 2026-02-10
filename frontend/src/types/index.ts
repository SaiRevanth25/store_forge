export interface Store {
  store_id: string;
  user_id: string;
  name?: string;
  engine: string;
  status: 'READY' | 'PROVISIONING' | 'FAILED';
  namespace: string;
  helm_release: string;
  store_url: string | null;
  error_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoreEvent {
  event_id: string;
  store_id: string;
  action: string;
  message: string;
  created_at: string;
}