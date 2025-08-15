// Service Worker for BharatMail Push Notifications - Mobile Optimized
const CACHE_NAME = 'bharatmail-mobile-v2';
const urlsToCache = [
  '/',
  '/static/logo.png',
  '/static/logo-192.png',
  '/static/logo-512.png',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css'
];

// Mobile device detection
function isMobile() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// Install event - cache resources with mobile optimization
self.addEventListener('install', function(event) {
  console.log('Service Worker installing with mobile optimization');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('Opened cache for mobile');
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

// Push event - handle incoming push notifications with mobile optimization
self.addEventListener('push', function(event) {
  console.log('Push message received:', event);
  
  let notificationData = {};
  
  if (event.data) {
    try {
      notificationData = event.data.json();
    } catch (e) {
      notificationData = {
        title: '📧 New Email',
        body: event.data.text(),
        icon: '/static/logo-192.png',
        badge: '/static/logo.png'
      };
    }
  } else {
    notificationData = {
      title: '📧 New Email - BharatMail',
      body: 'You have received a new email',
      icon: '/static/logo-192.png',
      badge: '/static/logo.png'
    };
  }

  // Mobile-optimized vibration patterns
  const vibrationPattern = isMobile() ? [200, 100, 200, 100, 200] : [100, 50, 100];
  
  // Choose appropriate icon size for mobile
  const iconUrl = isMobile() ? '/static/logo-192.png' : '/static/logo.png';
  
  const notificationOptions = {
    body: notificationData.body,
    icon: notificationData.icon || iconUrl,
    badge: '/static/logo.png',
    vibrate: vibrationPattern,
    silent: false,
    timestamp: Date.now(),
    data: {
      url: notificationData.url || '/inbox',
      mailId: notificationData.mailId || null,
      timestamp: Date.now()
    },
    actions: isMobile() ? [
      {
        action: 'open',
        title: '📖 Open',
        icon: '/static/logo.png'
      },
      {
        action: 'dismiss',
        title: '✖️ Dismiss',
        icon: '/static/logo.png'
      }
    ] : [
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
    requireInteraction: isMobile(), // More aggressive on mobile
    tag: 'bharatmail-notification',
    renotify: true,
    sticky: isMobile() // Sticky on mobile for better visibility
  };

  // Add mobile-specific options
  if (isMobile()) {
    notificationOptions.dir = 'auto';
    notificationOptions.lang = 'en';
  }

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
