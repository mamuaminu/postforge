'use client';

import { useEffect, useState } from 'react';
import { getPosts, deletePost } from '@/lib/api';

interface Post {
  id: string;
  content: string;
  platform: string;
  status: string;
  created_at: string;
}

export default function PostsPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    getPosts()
      .then(setPosts)
      .catch(() => setPosts([]))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(id: string) {
    if (!confirm('Delete this post?')) return;
    setDeleting(id);
    try {
      await deletePost(id);
      setPosts((prev) => prev.filter((p) => p.id !== id));
    } catch {
      // ignore
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold" style={{ color: 'var(--text)', fontFamily: "'Fira Code', monospace" }}>
          Posts
        </h2>
        <p className="mt-1" style={{ color: 'var(--text-muted)' }}>
          Manage all your generated content.
        </p>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-muted)' }}>Loading...</div>
      ) : posts.length === 0 ? (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-muted)' }}
        >
          No posts yet. Go to{' '}
          <a href="/generate" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
            Generate
          </a>{' '}
          to create your first post.
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <table className="w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th className="text-left px-5 py-3" style={{ color: 'var(--text-muted)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  Content
                </th>
                <th className="text-left px-5 py-3" style={{ color: 'var(--text-muted)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  Platform
                </th>
                <th className="text-left px-5 py-3" style={{ color: 'var(--text-muted)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  Status
                </th>
                <th className="text-left px-5 py-3" style={{ color: 'var(--text-muted)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  Date
                </th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {posts.map((post) => (
                <tr
                  key={post.id}
                  style={{ transition: 'background 150ms ease' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(30,41,59,0.5)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <td className="px-5 py-4">
                    <p className="text-sm line-clamp-2 max-w-md" style={{ color: '#cbd5e1' }}>
                      {post.content}
                    </p>
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--accent)' }}
                    >
                      {post.platform}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{
                        background: post.status === 'published' ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)',
                        color: post.status === 'published' ? '#4ade80' : '#fbbf24',
                      }}
                    >
                      {post.status}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-sm whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
                    {new Date(post.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-5 py-4">
                    <button
                      onClick={() => handleDelete(post.id)}
                      disabled={deleting === post.id}
                      className="text-xs"
                      style={{ color: 'var(--text-muted)', opacity: deleting === post.id ? 0.5 : 1, transition: 'color 150ms ease' }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#f87171')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                    >
                      {deleting === post.id ? 'Deleting...' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}