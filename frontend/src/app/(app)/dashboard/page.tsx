'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/store/auth';
import { getPosts, getPlatforms, generateContent } from '@/lib/api';

interface Post {
  id: string;
  content: string;
  platform: string;
  status: string;
  created_at: string;
}

interface Platform {
  id: string;
  name: string;
  connected: boolean;
}

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const [posts, setPosts] = useState<Post[]>([]);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [postsData, platformsData] = await Promise.all([
          getPosts().catch(() => []),
          getPlatforms().catch(() => []),
        ]);
        setPosts(postsData);
        setPlatforms(platformsData);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const connectedCount = platforms.filter((p) => p.connected).length;
  const recentPosts = posts.slice(0, 5);
  const publishedCount = posts.filter((p) => p.status === 'published').length;

  async function handleQuickGenerate() {
    setGenerating(true);
    try {
      await generateContent(
        'Your brand update',
        platforms.filter(p => p.connected).map(p => p.name),
        'Professional'
      );
    } catch {
      // silent
    } finally {
      setGenerating(false);
      const postsData = await getPosts().catch(() => []);
      setPosts(postsData);
    }
  }

  return (
    <div className="space-y-10 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold text-white tracking-tight">
          Good {getTimeOfDay()}, {user?.name?.split(' ')[0] || 'there'}
        </h2>
        <p className="text-gray-400 mt-2 text-sm">
          {connectedCount === 0
            ? 'Connect a platform to start publishing.'
            : `${connectedCount} platform${connectedCount > 1 ? 's' : ''} connected — you're ready to post.`}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Posts generated"
          value={posts.length}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          }
          accent="text-indigo-400"
        />
        <StatCard
          label="Published"
          value={publishedCount}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          }
          accent="text-emerald-400"
        />
        <StatCard
          label="Platforms"
          value={connectedCount}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
          }
          accent="text-amber-400"
        />
      </div>

      {/* Quick action */}
      <div className="flex items-center gap-4">
        <Link
          href="/generate"
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-medium px-5 py-2.5 rounded-lg transition-all duration-150 cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Generate content
        </Link>
        {connectedCount > 0 && (
          <button
            onClick={handleQuickGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 bg-gray-800 hover:bg-gray-700 active:scale-95 disabled:opacity-50 text-gray-300 font-medium px-5 py-2.5 rounded-lg transition-all duration-150 cursor-pointer"
          >
            {generating ? 'Opening...' : 'Quick post'}
          </button>
        )}
      </div>

      {/* Recent posts */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-white">Recent posts</h3>
          <Link href="/posts" className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors cursor-pointer">
            View all
          </Link>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 animate-pulse">
                <div className="h-4 bg-gray-800 rounded w-1/4 mb-3" />
                <div className="h-3 bg-gray-800 rounded w-3/4" />
              </div>
            ))}
          </div>
        ) : recentPosts.length === 0 ? (
          <div className="bg-gray-900/40 border border-dashed border-gray-800 rounded-xl p-10 text-center">
            <div className="mx-auto w-10 h-10 rounded-full bg-gray-800 flex items-center justify-center mb-3">
              <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
              </svg>
            </div>
            <p className="text-gray-400 text-sm font-medium">No posts yet</p>
            <p className="text-gray-500 text-xs mt-1">Generate your first post to get started</p>
            <Link href="/generate"
              className="inline-flex items-center gap-1.5 mt-4 text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors cursor-pointer">
              Create first post
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
              </svg>
            </Link>
          </div>
        ) : (
          <div className="bg-gray-900/40 border border-gray-800 rounded-xl divide-y divide-gray-800/60 overflow-hidden">
            {recentPosts.map((post) => (
              <div key={post.id} className="p-4 hover:bg-gray-800/30 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-900/40 text-indigo-300 border border-indigo-800/50">
                        {post.platform}
                      </span>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                        post.status === 'published'
                          ? 'bg-emerald-900/30 text-emerald-400'
                          : post.status === 'pending'
                          ? 'bg-amber-900/30 text-amber-400'
                          : 'bg-gray-800 text-gray-400'
                      }`}>
                        {post.status}
                      </span>
                      <span className="text-xs text-gray-500">
                        {formatDate(post.created_at)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-300 line-clamp-2 leading-relaxed">{post.content}</p>
                  </div>
                  <Link href="/posts"
                    className="text-xs text-gray-500 hover:text-indigo-400 transition-colors flex-shrink-0 mt-1 cursor-pointer">
                    View
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Connect platforms CTA */}
      {connectedCount === 0 && (
        <div className="bg-gradient-to-br from-indigo-900/30 to-purple-900/20 border border-indigo-800/40 rounded-xl p-6">
          <h4 className="text-white font-semibold text-sm mb-1">Connect your first platform</h4>
          <p className="text-gray-400 text-xs mb-4">Link your social accounts to start publishing directly from PostForge.</p>
          <Link href="/platforms"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors cursor-pointer">
            Connect platforms
          </Link>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, accent }: { label: string; value: number; icon: React.ReactNode; accent: string }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</p>
        <span className={accent}>{icon}</span>
      </div>
      <p className="text-3xl font-bold text-white tracking-tight">{value}</p>
    </div>
  );
}

function getTimeOfDay() {
  const h = new Date().getHours();
  if (h < 12) return 'morning';
  if (h < 17) return 'afternoon';
  return 'evening';
}

function formatDate(dateStr: string) {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}