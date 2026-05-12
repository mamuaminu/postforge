'use client';

import { useEffect, useState } from 'react';
import { getPlatforms, connectPlatform } from '@/lib/api';

interface Platform {
  id: string;
  name: string;
  connected: boolean;
  icon?: string;
}

export default function PlatformsPage() {
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);

  useEffect(() => {
    getPlatforms()
      .then(setPlatforms)
      .catch(() => setPlatforms([]))
      .finally(() => setLoading(false));
  }, []);

  async function handleConnect(platformId: string) {
    setConnecting(platformId);
    try {
      const result = await connectPlatform(platformId);
      if (result.url) {
        window.open(result.url, '_blank');
      }
      const updated = await getPlatforms();
      setPlatforms(updated);
    } catch {
      // ignore
    } finally {
      setConnecting(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold" style={{ color: 'var(--text)', fontFamily: "'Fira Code', monospace" }}>
          Platforms
        </h2>
        <p className="mt-1" style={{ color: 'var(--text-muted)' }}>
          Connect your social accounts to start publishing.
        </p>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-muted)' }}>Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {platforms.map((platform) => (
            <div
              key={platform.id}
              className="rounded-xl p-6 flex items-center justify-between"
              style={{
                background: 'var(--bg-surface)',
                border: platform.connected
                  ? '1px solid rgba(34,197,94,0.4)'
                  : '1px dashed var(--border)',
              }}
            >
              <div className="flex items-center gap-4">
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold"
                  style={{
                    background: 'var(--bg-elevated)',
                    color: 'var(--text)',
                    border: platform.connected ? '2px solid var(--accent)' : '2px solid var(--border)',
                  }}
                >
                  {platform.name.charAt(0)}
                </div>
                <div>
                  <p className="font-medium" style={{ color: 'var(--text)' }}>
                    {platform.name}
                  </p>
                  <p
                    className="text-sm"
                    style={{ color: platform.connected ? 'var(--accent)' : 'var(--text-muted)' }}
                  >
                    {platform.connected ? 'Connected' : 'Not connected'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => handleConnect(platform.id)}
                disabled={connecting === platform.id || platform.connected}
                className="text-sm font-medium px-4 py-2 rounded-lg"
                style={{
                  background: platform.connected ? 'rgba(34,197,94,0.1)' : 'var(--accent)',
                  color: platform.connected ? 'var(--accent)' : '#fff',
                  opacity: connecting === platform.id ? 0.5 : platform.connected ? 0.6 : 1,
                  transition: 'all 150ms ease',
                  cursor: platform.connected ? 'not-allowed' : 'pointer',
                }}
                onMouseEnter={(e) => {
                  if (!platform.connected && !connecting) {
                    e.currentTarget.style.background = '#16a34a';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!platform.connected) {
                    e.currentTarget.style.background = 'var(--accent)';
                  }
                }}
              >
                {connecting === platform.id ? 'Connecting...' : platform.connected ? 'Connected' : 'Connect'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}