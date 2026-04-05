import { AlertColor } from '@mui/material/Alert';

export interface Notification {
  message: string;
  severity: AlertColor;
  key: number;
}

type Listener = (notification: Notification) => void;

class NotificationService {
  private listeners: Listener[] = [];

  subscribe(listener: Listener): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  notify(notification: Omit<Notification, 'key'>): void {
    console.log('NotificationService: notify called with', notification);
    const newNotification: Notification = {
      ...notification,
      key: new Date().getTime() + Math.random(),
    };
    
    // Check if there are any listeners
    if (this.listeners.length === 0) {
      console.warn('NotificationService: No listeners registered! Notification will not be displayed.', notification);
    } else {
      console.log('NotificationService: Broadcasting to', this.listeners.length, 'listeners');
      this.listeners.forEach(listener => {
        try {
          listener(newNotification);
        } catch (error) {
          console.error('NotificationService: Error in listener', error);
        }
      });
    }
  }

  showSuccess(message: string): void {
    console.log('NotificationService: showSuccess', message);
    this.notify({ message, severity: 'success' });
  }

  showError(message: string): void {
    console.log('NotificationService: showError', message);
    this.notify({ message, severity: 'error' });
  }

  showInfo(message: string): void {
    console.log('NotificationService: showInfo', message);
    this.notify({ message, severity: 'info' });
  }

  showWarning(message: string): void {
    console.log('NotificationService: showWarning', message);
    this.notify({ message, severity: 'warning' });
  }
}

export const notificationService = new NotificationService();
