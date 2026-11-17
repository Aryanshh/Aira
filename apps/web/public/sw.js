// AIRA Care Service Worker (ELD-V5)
const CACHE_NAME = "aira-elder-v1";
const STATIC_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/favicon.ico",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {
        // Soft fail for missing optional icons in dev
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Push Notifications Handler (Web Push)
self.addEventListener("push", (event) => {
  let data = {
    title: "AIRA Care Alert",
    body: "Critical medicine and elder safety alert.",
    url: "/status",
  };

  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body || "Critical medicine and elder safety alert.",
    icon: "/favicon.ico",
    badge: "/favicon.ico",
    vibrate: [200, 100, 200, 100, 200],
    data: { url: data.url || "/status" },
    tag: data.tag || "aira-care-alert",
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(data.title || "AIRA Care Alert", options));
});

// Notification Click Handler
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const urlToOpen = event.notification.data?.url || "/status";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url && client.url.includes(urlToOpen) && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});

// Network-first with Cache-fallback for API requests and Stale-while-revalidate for pages
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // For API calls to elders/me endpoints (doses, profile, contacts):
  if (url.pathname.includes("/api/v1/elders/me/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // For navigation or static assets:
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return networkResponse;
        })
        .catch(() => cached);

      return cached || fetchPromise;
    })
  );
});
