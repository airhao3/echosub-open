import { SxProps, Theme } from '@mui/material';
import { ReactNode } from 'react';

export interface Job {
  id: number | string;
  title: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  updated_at: string;
  source_language: string;
  target_languages: string[];
  error?: string;
  metadata?: Record<string, any>;
}

export interface JobStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  details?: string;
  icon?: ReactNode;
  updated_at?: string;
  error?: string;
}

export interface BillingInfo {
  current_plan: {
    id: string;
    name: string;
    amount: number;
    currency: string;
    interval: 'month' | 'year';
  };
  status: 'active' | 'canceled' | 'past_due' | 'unpaid' | 'incomplete' | 'incomplete_expired' | 'trialing' | 'all';
  current_period_end: number;
  cancel_at_period_end: boolean;
  default_payment_method: string | null;
  next_billing_date: string;
  usage: {
    current: number;
    limit: number;
  };
  payment_methods: PaymentMethod[];
  subscription_id?: string;
  customer_id?: string;
  trial_end?: number | null;
  created?: number;
}

export interface PaymentMethod {
  id: number;
  cardholder_name: string;
  card_brand: string;
  last_four_digits: string;
  exp_month: number;
  exp_year: number;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Legacy properties for backward compatibility
  brand?: string;
  last4?: string;
}

// Helper types
export type StepStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export const formatDuration = (seconds: number): string => {
  if (isNaN(seconds)) return 'Calculating...';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  const parts = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0 || hours > 0) parts.push(`${minutes}m`);
  parts.push(`${secs}s`);
  
  return parts.join(' ');
};

// Type declarations for external modules
type ComposeFunction = <R>(...args: any[]) => R;

// Global type extensions
declare global {
  interface Window {
    __REDUX_DEVTOOLS_EXTENSION_COMPOSE__?: ComposeFunction;
  }
}

// SVG type declarations have been moved to svg.d.ts
