// Service Worker for BharatMail Push Notifications
const CACHE_NAME = 'bharatmail-v1';
const urlsToCache = [
  '/',
  '/static/logo.png',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css'
];

// Install event - cache resources
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});

// Fetch event - serve cached content when offline
self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      }
    )
  );
});

// Push event - handle incoming push notifications
self.addEventListener('push', function(event) {
  console.log('Push message received:', event);
  
  let notificationData = {};
  
  if (event.data) {
    try {
      notificationData = event.data.json();
    } catch (e) {
      notificationData = {
        title: 'New Email',
        body: event.data.text(),
        icon: '/static/logo.png',
        badge: '/static/logo.png'
      };
    }
  } else {
    notificationData = {
      title: 'New Email',
      body: 'You have received a new email',
      icon: '/static/logo.png',
      badge: '/static/logo.png'
    };
  }

  const notificationOptions = {
    body: notificationData.body,
    icon: notificationData.icon || '/static/logo.png',
    badge: notificationData.badge || '/static/logo.png',
    vibrate: [100, 50, 100],
    data: {
      url: notificationData.url || '/inbox',
      mailId: notificationData.mailId || null
    },
    actions: [
      {
        action: 'open',
        title: 'Open Email',
        icon: '/static/logo.png'
      },
      {
        action: 'dismiss',
        title: 'Dismiss',
        icon: '/static/logo.png'
      }
    ],
    requireInteraction: true,
    tag: 'bharatmail-notification'
  };

  event.waitUntil(
    self.registration.showNotification(notificationData.title, notificationOptions)
  );
});

// Notification click event
self.addEventListener('notificationclick', function(event) {
  console.log('Notification click received:', event);
  
  event.notification.close();

  if (event.action === 'dismiss') {
    return;
  }

  // Default action or 'open' action
  let urlToOpen = event.notification.data?.url || '/inbox';
  
  if (event.notification.data?.mailId) {
    urlToOpen = `/read/${event.notification.data.mailId}`;
  }

  event.waitUntil(
    clients.matchAll({
      type: 'window'
    }).then(function(clientList) {
      // Check if there's already a window/tab open with the target URL
      for (let i = 0; i < clientList.length; i++) {
        const client = clientList[i];
        if (client.url.includes('/inbox') && 'focus' in client) {
          client.navigate(urlToOpen);
          return client.focus();
        }
      }
      
      // If no window is open, open a new one
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});

// Background sync for offline functionality
self.addEventListener('sync', function(event) {
  if (event.tag === 'background-sync') {
    event.waitUntil(
      // Perform background sync operations
      console.log('Background sync triggered')
    );
  }
});

// Handle service worker updates
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Listen for messages from the main thread
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
