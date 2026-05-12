'use client';

import { useState } from 'react';
import { generateContent } from '@/lib/api';

const PLATFORMS = ['Facebook', 'X/Twitter', 'Instagram', 'LinkedIn', 'Threads'];
const TONES = ['Professional', 'Casual', 'Humorous', 'Inspirational'];

interface GeneratedPost {
  platform: string;
  content: string;
}

export default function GeneratePage() {
  const [topic, setTopic] = useState('');
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [tone, setTone] = useState('Professional');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<GeneratedPost[]>([]);
  const [error, setError] = useState('');

  function togglePlatform(p: string) {
    setSelectedPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  }

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    if (selectedPlatforms.length === 0) {
      setError('Select at least one platform.');
      return;
    }
    setError('');
    setLoading(true);
    setResults([]);
    try {
      const data = await generateContent(topic, selectedPlatforms, tone);
      setResults(data.posts || []);
    } catch (err: any) {
      setError(err.message || 'Generation failed');
    } finally {
      setLoading(false);
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).catch(() => {});
  }

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <h2 className="text-2xl font-bold" style={{ color: 'var(--text)', fontFamily: "'Fira Code', monospace" }}>
          Generate Content
        </h2>
        <p className="mt-1" style={{ color: 'var(--text-muted)' }}>
          Create platform-ready posts in seconds.
        </p>
      </div>

      <form
        onSubmit={handleGenerate}
        className="rounded-xl p-6 space-y-6"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
      >
        <div>
          <label className="block text-sm font-medium mb-1.5" style={{ color: '#cbd5e1' }}>
            Topic / Keyword
          </label>
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            rows={3}
            className="w-full rounded-lg px-4 py-2.5 resize-none"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text)',
              outline: 'none',
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
            placeholder="e.g. Why remote work is the future of productivity"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: '#cbd5e1' }}>
            Platforms
          </label>
          <div className="flex flex-wrap gap-2">
            {PLATFORMS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => togglePlatform(p)}
                className="px-4 py-2 rounded-lg text-sm font-medium"
                style={{
                  background: selectedPlatforms.includes(p) ? 'var(--accent)' : 'var(--bg-elevated)',
                  color: selectedPlatforms.includes(p) ? '#fff' : 'var(--text-muted)',
                  border: selectedPlatforms.includes(p) ? 'none' : '1px solid var(--border)',
                  transition: 'all 150ms ease',
                }}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: '#cbd5e1' }}>
            Tone
          </label>
          <div className="flex flex-wrap gap-2">
            {TONES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTone(t)}
                className="px-4 py-2 rounded-lg text-sm font-medium"
                style={{
                  background: tone === t ? 'var(--accent)' : 'var(--bg-elevated)',
                  color: tone === t ? '#fff' : 'var(--text-muted)',
                  border: tone === t ? 'none' : '1px solid var(--border)',
                  transition: 'all 150ms ease',
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div
            className="rounded-lg px-4 py-2.5 text-sm"
            style={{ background: 'rgba(220,38,38,0.15)', border: '1px solid rgba(220,38,38,0.3)', color: '#fca5a5' }}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full font-medium py-2.5 rounded-lg"
          style={{
            background: 'var(--accent)',
            color: '#fff',
            opacity: loading ? 0.5 : 1,
            transition: 'all 150ms ease',
          }}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background = '#16a34a'; }}
          onMouseLeave={(e) => { if (!loading) e.currentTarget.style.background = 'var(--accent)'; }}
        >
          {loading ? 'Generating...' : 'Generate Content'}
        </button>
      </form>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Generated Posts
          </h3>
          {results.map((post, i) => (
            <div
              key={i}
              className="rounded-xl p-5"
              style={{ background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(34,197,94,0.3)' }}
            >
              <div className="flex items-center justify-between mb-3">
                <span
                  className="text-sm font-medium px-2.5 py-0.5 rounded-full"
                  style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--accent)' }}
                >
                  {post.platform}
                </span>
                <button
                  onClick={() => copyToClipboard(post.content)}
                  className="text-xs flex items-center gap-1"
                  style={{ color: 'var(--text-muted)', transition: 'color 150ms ease' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#4ade80')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>
                  Copy
                </button>
              </div>
              <p className="text-sm whitespace-pre-wrap" style={{ color: '#cbd5e1' }}>
                {post.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}