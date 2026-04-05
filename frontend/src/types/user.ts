export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  bio?: string;
  location?: string;
  website?: string;
  avatar_url?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface BillingPlan {
  id: string;
  name: string;
  price: number;
  interval: 'month' | 'year';
  features: string[];
}

export interface BillingInfo {
  current_plan?: BillingPlan | string;
  status: 'active' | 'canceled' | 'past_due' | 'unpaid' | 'incomplete' | 'incomplete_expired' | 'trialing' | 'paused';
  next_billing_date?: string;
  card_last4?: string;
  card_brand?: string;
}


export interface ProfileFormValues {
  username: string;
  email: string;
  full_name: string;
  bio: string;
  location: string;
  website: string;
}

export interface PasswordChangeFormValues {
  current_password: string;
  password: string;
  confirm_password: string;
}
